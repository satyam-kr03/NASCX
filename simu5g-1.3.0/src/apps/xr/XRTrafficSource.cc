#include "XRTrafficSource.h"
#include <set>
#include <cmath>
#include <cstdio>
#include "inet/common/ModuleAccess.h"
#include "inet/common/packet/Packet.h"
#include "inet/common/TimeTag_m.h"
#include "inet/networklayer/common/L3AddressTag_m.h"
#include "inet/transportlayer/common/L4PortTag_m.h"
#include "inet/common/lifecycle/NodeStatus.h"
#include "apps/xr/XRHeader_m.h"
#include "common/binder/Binder.h"
#include "stack/mac/amc/LteAmc.h"
#include "stack/mac/buffer/LteMacBuffer.h"
#include "stack/mac/scheduler/LteSchedulerEnb.h"

namespace simu5g
{

    Define_Module(XRTrafficSource);

    XRTrafficSource::~XRTrafficSource()
    {
        cancelAndDelete(sendTimer);
    }

    void XRTrafficSource::initialize(int stage)
    {
        ApplicationBase::initialize(stage);

        if (stage == INITSTAGE_LOCAL)
        {
            // Initialize parameters
            fps = par("fps").doubleValue();
            jitter_mean = par("jitterMean").doubleValue();
            jitter_sd = par("jitterStd").doubleValue();
            jitter_min = par("jitterMin").doubleValue();
            jitter_max = par("jitterMax").doubleValue();
            seed_val = par("jitterSeed").intValue();
            startTime = par("startTime");

            localPort = par("localPort").intValue();
            destPort = par("destPort").intValue();
            destAddressStr = par("destAddress").stdstringValue();
            pcaFile = par("pcaFile").stdstringValue();
            compressionLevel_ = par("compressionLevel").intValue();
            selectionMode_ = par("selectionMode").stdstringValue();
            prescribedFile_ = par("prescribedFile").stdstringValue();
            modelServerUrl_ = par("modelServerUrl").stdstringValue();
            modelNumUsers_ = par("modelNumUsers").intValue();
            modelDefaultCqi_ = par("modelDefaultCqi").intValue();

            frame_number = 0;
            sendTimer = new cMessage("sendTimer");

            // Register signals
            sentPktSignal = registerSignal("sentPkt");
            sentBytesSignal = registerSignal("sentBytes");

            // Initialize binder pointer to nullptr
            binder_ = nullptr;
            macNodeId_ = NODEID_NONE;
            gnbMac_ = nullptr;

            // Load PCA reconstruction data
            loadPCAData(pcaFile);

            // Load prescribed schedule if in prescribed mode
            if (selectionMode_ == "prescribed" && !prescribedFile_.empty())
            {
                loadPrescribedData(prescribedFile_);
            }
            socket.setOutputGate(gate("socketOut"));
            socket.setCallback(this);
        }
        else if (stage == INITSTAGE_APPLICATION_LAYER)
        {
            // Resolve destination address
            destAddress = L3AddressResolver().resolve(destAddressStr.c_str());

            binder_ = getBinderModule();

            // For downlink: get DESTINATION UE's MAC ID, not source
            if (!destAddress.isUnspecified() && destAddress.getType() == inet::L3Address::IPv4)
            {
                macNodeId_ = binder_->getMacNodeId(destAddress.toIpv4());
            }

            EV << "XRTrafficSource initialized with " << frames.size()
               << " frames, FPS=" << fps << ", dest=" << destAddress
               << ":" << destPort << ", macNodeId=" << macNodeId_
               << ", mode=" << selectionMode_ << endl;

            // Resolve gNB MAC module for buffer/utilization queries
            try {
                cModule *serverModule = getParentModule();
                cModule *networkModule = getSimulation()->getSystemModule();
                cModule *gnbModule = networkModule->getSubmodule("gnb");
                if (gnbModule) {
                    cModule *cellularNic = gnbModule->getSubmodule("cellularNic");
                    if (cellularNic) {
                        // Try NR MAC first, then fall back to regular MAC
                        cModule *macModule = cellularNic->getSubmodule("nrMac");
                        if (!macModule) macModule = cellularNic->getSubmodule("mac");
                        if (macModule) {
                            gnbMac_ = dynamic_cast<LteMacEnb*>(macModule);
                        }
                    }
                }
            } catch (...) {
                EV_WARN << "Could not resolve gNB MAC module" << endl;
            }
            std::cout << "XRTrafficSource: gnbMac_=" << (gnbMac_ ? "resolved" : "null") << endl;

        }
    }

    void XRTrafficSource::handleStartOperation(LifecycleOperation *operation)
    {
        // Bind socket when application is starting
        socket.bind(localPort);

        // Make sure destination address is resolved
        if (destAddress.isUnspecified())
        {
            destAddress = L3AddressResolver().resolve(destAddressStr.c_str());
        }

        if (destAddress.isUnspecified())
        {
            error("XRTrafficSource: Could not resolve destination address: %s", destAddressStr.c_str());
            return;
        }

        if (binder_ != nullptr && destAddress.getType() == inet::L3Address::IPv4)
        {
            macNodeId_ = binder_->getMacNodeId(destAddress.toIpv4());
        }

        // In model mode, store video stats in Binder so all sources
        // can gather each other's features for batched model queries
        if (selectionMode_ == "model" && binder_ != nullptr && macNodeId_ != NODEID_NONE)
        {
            binder_->setXRVideoStats(macNodeId_, meanTrafficSize_, stdTrafficSize_, fps);
            std::cout << "XRTrafficSource: Stored video stats in Binder for UE "
                      << macNodeId_ << " (mean=" << meanTrafficSize_
                      << ", std=" << stdTrafficSize_ << ", fps=" << fps << ")" << endl;
        }

        // Connect to the destination
        socket.connect(destAddress, destPort);

        // Schedule first packet after socket is bound and application is started
        if (getFrameCount() > 0)
        {
            double jitter_ms = tran_gau_num(jitter_mean, jitter_sd, jitter_min, jitter_max);
            double sendDelay = (1.0 / fps) + (jitter_ms / 1000.0);
            simtime_t firstSendTime = simTime() + startTime + sendDelay;
            scheduleAt(firstSendTime, sendTimer);
            EV << "First packet scheduled at " << firstSendTime << endl;
        }
        else
        {
            EV_ERROR << "No frames loaded, cannot schedule transmission!" << endl;
        }
    }

    void XRTrafficSource::handleStopOperation(LifecycleOperation *operation)
    {
        cancelEvent(sendTimer);
        socket.close();
    }

    void XRTrafficSource::handleCrashOperation(LifecycleOperation *operation)
    {
        cancelEvent(sendTimer);
        if (socket.isOpen())
            socket.destroy();
    }

    void XRTrafficSource::handleMessageWhenUp(cMessage *msg)
    {
        if (msg->isSelfMessage())
        {
            if (msg == sendTimer)
            {
                sendPacket();
                scheduleNextPacket();
            }
        }
        else
        {
            // Process incoming socket messages
            socket.processMessage(msg);
        }
    }

    void XRTrafficSource::sendPacket()
    {
        int totalFrames = getFrameCount();
        if (frame_number >= totalFrames)
        {
            EV << "All frames sent, stopping transmission" << endl;
            return;
        }

        FrameInfo frameInfo;

        if (selectionMode_ == "random")
        {
            // Random per-frame compression selection
            int frameNum = frameNumbers_[frame_number];
            int compIdx = intuniform(0, availableComponents_.size() - 1);
            int chosenComponents = availableComponents_[compIdx];

            auto frameIt = allFrameData_.find(frameNum);
            if (frameIt != allFrameData_.end())
            {
                auto compIt = frameIt->second.find(chosenComponents);
                if (compIt != frameIt->second.end())
                {
                    frameInfo = compIt->second;
                }
                else
                {
                    EV_ERROR << "No data for frame " << frameNum
                             << " at components=" << chosenComponents << endl;
                    frame_number++;
                    return;
                }
            }
            else
            {
                EV_ERROR << "No data for frame " << frameNum << endl;
                frame_number++;
                return;
            }
        }
        else if (selectionMode_ == "prescribed")
        {
            // Prescribed mode: look up components from prescribed schedule
            int frameNum = frameNumbers_[frame_number];
            auto prescIt = prescribedComponents_.find(frameNum);
            int chosenComponents;
            if (prescIt != prescribedComponents_.end())
            {
                chosenComponents = prescIt->second;
            }
            else
            {
                // Fallback: use middle compression level
                chosenComponents = availableComponents_[availableComponents_.size() / 2];
                EV_WARN << "No prescribed level for frame " << frameNum
                        << ", using fallback=" << chosenComponents << endl;
            }

            auto frameIt = allFrameData_.find(frameNum);
            if (frameIt != allFrameData_.end())
            {
                auto compIt = frameIt->second.find(chosenComponents);
                if (compIt != frameIt->second.end())
                {
                    frameInfo = compIt->second;
                }
                else
                {
                    EV_ERROR << "No PCA data for frame " << frameNum
                             << " at prescribed components=" << chosenComponents << endl;
                    frame_number++;
                    return;
                }
            }
            else
            {
                EV_ERROR << "No PCA data for frame " << frameNum << endl;
                frame_number++;
                return;
            }
        }
        else if (selectionMode_ == "model")
        {
            // Model mode: query the model API with live CQI from Binder
            int frameNum = frameNumbers_[frame_number];
            int chosenComponents = queryModelServer(frameNum);

            auto frameIt = allFrameData_.find(frameNum);
            if (frameIt != allFrameData_.end())
            {
                auto compIt = frameIt->second.find(chosenComponents);
                if (compIt != frameIt->second.end())
                {
                    frameInfo = compIt->second;
                }
                else
                {
                    // Fallback: find closest available compression level
                    int closest = availableComponents_[0];
                    int minDist = abs(chosenComponents - closest);
                    for (int c : availableComponents_)
                    {
                        int dist = abs(chosenComponents - c);
                        if (dist < minDist) { minDist = dist; closest = c; }
                    }
                    auto closestIt = frameIt->second.find(closest);
                    if (closestIt != frameIt->second.end())
                    {
                        frameInfo = closestIt->second;
                        EV_WARN << "Model suggested components=" << chosenComponents
                                << " not in data, using closest=" << closest << endl;
                    }
                    else
                    {
                        EV_ERROR << "No data for frame " << frameNum << endl;
                        frame_number++;
                        return;
                    }
                }
            }
            else
            {
                EV_ERROR << "No data for frame " << frameNum << endl;
                frame_number++;
                return;
            }
        }
        else
        {
            // Fixed mode: use legacy frames vector
            frameInfo = frames[frame_number];
        }

        // Update binder with XR metrics for this frame
        if (frameInfo.frame_number != lastFrameUpdated)
        {
            if (binder_ != nullptr && macNodeId_ != NODEID_NONE)
            {
                binder_->setXRMetrics(macNodeId_, frameInfo.frame_number, frameInfo.mse, frameInfo.size_bytes);
                lastFrameUpdated = frameInfo.frame_number;
            }
        }

        // Update gNB-level metrics (buffer, MCS, utilization, active UEs)
        updateGnbMetrics();
        // Get max payload size from parameter
        int maxPayloadSize = par("maxPayloadSize").intValue();

        // Calculate number of fragments needed
        int totalFragments = (frameInfo.size_bytes + maxPayloadSize - 1) / maxPayloadSize;
        int remainingBytes = frameInfo.size_bytes;

        // Send each fragment
        for (int fragIndex = 0; fragIndex < totalFragments; fragIndex++)
        {
            // Calculate fragment size
            int fragSize = std::min(remainingBytes, maxPayloadSize);
            remainingBytes -= fragSize;

            // Create INET packet with descriptive name
            char msgName[64];
            sprintf(msgName, "XRFrame-F%d-C%d-Frag%d",
                    frameInfo.frame_number, frameInfo.components, fragIndex);
            Packet *packet = new Packet(msgName);

            // Create and populate XR header
            auto header = makeShared<XRHeader>();
            header->setFrameNumber(frameInfo.frame_number);
            header->setPcaComponents(frameInfo.components);
            header->setMse(frameInfo.mse);
            header->setSizeBytes(frameInfo.size_bytes);
            header->setGenTime(simTime().dbl());
            header->setFragIndex(fragIndex);
            header->setTotalFragments(totalFragments);
            header->setChunkLength(B(32)); // Fixed header size

            // Add header to packet
            packet->insertAtFront(header);

            // Add payload data
            const auto &payload = makeShared<ByteCountChunk>(B(fragSize));
            packet->insertAtBack(payload);

            // Add timestamp tag
            auto creationTimeTag = packet->addTag<CreationTimeTag>();
            creationTimeTag->setCreationTime(simTime());

            // Check if socket is open before sending
            if (!socket.isOpen())
            {
                EV_ERROR << "Socket not open, cannot send packet" << endl;
                delete packet;
                return;
            }

            // Send via UDP socket (INET takes ownership of the packet)
            socket.send(packet);

            // Update statistics (only once per frame)
            if (fragIndex == 0)
            {
                emit(sentPktSignal, 1);
                emit(sentBytesSignal, (long)frameInfo.size_bytes);
            }
        }

        EV << "Sent frame " << frameInfo.frame_number
           << ": components=" << frameInfo.components
           << ", size=" << frameInfo.size_bytes << " bytes"
           << ", MSE=" << frameInfo.mse
           << ", fragments=" << totalFragments
           << ", mode=" << selectionMode_ << endl;

        frame_number++;
    }

    void XRTrafficSource::scheduleNextPacket()
    {
        if (frame_number >= getFrameCount())
        {
            return;
        }

        // Calculate next send time with jitter
        double jitter_ms = tran_gau_num(jitter_mean, jitter_sd, jitter_min, jitter_max);
        double intervalWithJitter = (1.0 / fps) + (jitter_ms / 1000.0);

        scheduleAt(simTime() + intervalWithJitter, sendTimer);
    }

    double XRTrafficSource::tran_gau_num(double mean, double sd, double minv, double maxv)
    {
        // Truncated Gaussian using OMNeT++ normal() function
        double x = normal(mean, sd, seed_val);
        int attempts = 0;

        while ((x < minv || x > maxv) && attempts < 1000)
        {
            x = normal(mean, sd, seed_val);
            attempts++;
        }

        // Clamp to valid range if necessary
        if (x < minv)
            x = minv;
        if (x > maxv)
            x = maxv;

        return x;
    }

    void XRTrafficSource::loadPCAData(const string &pcaFile)
    {
        ifstream f(pcaFile);
        if (!f.is_open())
        {
            EV_ERROR << "Cannot open PCA data file: " << pcaFile << endl;
            error("Failed to open PCA reconstruction file");
            return;
        }

        string line;
        // Skip header line
        if (!getline(f, line))
        {
            EV_ERROR << "Empty PCA file: " << pcaFile << endl;
            return;
        }

        // Parse data lines: frame,components,mse,size_bytes
        int lineNum = 1;
        std::set<int> uniqueFrames;
        std::set<int> uniqueComponents;

        while (getline(f, line))
        {
            lineNum++;
            if (line.empty())
                continue;

            // Parse CSV line
            stringstream ss(line);
            string field;
            vector<string> fields;

            while (getline(ss, field, ','))
            {
                // Trim whitespace
                field.erase(remove_if(field.begin(), field.end(), ::isspace), field.end());
                fields.push_back(field);
            }

            if (fields.size() < 4)
            {
                EV_WARN << "Skipping malformed line " << lineNum << " in " << pcaFile
                        << " (expected 4 fields, got " << fields.size() << ")" << endl;
                continue;
            }

            try
            {
                FrameInfo fi;
                fi.frame_number = stoi(fields[0]);
                fi.components = stoi(fields[1]);
                fi.mse = stod(fields[2]);
                fi.size_bytes = stoi(fields[3]);

                // Columns from our python scripts: 
                // frame(0), components(1), mse(2), size_bytes(3), ...
                // Error vector is built from allFrameData_ after loading (post-processing step).

                if (fields.size() >= 5)
                {
                    double fc_or_at80 = stod(fields[4]);
                    
                    // Keep frameComplexity population for legacy compatibility
                    if (frameComplexity_.find(fi.frame_number) == frameComplexity_.end())
                    {
                        frameComplexity_[fi.frame_number] = fc_or_at80;
                    }
                }

                // Always store in allFrameData_ for any selection mode
                allFrameData_[fi.frame_number][fi.components] = fi;

                // Track unique frames and components (exclude uncompressed)
                uniqueFrames.insert(fi.frame_number);
                if (fi.components != 150528 && fi.components != 0)  // Exclude uncompressed
                {
                    uniqueComponents.insert(fi.components);
                }

                // For "fixed" mode: also populate legacy frames vector
                if (selectionMode_ == "fixed")
                {
                    if (compressionLevel_ == 0 || fi.components == compressionLevel_)
                    {
                        frames.push_back(fi);
                    }
                }
            }
            catch (const exception &e)
            {
                EV_WARN << "Error parsing line " << lineNum << " in " << pcaFile
                        << ": " << e.what() << endl;
            }
        }

        f.close();

        // Build sorted vectors from sets
        frameNumbers_.assign(uniqueFrames.begin(), uniqueFrames.end());
        availableComponents_.assign(uniqueComponents.begin(), uniqueComponents.end());

        int totalLoaded = (selectionMode_ == "random") ? (int)frameNumbers_.size() : (int)frames.size();

        EV << "Loaded PCA data from " << pcaFile
           << ": " << uniqueFrames.size() << " unique frames"
           << ", " << availableComponents_.size() << " compression levels"
           << ", selectionMode=" << selectionMode_
           << ", effective frame count=" << totalLoaded << endl;

        // Post-process: build per-frame error vector from allFrameData_
        // For each unique frame, extract MSE at each of the 16 CLs (5,10,...,80)
        {
            const int clStep = 5;
            for (const auto &framePair : allFrameData_)
            {
                int fn = framePair.first;
                std::vector<double> errVec(NUM_CL_LEVELS, 0.0);
                for (int k = 0; k < NUM_CL_LEVELS; k++)
                {
                    int cl = (k + 1) * clStep;  // 5, 10, ..., 80
                    auto compIt = framePair.second.find(cl);
                    if (compIt != framePair.second.end())
                    {
                        errVec[k] = compIt->second.mse;
                    }
                }
                frameErrorVector_[fn] = errVec;
            }
            EV << "  Built error vectors for " << frameErrorVector_.size() << " frames (" << NUM_CL_LEVELS << " CLs each)" << endl;
        }

        if (selectionMode_ == "random")
        {
            EV << "  Available components: ";
            for (int c : availableComponents_) EV << c << " ";
            EV << endl;
        }

        if (!frames.empty() || !frameNumbers_.empty())
        {
            // Calculate summary statistics from allFrameData_
            double avgMSE = 0;
            int count = 0;
            for (const auto &framePair : allFrameData_)
            {
                for (const auto &compPair : framePair.second)
                {
                    avgMSE += compPair.second.mse;
                    count++;
                }
            }
            if (count > 0) avgMSE /= count;
            EV << "  Overall average MSE across all levels: " << avgMSE << endl;
        }

        // Compute mean and std of frame_complexity for model mode
        if (!frameComplexity_.empty())
        {
            double sumFC = 0;
            for (const auto &p : frameComplexity_) sumFC += p.second;
            meanTrafficSize_ = sumFC / frameComplexity_.size();

            double sumSqDiff = 0;
            for (const auto &p : frameComplexity_)
            {
                double diff = p.second - meanTrafficSize_;
                sumSqDiff += diff * diff;
            }
            stdTrafficSize_ = sqrt(sumSqDiff / frameComplexity_.size());

            EV << "  Video stats: meanTrafficSize=" << meanTrafficSize_
               << ", stdTrafficSize=" << stdTrafficSize_
               << ", frames with complexity=" << frameComplexity_.size() << endl;
        }
    }

    void XRTrafficSource::loadPrescribedData(const string &prescribedFile)
    {
        ifstream f(prescribedFile);
        if (!f.is_open())
        {
            EV_ERROR << "Cannot open prescribed file: " << prescribedFile << endl;
            error("Failed to open prescribed compression schedule file");
            return;
        }

        string line;
        // Skip header line (frame,components)
        if (!getline(f, line))
        {
            EV_ERROR << "Empty prescribed file: " << prescribedFile << endl;
            return;
        }

        int loaded = 0;
        while (getline(f, line))
        {
            if (line.empty())
                continue;

            stringstream ss(line);
            string field;
            vector<string> fields;

            while (getline(ss, field, ','))
            {
                field.erase(remove_if(field.begin(), field.end(), ::isspace), field.end());
                fields.push_back(field);
            }

            if (fields.size() < 2)
                continue;

            try
            {
                int frameNum = stoi(fields[0]);
                int components = stoi(fields[1]);
                prescribedComponents_[frameNum] = components;
                loaded++;
            }
            catch (const exception &e)
            {
                EV_WARN << "Error parsing prescribed file line: " << e.what() << endl;
            }
        }

        f.close();

        EV << "Loaded " << loaded << " prescribed compression levels from " << prescribedFile << endl;
    }

    int XRTrafficSource::getFrameCount() const
    {
        if (selectionMode_ == "random" || selectionMode_ == "prescribed" || selectionMode_ == "model")
            return (int)frameNumbers_.size();
        else
            return (int)frames.size();
    }

    void XRTrafficSource::updateGnbMetrics()
    {
        if (binder_ == nullptr || macNodeId_ == NODEID_NONE || gnbMac_ == nullptr)
            return;

        // 1. Per-UE DL buffer occupancy — sum across all CIDs for this UE's destination
        unsigned int totalBufferBytes = 0;
        LteMacBufferMap *macBuffers = gnbMac_->getMacBuffers();
        if (macBuffers) {
            for (auto &[cid, buffer] : *macBuffers) {
                // CID encodes the destination nodeId in the upper bits
                MacNodeId cidNodeId = MacCidToNodeId(cid);
                if (cidNodeId == macNodeId_) {
                    totalBufferBytes += buffer->getQueueOccupancy();
                }
            }
        }
        binder_->setXRBufferBytes(macNodeId_, totalBufferBytes);

        // 2. Per-UE MCS index from AMC (CQI → iTBS mapping)
        unsigned int mcsIndex = 0;
        LteAmc *amc = gnbMac_->getAmc();
        if (amc) {
            unsigned int cqi = binder_->getXRCqi(macNodeId_);
            if (cqi == 0) cqi = (unsigned int)modelDefaultCqi_;
            if (cqi < 1) cqi = 1;
            if (cqi > 15) cqi = 15;
            mcsIndex = amc->getItbsPerCqi((Cqi)cqi, DL);
        }
        binder_->setXRMcsIndex(macNodeId_, mcsIndex);

        // 3. DL scheduler utilization [0.0 - 1.0]
        double util = gnbMac_->getUtilization(DL) / 100.0;  // getUtilization returns percentage
        binder_->setDlUtilization(util);

        // 4. Active UE count
        int activeUes = gnbMac_->getActiveUesNumber(DL);
        binder_->setNActiveUes(activeUes);
    }

    void XRTrafficSource::finish()
    {
        ApplicationBase::finish();
        EV << "XRTrafficSource finished. Sent " << frame_number << " frames." << endl;
    }

    // UdpSocket::ICallback implementations
    void XRTrafficSource::socketDataArrived(UdpSocket *socket, Packet *packet)
    {
        // This is a traffic source, we don't expect to receive data
        EV_WARN << "Received unexpected packet: " << packet->getName() << endl;
        delete packet;
    }

    void XRTrafficSource::socketErrorArrived(UdpSocket *socket, Indication *indication)
    {
        EV_WARN << "Socket error occurred" << endl;
        delete indication;
    }

    void XRTrafficSource::socketClosed(UdpSocket *socket)
    {
        EV << "Socket closed" << endl;
    }

    Binder *XRTrafficSource::getBinderModule()
    {
        // Method 1: Direct path lookup
        Binder *binder = dynamic_cast<Binder *>(
            getSimulation()->getModuleByPath("binder"));

        if (binder != nullptr)
        {
            return binder;
        }

        // Method 2: Search for Binder type
        cModule *networkModule = getSimulation()->getSystemModule();
        for (cModule::SubmoduleIterator it(networkModule); !it.end(); ++it)
        {
            Binder *b = dynamic_cast<Binder *>(*it);
            if (b != nullptr)
            {
                return b;
            }
        }

        return nullptr;
    }

    MacNodeId XRTrafficSource::getMacNodeIdFromModule()
    {
        cModule *ueModule = getParentModule();

        // Try different NIC names
        const char *nicNames[] = {"cellularNic", "nrNic", "nic"};

        for (const char *nicName : nicNames)
        {
            cModule *nic = ueModule->getSubmodule(nicName);
            if (nic != nullptr)
            {
                cModule *mac = nic->getSubmodule("mac");
                if (mac != nullptr)
                {
                    // Try different parameter names
                    if (mac->hasPar("macNodeId"))
                    {
                        return MacNodeId(mac->par("macNodeId").intValue());
                    }
                    if (mac->hasPar("nrMacNodeId"))
                    {
                        return MacNodeId(mac->par("nrMacNodeId").intValue());
                    }
                }
            }
        }

        // Fallback: IP address lookup
        if (binder_ != nullptr)
        {
            inet::L3AddressResolver resolver;
            inet::L3Address addr = resolver.addressOf(ueModule);
            if (!addr.isUnspecified() && addr.getType() == inet::L3Address::IPv4)
            {
                return binder_->getMacNodeId(addr.toIpv4());
            }
        }

        return NODEID_NONE;
    }

    std::string XRTrafficSource::httpPost(const std::string& url, const std::string& jsonPayload)
    {
        // Write payload to a temp file to avoid shell quoting issues
        std::string tmpFile = "/tmp/xr_model_payload_" + std::to_string(getSimulation()->getUniqueNumber()) + ".json";
        {
            std::ofstream ofs(tmpFile);
            ofs << jsonPayload;
            ofs.close();
        }

        // Use wget (curl not always available)
        std::string command = "wget -qO- --header='Content-Type: application/json' "
                              "--post-file='" + tmpFile + "' '" + url + "' 2>/dev/null";

        FILE *pipe = popen(command.c_str(), "r");
        if (!pipe)
        {
            EV_ERROR << "httpPost: popen failed for " << url << endl;
            std::remove(tmpFile.c_str());
            return "";
        }

        std::string result;
        char buffer[4096];
        while (fgets(buffer, sizeof(buffer), pipe) != nullptr)
        {
            result += buffer;
        }
        int status = pclose(pipe);
        std::remove(tmpFile.c_str());

        if (status != 0)
        {
            EV_WARN << "httpPost: wget returned status " << status
                    << " for " << url << endl;
        }

        return result;
    }

    int XRTrafficSource::queryModelServer(int frameNum)
    {
        if (binder_ == nullptr || macNodeId_ == NODEID_NONE)
        {
            EV_WARN << "queryModelServer: Binder not available, using default" << endl;
            return availableComponents_[availableComponents_.size() / 2];
        }

        // Gather all XR users' node IDs from the Binder
        std::vector<MacNodeId> allUsers = binder_->getXRUserNodeIds();
        int numUsers = (int)allUsers.size();

        // The model requires at least 2 users
        if (numUsers < 2)
        {
            EV_WARN << "queryModelServer: Only " << numUsers
                    << " users registered, need >= 2. Using fallback." << endl;
            return availableComponents_[availableComponents_.size() / 2];
        }

        // Find our own index in the user list
        int myIndex = -1;
        for (int i = 0; i < numUsers; i++)
        {
            if (allUsers[i] == macNodeId_)
            {
                myIndex = i;
                break;
            }
        }
        if (myIndex < 0)
        {
            EV_WARN << "queryModelServer: Own macNodeId " << macNodeId_
                    << " not found in Binder user list. Using fallback." << endl;
            return availableComponents_[availableComponents_.size() / 2];
        }

        // Get this frame's full error vector (MSE at each CL)
        std::vector<double> myErrorVector(NUM_CL_LEVELS, 0.0);
        auto evIt = frameErrorVector_.find(frameNum);
        if (evIt != frameErrorVector_.end()) {
            myErrorVector = evIt->second;
        }

        // Update Binder with our current true metrics so peers see real data
        binder_->setXRErrorMetrics(macNodeId_, myErrorVector);

        // Build JSON payload: {"users": [{...}, {...}, ...]}
        std::ostringstream json;
        json << "{\"users\":[";
        for (int i = 0; i < numUsers; i++)
        {
            MacNodeId uid = allUsers[i];
            const XRVideoStats *stats = binder_->getXRVideoStats(uid);
            unsigned int cqi = binder_->getXRCqi(uid);
            double prevDelayMs = binder_->getXRVideoPrevDelayMs(uid);

            double frate = stats ? stats->frameRate : 60;

            // Get the full error vector for this user from Binder
            std::vector<double> errVec(NUM_CL_LEVELS, 0.0);
            if (stats) {
                errVec = stats->currentErrorVector;
            }

            // Clamp CQI to model range [5, 15]
            if (cqi == 0) cqi = (unsigned int)modelDefaultCqi_;
            if (cqi < 5) cqi = 5;
            if (cqi > 15) cqi = 15;

            if (i > 0) json << ",";
            // Build mse_vector JSON array
            json << "{\"mse_vector\":[";
            for (int k = 0; k < NUM_CL_LEVELS; k++) {
                if (k > 0) json << ",";
                json << errVec[k];
            }
            json << "]"
                 << ",\"frame_rate\":" << frate
                 << ",\"cqi\":" << cqi 
                 << ",\"prev_delay_ms\":" << prevDelayMs
                 << ",\"buffer_bytes\":" << binder_->getXRBufferBytes(uid)
                 << ",\"mcs_index\":" << binder_->getXRMcsIndex(uid) << "}";
        }
        json << "],"
             << "\"dl_utilization\":" << binder_->getDlUtilization()
             << ",\"n_active_ues\":" << binder_->getNActiveUes()
             << "}";

        // Make HTTP request
        std::string url = modelServerUrl_ + "/predict";
        std::string response = httpPost(url, json.str());

        if (response.empty())
        {
            EV_WARN << "queryModelServer: Empty response from " << url << endl;
            return availableComponents_[availableComponents_.size() / 2];
        }

        // Parse response JSON to extract our user's optimal_components.
        // Response format: {"predictions": [{"user_id": 0, "optimal_components": 200, ...}, ...]}
        // Simple JSON extraction without a library:
        int chosenComponents = availableComponents_[availableComponents_.size() / 2];

        // Find the prediction for our user_id
        std::string searchKey = "\"user_id\":" + std::to_string(myIndex);
        size_t pos = response.find(searchKey);
        if (pos != std::string::npos)
        {
            // Find "optimal_components": NNN after this position
            std::string compKey = "\"optimal_components\":";
            size_t compPos = response.find(compKey, pos);
            if (compPos != std::string::npos)
            {
                compPos += compKey.length();
                // Skip whitespace
                while (compPos < response.size() && (response[compPos] == ' ' || response[compPos] == '\t'))
                    compPos++;
                // Read the integer
                std::string numStr;
                while (compPos < response.size() && std::isdigit(response[compPos]))
                {
                    numStr += response[compPos];
                    compPos++;
                }
                if (!numStr.empty())
                {
                    chosenComponents = std::stoi(numStr);
                }
            }
        }
        else
        {
            EV_WARN << "queryModelServer: Could not find user_id=" << myIndex
                    << " in response: " << response.substr(0, 200) << endl;
        }

        EV << "queryModelServer: frame=" << frameNum
           << " myIndex=" << myIndex
           << " cqi=" << binder_->getXRCqi(macNodeId_)
           << " → components=" << chosenComponents << endl;

        return chosenComponents;
    }

} // namespace simu5g