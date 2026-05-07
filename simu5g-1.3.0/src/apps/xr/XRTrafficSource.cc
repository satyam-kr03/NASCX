#include "XRTrafficSource.h"
#include "apps/xr/XRUtils.h"
#include <set>
#include <cmath>
#include <cstdio>
#include <cctype>
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
#include <regex>
#include <unistd.h>

using std::endl;

namespace {

class TempFile
{
public:
    explicit TempFile(const std::string &prefix)
    {
        std::string templ = "/tmp/" + prefix + "_XXXXXX";
        std::vector<char> pathBuf(templ.begin(), templ.end());
        pathBuf.push_back('\0');
        int fd = mkstemp(pathBuf.data());
        if (fd == -1)
        {
            return;
        }
        close(fd);
        path_ = pathBuf.data();
    }

    ~TempFile()
    {
        if (!path_.empty())
        {
            std::remove(path_.c_str());
        }
    }

    const std::string &path() const { return path_; }
    bool valid() const { return !path_.empty(); }

private:
    std::string path_;
};

int findJsonIntField(const std::string &obj, const std::string &key, int fallback)
{
    std::regex re("\\\"" + key + "\\\"\\s*:\\s*(\\d+)");
    std::smatch match;
    if (std::regex_search(obj, match, re) && match.size() > 1)
    {
        return std::stoi(match[1].str());
    }
    return fallback;
}

int extractOptimalComponents(const std::string &response, int userId, int fallback)
{
    std::regex objRe(R"(\{[^{}]*\})");
    auto begin = std::sregex_iterator(response.begin(), response.end(), objRe);
    auto end = std::sregex_iterator();
    for (auto it = begin; it != end; ++it)
    {
        const std::string obj = it->str();
        int uid = findJsonIntField(obj, "user_id", -1);
        if (uid == userId)
        {
            return findJsonIntField(obj, "optimal_components", fallback);
        }
    }
    return fallback;
}

} // namespace

namespace simu5g
{

    Define_Module(XRTrafficSource);

    XRTrafficSource::~XRTrafficSource()
    {
        cancelAndDelete(sendTimer_);
    }

    void XRTrafficSource::initialize(int stage)
    {
        ApplicationBase::initialize(stage);

        if (stage == INITSTAGE_LOCAL)
        {
            // Initialize parameters
            fps_ = par("fps").doubleValue();
            jitter_mean_ = par("jitterMean").doubleValue();
            jitter_sd_ = par("jitterStd").doubleValue();
            jitter_min_ = par("jitterMin").doubleValue();
            jitter_max_ = par("jitterMax").doubleValue();
            seed_val_ = par("jitterSeed").intValue();
            startTime_ = par("startTime");

            localPort_ = par("localPort").intValue();
            destPort_ = par("destPort").intValue();
            destAddressStr_ = par("destAddress").stdstringValue();
            pcaFile_ = par("pcaFile").stdstringValue();
            compressionLevel_ = par("compressionLevel").intValue();
            selectionMode_ = par("selectionMode").stdstringValue();
            prescribedFile_ = par("prescribedFile").stdstringValue();
            modelServerUrl_ = par("modelServerUrl").stdstringValue();
            modelNumUsers_ = par("modelNumUsers").intValue();
            modelDefaultCqi_ = par("modelDefaultCqi").intValue();

            frameNumber_ = 0;
            sendTimer_ = new omnetpp::cMessage("sendTimer");

            // Register signals
            sentPktSignal_ = registerSignal("sentPkt");
            sentBytesSignal_ = registerSignal("sentBytes");

            // Initialize binder pointer to nullptr
            binder_ = nullptr;
            macNodeId_ = NODEID_NONE;
            gnbMac_ = nullptr;

            // Load PCA reconstruction data
            loadPCAData(pcaFile_);

            // Load prescribed schedule if in prescribed mode
            if (selectionMode_ == "prescribed" && !prescribedFile_.empty())
            {
                loadPrescribedData(prescribedFile_);
            }
            socket_.setOutputGate(gate("socketOut"));
            socket_.setCallback(this);
        }
        else if (stage == INITSTAGE_APPLICATION_LAYER)
        {
            // Resolve destination address
            destAddress_ = inet::L3AddressResolver().resolve(destAddressStr_.c_str());

            binder_ = resolveBinderModule(getSimulation());

            // For downlink: get DESTINATION UE's MAC ID, not source
            if (!destAddress_.isUnspecified() && destAddress_.getType() == inet::L3Address::IPv4)
            {
                macNodeId_ = binder_->getMacNodeId(destAddress_.toIpv4());
            }

            EV << "XRTrafficSource initialized with " << frames_.size()
               << " frames, FPS=" << fps_ << ", dest=" << destAddress_
               << ":" << destPort_ << ", macNodeId=" << macNodeId_
               << ", mode=" << selectionMode_ << endl;

            // Resolve gNB MAC module for buffer/utilization queries
            try {
                omnetpp::cModule *networkModule = getSimulation()->getSystemModule();
                omnetpp::cModule *gnbModule = networkModule->getSubmodule("gnb");
                if (gnbModule) {
                    omnetpp::cModule *cellularNic = gnbModule->getSubmodule("cellularNic");
                    if (cellularNic) {
                        // Try NR MAC first, then fall back to regular MAC
                        omnetpp::cModule *macModule = cellularNic->getSubmodule("nrMac");
                        if (!macModule) macModule = cellularNic->getSubmodule("mac");
                        if (macModule) {
                            gnbMac_ = dynamic_cast<LteMacEnb*>(macModule);
                        }
                    }
                }
            } catch (...) {
                EV_WARN << "Could not resolve gNB MAC module" << endl;
            }
            EV << "XRTrafficSource: gnbMac_=" << (gnbMac_ ? "resolved" : "null") << endl;

        }
    }

    void XRTrafficSource::handleStartOperation(inet::LifecycleOperation *operation)
    {
        // Bind socket when application is starting
        socket_.bind(localPort_);

        // Make sure destination address is resolved
        if (destAddress_.isUnspecified())
        {
            destAddress_ = inet::L3AddressResolver().resolve(destAddressStr_.c_str());
        }

        if (destAddress_.isUnspecified())
        {
            error("XRTrafficSource: Could not resolve destination address: %s", destAddressStr_.c_str());
            return;
        }

        if (binder_ != nullptr && destAddress_.getType() == inet::L3Address::IPv4)
        {
            macNodeId_ = binder_->getMacNodeId(destAddress_.toIpv4());
        }

        // In model mode, store video stats in Binder so all sources
        // can gather each other's features for batched model queries
        if (selectionMode_ == "model" && binder_ != nullptr && macNodeId_ != NODEID_NONE)
        {
            binder_->setXRVideoStats(macNodeId_, meanTrafficSize_, stdTrafficSize_, fps_);
            EV << "XRTrafficSource: Stored video stats in Binder for UE "
               << macNodeId_ << " (mean=" << meanTrafficSize_
               << ", std=" << stdTrafficSize_ << ", fps=" << fps_ << ")" << endl;
        }

        // Connect to the destination
        socket_.connect(destAddress_, destPort_);

        // Schedule first packet after socket is bound and application is started
        if (getFrameCount() > 0)
        {
            double jitter_ms = tran_gau_num(jitter_mean_, jitter_sd_, jitter_min_, jitter_max_);
            double sendDelay = (1.0 / fps_) + (jitter_ms / 1000.0);
            omnetpp::simtime_t firstSendTime = omnetpp::simTime() + startTime_ + sendDelay;
            scheduleAt(firstSendTime, sendTimer_);
            EV << "First packet scheduled at " << firstSendTime << endl;
        }
        else
        {
            EV_ERROR << "No frames loaded, cannot schedule transmission!" << endl;
        }
    }

    void XRTrafficSource::handleStopOperation(inet::LifecycleOperation *operation)
    {
        cancelEvent(sendTimer_);
        socket_.close();
    }

    void XRTrafficSource::handleCrashOperation(inet::LifecycleOperation *operation)
    {
        cancelEvent(sendTimer_);
        if (socket_.isOpen())
            socket_.destroy();
    }

    void XRTrafficSource::handleMessageWhenUp(omnetpp::cMessage *msg)
    {
        if (msg->isSelfMessage())
        {
            if (msg == sendTimer_)
            {
                sendPacket();
                scheduleNextPacket();
            }
        }
        else
        {
            // Process incoming socket messages
            socket_.processMessage(msg);
        }
    }

    bool XRTrafficSource::resolveFrameInfo(int frameIdx, FrameInfo &frameInfo)
    {
        if (selectionMode_ == "fixed")
        {
            if (frameIdx >= static_cast<int>(frames_.size()))
            {
                EV_ERROR << "No frame data for fixed mode at index " << frameIdx << endl;
                return false;
            }
            frameInfo = frames_[frameIdx];
            return true;
        }

        if (frameIdx >= static_cast<int>(frameNumbers_.size()))
        {
            EV_ERROR << "No frame data at index " << frameIdx << endl;
            return false;
        }

        if (availableComponents_.empty())
        {
            EV_ERROR << "No compression levels loaded for selection" << endl;
            return false;
        }

        int frameNum = frameNumbers_[frameIdx];
        int chosenComponents = 0;

        if (selectionMode_ == "random")
        {
            int compIdx = omnetpp::intuniform(0, static_cast<int>(availableComponents_.size()) - 1);
            chosenComponents = availableComponents_[compIdx];
        }
        else if (selectionMode_ == "prescribed")
        {
            auto prescIt = prescribedComponents_.find(frameNum);
            if (prescIt != prescribedComponents_.end())
            {
                chosenComponents = prescIt->second;
            }
            else
            {
                chosenComponents = availableComponents_[availableComponents_.size() / 2];
                EV_WARN << "No prescribed level for frame " << frameNum
                        << ", using fallback=" << chosenComponents << endl;
            }
        }
        else if (selectionMode_ == "model")
        {
            chosenComponents = queryModelServer(frameNum);
        }
        else
        {
            EV_ERROR << "Unknown selection mode: " << selectionMode_ << endl;
            return false;
        }

        auto frameIt = allFrameData_.find(frameNum);
        if (frameIt == allFrameData_.end())
        {
            EV_ERROR << "No PCA data for frame " << frameNum << endl;
            return false;
        }

        auto compIt = frameIt->second.find(chosenComponents);
        if (compIt != frameIt->second.end())
        {
            frameInfo = compIt->second;
            return true;
        }

        if (selectionMode_ == "model")
        {
            int closest = availableComponents_[0];
            int minDist = std::abs(chosenComponents - closest);
            for (int c : availableComponents_)
            {
                int dist = std::abs(chosenComponents - c);
                if (dist < minDist) { minDist = dist; closest = c; }
            }
            auto closestIt = frameIt->second.find(closest);
            if (closestIt != frameIt->second.end())
            {
                frameInfo = closestIt->second;
                EV_WARN << "Model suggested components=" << chosenComponents
                        << " not in data, using closest=" << closest << endl;
                return true;
            }
        }

        EV_ERROR << "No PCA data for frame " << frameNum
                 << " at components=" << chosenComponents << endl;
        return false;
    }

    void XRTrafficSource::sendPacket()
    {
        int totalFrames = getFrameCount();
        if (frameNumber_ >= totalFrames)
        {
            EV << "All frames sent, stopping transmission" << endl;
            return;
        }

        FrameInfo frameInfo;
        if (!resolveFrameInfo(frameNumber_, frameInfo))
        {
            frameNumber_++;
            return;
        }

        // Update binder with XR metrics for this frame
        if (frameInfo.frameNumber_ != lastFrameUpdated_)
        {
            if (binder_ != nullptr && macNodeId_ != NODEID_NONE)
            {
                binder_->setXRMetrics(macNodeId_, frameInfo.frameNumber_, frameInfo.mse, frameInfo.size_bytes);
                lastFrameUpdated_ = frameInfo.frameNumber_;
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
                std::snprintf(msgName, sizeof(msgName), "XRFrame-F%d-C%d-Frag%d",
                    frameInfo.frameNumber_, frameInfo.components, fragIndex);
                inet::Packet *packet = new inet::Packet(msgName);

            // Create and populate XR header
            auto header = inet::makeShared<XRHeader>();
            header->setFrameNumber(frameInfo.frameNumber_);
            header->setPcaComponents(frameInfo.components);
            header->setMse(frameInfo.mse);
            header->setSizeBytes(frameInfo.size_bytes);
            header->setGenTime(omnetpp::simTime().dbl());
            header->setFragIndex(fragIndex);
            header->setTotalFragments(totalFragments);
            header->setChunkLength(inet::B(32)); // Fixed header size

            // Add header to packet
            packet->insertAtFront(header);

            // Add payload data
            const auto &payload = inet::makeShared<inet::ByteCountChunk>(inet::B(fragSize));
            packet->insertAtBack(payload);

            // Add timestamp tag
            auto creationTimeTag = packet->addTag<inet::CreationTimeTag>();
            creationTimeTag->setCreationTime(omnetpp::simTime());

            // Check if socket is open before sending
            if (!socket_.isOpen())
            {
                EV_ERROR << "Socket not open, cannot send packet" << endl;
                delete packet;
                return;
            }

            // Send via UDP socket (INET takes ownership of the packet)
            socket_.send(packet);

            // Update statistics (only once per frame)
            if (fragIndex == 0)
            {
                emit(sentPktSignal_, 1);
                emit(sentBytesSignal_, (long)frameInfo.size_bytes);
            }
        }

        EV << "Sent frame " << frameInfo.frameNumber_
           << ": components=" << frameInfo.components
           << ", size=" << frameInfo.size_bytes << " bytes"
           << ", MSE=" << frameInfo.mse
           << ", fragments=" << totalFragments
           << ", mode=" << selectionMode_ << endl;

        frameNumber_++;
    }

    void XRTrafficSource::scheduleNextPacket()
    {
        if (frameNumber_ >= getFrameCount())
        {
            return;
        }

        // Calculate next send time with jitter
        double jitter_ms = tran_gau_num(jitter_mean_, jitter_sd_, jitter_min_, jitter_max_);
        double intervalWithJitter = (1.0 / fps_) + (jitter_ms / 1000.0);

        scheduleAt(omnetpp::simTime() + intervalWithJitter, sendTimer_);
    }

    double XRTrafficSource::tran_gau_num(double mean, double sd, double minv, double maxv)
    {
        // Truncated Gaussian using OMNeT++ normal() function
        double x = omnetpp::normal(mean, sd, seed_val_);
        int attempts = 0;

        while ((x < minv || x > maxv) && attempts < 1000)
        {
            x = omnetpp::normal(mean, sd, seed_val_);
            attempts++;
        }

        // Clamp to valid range if necessary
        if (x < minv)
            x = minv;
        if (x > maxv)
            x = maxv;

        return x;
    }

    void XRTrafficSource::loadPCAData(const std::string &pcaFile)
    {
        frames_.clear();
        allFrameData_.clear();
        frameNumbers_.clear();
        availableComponents_.clear();
        frameComplexity_.clear();
        frameErrorVector_.clear();
        meanTrafficSize_ = 0.0;
        stdTrafficSize_ = 0.0;

        parseCSV(pcaFile);
        buildErrorVectors();
        computeVideoStats();
    }

    void XRTrafficSource::parseCSV(const std::string &pcaFile)
    {
        std::ifstream f(pcaFile);
        if (!f.is_open())
        {
            EV_ERROR << "Cannot open PCA data file: " << pcaFile << endl;
            error("Failed to open PCA reconstruction file");
            return;
        }

        std::string line;
        if (!std::getline(f, line))
        {
            EV_ERROR << "Empty PCA file: " << pcaFile << endl;
            return;
        }

        int lineNum = 1;
        std::set<int> uniqueFrames;
        std::set<int> uniqueComponents;

        while (std::getline(f, line))
        {
            lineNum++;
            if (line.empty())
                continue;

            std::stringstream ss(line);
            std::string field;
            std::vector<std::string> fields;

            while (std::getline(ss, field, ','))
            {
                field.erase(std::remove_if(field.begin(), field.end(), ::isspace), field.end());
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
                fi.frameNumber_ = std::stoi(fields[0]);
                fi.components = std::stoi(fields[1]);
                fi.mse = std::stod(fields[2]);
                fi.size_bytes = std::stoi(fields[3]);

                if (fields.size() >= 5)
                {
                    double fc_or_at80 = std::stod(fields[4]);
                    if (frameComplexity_.find(fi.frameNumber_) == frameComplexity_.end())
                    {
                        frameComplexity_[fi.frameNumber_] = fc_or_at80;
                    }
                }

                allFrameData_[fi.frameNumber_][fi.components] = fi;

                uniqueFrames.insert(fi.frameNumber_);
                if (fi.components != UNCOMPRESSED_COMPONENTS && fi.components != 0)
                {
                    uniqueComponents.insert(fi.components);
                }

                if (selectionMode_ == "fixed")
                {
                    if (compressionLevel_ == 0 || fi.components == compressionLevel_)
                    {
                        frames_.push_back(fi);
                    }
                }
            }
            catch (const std::exception &e)
            {
                EV_WARN << "Error parsing line " << lineNum << " in " << pcaFile
                        << ": " << e.what() << endl;
            }
        }

        f.close();

        frameNumbers_.assign(uniqueFrames.begin(), uniqueFrames.end());
        availableComponents_.assign(uniqueComponents.begin(), uniqueComponents.end());

        int totalLoaded = (selectionMode_ == "random") ? static_cast<int>(frameNumbers_.size())
                                                        : static_cast<int>(frames_.size());

        EV << "Loaded PCA data from " << pcaFile
           << ": " << uniqueFrames.size() << " unique frames"
           << ", " << availableComponents_.size() << " compression levels"
           << ", selectionMode=" << selectionMode_
           << ", effective frame count=" << totalLoaded << endl;

        if (selectionMode_ == "random")
        {
            EV << "  Available components: ";
            for (int c : availableComponents_) EV << c << " ";
            EV << endl;
        }

        if (!frames_.empty() || !frameNumbers_.empty())
        {
            double avgMSE = 0.0;
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
    }

    void XRTrafficSource::buildErrorVectors()
    {
        for (const auto &framePair : allFrameData_)
        {
            int fn = framePair.first;
            std::vector<double> errVec(NUM_CL_LEVELS, 0.0);
            for (int k = 0; k < NUM_CL_LEVELS; k++)
            {
                int cl = (k + 1) * CL_STEP;
                auto compIt = framePair.second.find(cl);
                if (compIt != framePair.second.end())
                {
                    errVec[k] = compIt->second.mse;
                }
            }
            frameErrorVector_[fn] = errVec;
        }
        EV << "  Built error vectors for " << frameErrorVector_.size()
           << " frames (" << NUM_CL_LEVELS << " CLs each)" << endl;
    }

    void XRTrafficSource::computeVideoStats()
    {
        if (frameComplexity_.empty())
        {
            return;
        }

        double sumFC = 0.0;
        for (const auto &p : frameComplexity_) sumFC += p.second;
        meanTrafficSize_ = sumFC / frameComplexity_.size();

        double sumSqDiff = 0.0;
        for (const auto &p : frameComplexity_)
        {
            double diff = p.second - meanTrafficSize_;
            sumSqDiff += diff * diff;
        }
        stdTrafficSize_ = std::sqrt(sumSqDiff / frameComplexity_.size());

        EV << "  Video stats: meanTrafficSize=" << meanTrafficSize_
           << ", stdTrafficSize=" << stdTrafficSize_
           << ", frames with complexity=" << frameComplexity_.size() << endl;
    }

    void XRTrafficSource::loadPrescribedData(const std::string &prescribedFile)
    {
        std::ifstream f(prescribedFile);
        if (!f.is_open())
        {
            EV_ERROR << "Cannot open prescribed file: " << prescribedFile << endl;
            error("Failed to open prescribed compression schedule file");
            return;
        }

        std::string line;
        // Skip header line (frame,components)
        if (!std::getline(f, line))
        {
            EV_ERROR << "Empty prescribed file: " << prescribedFile << endl;
            return;
        }

        int loaded = 0;
        while (std::getline(f, line))
        {
            if (line.empty())
                continue;

            std::stringstream ss(line);
            std::string field;
            std::vector<std::string> fields;

            while (std::getline(ss, field, ','))
            {
                field.erase(std::remove_if(field.begin(), field.end(), ::isspace), field.end());
                fields.push_back(field);
            }

            if (fields.size() < 2)
                continue;

            try
            {
                int frameNum = std::stoi(fields[0]);
                int components = std::stoi(fields[1]);
                prescribedComponents_[frameNum] = components;
                loaded++;
            }
            catch (const std::exception &e)
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
            return (int)frames_.size();
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
        EV << "XRTrafficSource finished. Sent " << frameNumber_ << " frames_." << endl;
    }

    // UdpSocket::ICallback implementations
    void XRTrafficSource::socketDataArrived(inet::UdpSocket *socket, inet::Packet *packet)
    {
        // This is a traffic source, we don't expect to receive data
        EV_WARN << "Received unexpected packet: " << packet->getName() << endl;
        delete packet;
    }

    void XRTrafficSource::socketErrorArrived(inet::UdpSocket *socket, inet::Indication *indication)
    {
        EV_WARN << "Socket error occurred" << endl;
        delete indication;
    }

    void XRTrafficSource::socketClosed(inet::UdpSocket *socket)
    {
        EV << "Socket closed" << endl;
    }

    std::string XRTrafficSource::httpPost(const std::string& url, const std::string& jsonPayload)
    {
        TempFile tmpFile("xr_model_payload");
        if (!tmpFile.valid())
        {
            EV_ERROR << "httpPost: failed to create temp file" << endl;
            return "";
        }

        {
            std::ofstream ofs(tmpFile.path());
            if (!ofs.is_open())
            {
                EV_ERROR << "httpPost: failed to open temp file" << endl;
                return "";
            }
            ofs << jsonPayload;
        }

        std::string command = "wget -qO- --header='Content-Type: application/json' "
                              "--post-file='" + tmpFile.path() + "' '" + url + "' 2>/dev/null";

        FILE *pipe = ::popen(command.c_str(), "r");
        if (!pipe)
        {
            EV_ERROR << "httpPost: popen failed for " << url << endl;
            return "";
        }

        std::string result;
        char buffer[4096];
        while (::fgets(buffer, sizeof(buffer), pipe) != nullptr)
        {
            result += buffer;
        }
        int status = ::pclose(pipe);

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

        int fallbackComponents = availableComponents_[availableComponents_.size() / 2];
        int chosenComponents = extractOptimalComponents(response, myIndex, fallbackComponents);
        if (chosenComponents == fallbackComponents)
        {
            EV_WARN << "queryModelServer: Using fallback components=" << fallbackComponents
                    << " for user_id=" << myIndex << endl;
        }

        EV << "queryModelServer: frame=" << frameNum
           << " myIndex=" << myIndex
           << " cqi=" << binder_->getXRCqi(macNodeId_)
           << " → components=" << chosenComponents << endl;

        return chosenComponents;
    }

} // namespace simu5g