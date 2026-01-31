#include "XRTrafficSource.h"
#include "inet/common/ModuleAccess.h"
#include "inet/common/packet/Packet.h"
#include "inet/common/TimeTag_m.h"
#include "inet/networklayer/common/L3AddressTag_m.h"
#include "inet/transportlayer/common/L4PortTag_m.h"
#include "inet/common/lifecycle/NodeStatus.h"
#include "inet/common/packet/chunk/ByteCountChunk.h"
#include "apps/xr/XRHeader_m.h"
#include "common/binder/Binder.h"

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

            frame_number = 0;
            sendTimer = new cMessage("sendTimer");


            // Initialize binder pointer to nullptr
            binder_ = nullptr;
            macNodeId_ = NODEID_NONE;

            // Load PCA reconstruction data
            loadPCAData(pcaFile);
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
               << ":" << destPort << ", macNodeId=" << macNodeId_ << endl;
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

        // Connect to the destination
        socket.connect(destAddress, destPort);

        // Schedule first packet after socket is bound and application is started
        if (!frames.empty())
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
        if (frame_number >= (int)frames.size())
        {
            EV << "All frames sent, stopping transmission" << endl;
            return;
        }

        // Get current frame info
        FrameInfo &frameInfo = frames[frame_number];

        // Update binder with XR metrics for this frame
        // static int lastFrameUpdated = -1;
        if (frameInfo.frame_number != lastFrameUpdated)
        {
            if (binder_ != nullptr && macNodeId_ != NODEID_NONE)
            {
                binder_->setXRMetrics(macNodeId_, frameInfo.frame_number, frameInfo.mse, frameInfo.size_bytes);
                lastFrameUpdated = frameInfo.frame_number;
            }
        }
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


        }

        EV << "Sent frame " << frameInfo.frame_number
           << ": components=" << frameInfo.components
           << ", size=" << frameInfo.size_bytes << " bytes"
           << ", MSE=" << frameInfo.mse
           << ", fragments=" << totalFragments << endl;

        frame_number++;
    }

    void XRTrafficSource::scheduleNextPacket()
    {
        if (frame_number >= (int)frames.size())
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

            if (fields.size() != 4)
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
                
                // Filter by compression level if specified
                if (compressionLevel_ == 0 || fi.components == compressionLevel_)
                {
                    frames.push_back(fi);
                }
            }
            catch (const exception &e)
            {
                EV_WARN << "Error parsing line " << lineNum << " in " << pcaFile
                        << ": " << e.what() << endl;
            }
        }

        f.close();

        EV << "Loaded " << frames.size() << " frames from PCA reconstruction file "
           << pcaFile << endl;

        if (!frames.empty())
        {
            // Calculate summary statistics
            int minSize = frames[0].size_bytes;
            int maxSize = frames[0].size_bytes;
            double avgMSE = 0;

            for (const auto &frame : frames)
            {
                minSize = min(minSize, frame.size_bytes);
                maxSize = max(maxSize, frame.size_bytes);
                avgMSE += frame.mse;
            }
            avgMSE /= frames.size();

            EV << "  Frame size range: " << minSize << " - " << maxSize << " bytes" << endl;
            EV << "  Average MSE: " << avgMSE << endl;
        }
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

} // namespace simu5g