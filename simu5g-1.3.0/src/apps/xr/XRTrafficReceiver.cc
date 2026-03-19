#include "XRTrafficReceiver.h"
#include "apps/xr/XRHeader_m.h"
#include "inet/common/ModuleAccess.h"
#include "inet/common/packet/Packet.h"
#include "inet/common/TimeTag_m.h"
#include "inet/networklayer/common/L3AddressTag_m.h"
#include "inet/transportlayer/common/L4PortTag_m.h"
#include "inet/common/lifecycle/NodeStatus.h"
#include "inet/networklayer/common/L3AddressResolver.h"
#include "stack/phy/LtePhyUe.h"
#include "common/binder/Binder.h"
#include <algorithm>
#include <fstream>
#include <iomanip>
#include <numeric>
#include <sstream>
#include <unistd.h>
#include <limits.h>

namespace simu5g
{

    // Static variable definitions
    double XRTrafficReceiver::totalSumError = 0.0;
    int XRTrafficReceiver::totalExpectedFrames = 0;
    int XRTrafficReceiver::totalOnTimeFrames = 0;
    int XRTrafficReceiver::totalSatisfiedUsers = 0;
    int XRTrafficReceiver::userCount = 0;
    bool XRTrafficReceiver::globalStatsPrinted = false;
    int XRTrafficReceiver::finishedCount = 0;
    std::ofstream XRTrafficReceiver::globalResultFile;

    Define_Module(XRTrafficReceiver);

    XRTrafficReceiver::XRTrafficReceiver()
        : expectedTotalFrames(100), nextExpectedFrame(1), trackingStarted(false), qoeComputed(false),
          elostValue(1000.0), autoElost(true), avgCqi_(0.0), phyUe_(nullptr),
          binder_(nullptr), macNodeId_(NODEID_NONE)
    {
    }

    XRTrafficReceiver::~XRTrafficReceiver()
    {
        if (resultFile.is_open())
            resultFile.close();
    }

    void XRTrafficReceiver::initialize(int stage)
    {
        ApplicationBase::initialize(stage);

        if (stage == INITSTAGE_LOCAL)
        {
            localPort = par("localPort").intValue();
            deadlineMs = par("deadlineMs").doubleValue();
            reliabilityThreshold = par("reliabilityThreshold").doubleValue();
            expectedTotalFrames = par("expectedFrames").intValue();

            // Read Elost parameters
            autoElost = par("autoElost").boolValue();
            if (autoElost)
            {
                std::string pcaFile = par("pcaFile").stdstringValue();
                int minComponents = par("minComponents").intValue();
                elostValue = getMaxMSE(pcaFile, minComponents);
                std::cout << "XRTrafficReceiver: autoElost=true, computed Elost="
                          << elostValue << " from max MSE at components="
                          << minComponents << endl;
            }
            else
            {
                elostValue = par("elostValue").doubleValue();
                std::cout << "XRTrafficReceiver: autoElost=false, manual Elost="
                          << elostValue << endl;
            }

            nextExpectedFrame = 1;
            trackingStarted = false;
            userCount++;



            resultFilename = par("resultFile").stdstringValue();
            if (!resultFilename.empty())
            {
                resultFile.open(resultFilename);
                if (resultFile.is_open())
                {
                    resultFile << "frameNumber,components,mse,sizeBytes,genTime,recvTime,"
                               << "delay_ms,receivedOnTime,effectiveError,deadline_ms,cqi" << endl;
                }
            }

            std::cout << "XRTrafficReceiver: Initialized with deadline=" << deadlineMs
                      << "ms, expected frames=" << expectedTotalFrames
                      << ", Elost=" << elostValue << endl;
        }
        else if (stage == INITSTAGE_APPLICATION_LAYER)
        {
            // Resolve Binder and own MacNodeId for CQI feedback
            binder_ = dynamic_cast<Binder *>(
                getSimulation()->getModuleByPath("binder"));
            if (binder_ == nullptr)
            {
                // Fallback: search for Binder type
                cModule *networkModule = getSimulation()->getSystemModule();
                for (cModule::SubmoduleIterator it(networkModule); !it.end(); ++it)
                {
                    Binder *b = dynamic_cast<Binder *>(*it);
                    if (b != nullptr) { binder_ = b; break; }
                }
            }

            // Resolve own MacNodeId from this UE's IP address
            if (binder_ != nullptr)
            {
                cModule *ueModule = getParentModule();
                inet::L3AddressResolver resolver;
                inet::L3Address addr = resolver.addressOf(ueModule);
                if (!addr.isUnspecified() && addr.getType() == inet::L3Address::IPv4)
                {
                    macNodeId_ = binder_->getMacNodeId(addr.toIpv4());
                }
            }

            std::cout << "XRTrafficReceiver: Binder=" << (binder_ ? "resolved" : "null")
                      << ", macNodeId=" << macNodeId_ << endl;
        }
    }

    void XRTrafficReceiver::handleStartOperation(LifecycleOperation *operation)
    {
        socket.setOutputGate(gate("socketOut"));
        socket.setCallback(this);
        socket.bind(localPort);

        // Resolve PHY pointer early so we can query per-frame CQI
        try {
            cModule *ue = getParentModule();
            if (ue != nullptr) {
                cModule *cellularNic = ue->getSubmodule("cellularNic");
                if (cellularNic != nullptr) {
                    cModule *phyModule = cellularNic->getSubmodule("nrPhy");
                    if (phyModule == nullptr) {
                        phyModule = cellularNic->getSubmodule("phy");
                    }
                    if (phyModule != nullptr) {
                        phyUe_ = dynamic_cast<LtePhyUe*>(phyModule);
                    }
                }
            }
        } catch (...) {
            EV_WARN << "Could not resolve PHY module for per-frame CQI" << endl;
        }

        std::cout << "XRTrafficReceiver: Socket bound to port " << localPort
                  << ", phyUe_=" << (phyUe_ ? "resolved" : "null") << endl;
    }

    void XRTrafficReceiver::handleStopOperation(LifecycleOperation *operation)
    {
        socket.close();
        detectLostFrames();
        computeAndRecordQoE();
    }

    void XRTrafficReceiver::handleCrashOperation(LifecycleOperation *operation)
    {
        if (socket.isOpen())
            socket.destroy();
    }

    void XRTrafficReceiver::handleMessageWhenUp(cMessage *msg)
    {
        socket.processMessage(msg);
    }

    void XRTrafficReceiver::socketDataArrived(UdpSocket *socket, Packet *packet)
    {
        std::cout << "XRTrafficReceiver: Packet arrived from "
                  << packet->getTag<L3AddressInd>()->getSrcAddress()
                  << ", name: " << packet->getName() << endl;

        std::cout << "Packet details: " << packet->str() << endl;

        processFrame(packet);
    }

    void XRTrafficReceiver::processFrame(Packet *packet)
    {
        auto header = packet->popAtFront<XRHeader>();
        if (header == nullptr)
        {
            EV_WARN << "Received packet without XRHeader, skipping" << endl;
            delete packet;
            return;
        }

        int frameNumber = header->getFrameNumber();
        int components = header->getPcaComponents();
        double mse = header->getMse();
        int sizeBytes = header->getSizeBytes();
        double genTime = header->getGenTime();
        int fragIndex = header->getFragIndex();
        int totalFragments = header->getTotalFragments();

        std::cout << "Extracted header: Frame=" << frameNumber
                  << ", Components=" << components
                  << ", FragIndex=" << fragIndex << "/" << totalFragments << endl;

        simtime_t recvTime = simTime();

        if (!trackingStarted)
        {
            trackingStarted = true;
            firstFrameTime = recvTime;
            std::cout << "XRTrafficReceiver: Started tracking at t=" << recvTime << endl;
        }

        if (receivedFrames.find(frameNumber) == receivedFrames.end())
        {
            ReceivedFrameStats stats;
            stats.frameNumber = frameNumber;
            stats.pcaComponents = components;
            stats.mse = mse;
            stats.sizeBytes = sizeBytes;
            stats.genTime = genTime;
            stats.recvTime = recvTime;
            stats.delay = -1; // mark as incomplete until all fragments arrive
            stats.receivedOnTime = false;
            stats.effectiveError = elostValue; // penalty for frames that never complete
            stats.fragmentsReceived = 1;
            stats.totalFragments = totalFragments;
            stats.cqi = 0; // will be set when frame completes

            receivedFrames[frameNumber] = stats;

            std::cout << "Received first fragment " << fragIndex << "/" << totalFragments
                      << " of frame " << frameNumber << endl;
        }
        else
        {
            receivedFrames[frameNumber].fragmentsReceived++;

            std::cout << "Received fragment " << fragIndex << "/" << totalFragments
                      << " of frame " << frameNumber << " (total: "
                      << receivedFrames[frameNumber].fragmentsReceived << ")" << endl;
        }

        if (receivedFrames[frameNumber].fragmentsReceived == totalFragments)
        {
            double delay = (recvTime.dbl() - genTime) * 1000.0;
            receivedFrames[frameNumber].delay = delay;
            
            // Push delay to Binder for real-time feedback to the source
            if (binder_ != nullptr && macNodeId_ != NODEID_NONE)
            {
                binder_->setXRVideoPrevDelayMs(macNodeId_, delay);
            }

            bool onTime = (delay <= deadlineMs);
            receivedFrames[frameNumber].receivedOnTime = onTime;

            // Query instantaneous DL CQI from UE PHY layer
            unsigned int frameCqi = 0;
            if (phyUe_ != nullptr) {
                frameCqi = phyUe_->getLastCqi(DL);
            }
            receivedFrames[frameNumber].cqi = frameCqi;

            double effectiveError;
            if (onTime)
            {
                effectiveError = mse;
            }
            else
            {
                // Penalty = max MSE at most aggressive compression level
                effectiveError = elostValue;
            }
            receivedFrames[frameNumber].effectiveError = effectiveError;



            if (resultFile.is_open())
            {
                resultFile << frameNumber << "," << components << "," << mse << ","
                           << sizeBytes << "," << fixed << setprecision(9) << genTime << ","
                           << recvTime.dbl() << "," << setprecision(6) << delay << ","
                           << (onTime ? 1 : 0) << "," << effectiveError << ","
                           << deadlineMs << "," << frameCqi << endl;
            }

            std::cout << "Frame " << frameNumber << " COMPLETE: delay=" << delay
                      << "ms, onTime=" << onTime << ", MSE=" << mse
                      << ", error=" << effectiveError
                      << ", cqi=" << frameCqi << endl;

            // Push CQI to Binder for real-time feedback to the source
            if (binder_ != nullptr && macNodeId_ != NODEID_NONE)
            {
                binder_->setXRCqi(macNodeId_, frameCqi);
            }
        }

        delete packet;
    }

    void XRTrafficReceiver::detectLostFrames()
    {
        std::cout << "XRTrafficReceiver: Detecting lost frames..." << endl;

        int lostCount = 0;
        for (int i = 1; i <= expectedTotalFrames; i++)
        {
            if (receivedFrames.find(i) == receivedFrames.end())
            {
                ReceivedFrameStats lostStats;
                lostStats.frameNumber = i;
                lostStats.pcaComponents = 0;
                lostStats.mse = 0;
                lostStats.sizeBytes = 0;
                lostStats.genTime = 0;
                lostStats.recvTime = 0;
                lostStats.delay = -1;
                lostStats.receivedOnTime = false;
                lostStats.effectiveError = elostValue;
                lostStats.cqi = 0;

                receivedFrames[i] = lostStats;
                lostCount++;

                if (resultFile.is_open())
                {
                    resultFile << i << ",0,0,0,0,0,-1,0," << elostValue << ","
                               << deadlineMs << ",0" << endl;
                }
            }
        }

        std::cout << "Total lost frames: " << lostCount << " out of " << expectedTotalFrames << endl;
    }

    void XRTrafficReceiver::computeAndRecordQoE()
    {
        if (receivedFrames.empty())
        {
            EV_WARN << "No frames received, cannot compute QoE metrics" << endl;
            return;
        }

        int totalFrames = expectedTotalFrames;
        int receivedCount = 0;
        int onTimeCount = 0;
        int lateCount = 0;
        int lostCount = 0;

        double sumError = 0.0;
        double sumDelay = 0.0;

        vector<double> allErrors;
        vector<double> delays;

        for (int i = 1; i <= expectedTotalFrames; i++)
        {
            const auto &stats = receivedFrames[i];

            allErrors.push_back(stats.effectiveError);
            sumError += stats.effectiveError;

            if (stats.delay >= 0)
            {
                receivedCount++;
                delays.push_back(stats.delay);
                sumDelay += stats.delay;

                if (stats.receivedOnTime)
                {
                    onTimeCount++;
                }
                else
                {
                    lateCount++;
                }
            }
            else
            {
                lostCount++;
            }
        }

        double meanError = (totalFrames > 0) ? sumError / totalFrames : 0.0;

        double deliveryRatio = (double)receivedCount / totalFrames;
        double onTimeRatio = (double)onTimeCount / totalFrames;
        double lossRatio = (double)lostCount / totalFrames;
        double avgDelay = (receivedCount > 0) ? sumDelay / receivedCount : 0;

        if (!qoeComputed)
        {
            totalSumError += sumError;
            totalExpectedFrames += totalFrames;
            totalOnTimeFrames += onTimeCount;
            qoeComputed = true;
        }



        // Calculate delay reliability and user satisfaction
        double delayReliability = onTimeRatio;  // Percentage of frames delivered on-time
        bool userSatisfied = (delayReliability >= reliabilityThreshold);  // 99% threshold
        


        // Update global satisfied user count
        if (userSatisfied) {
            totalSatisfiedUsers++;
        }

        // Write unique summary file for this user
        if (!resultFilename.empty()) {
            std::string summaryFilename = resultFilename + ".summary";
            std::ofstream summaryFile(summaryFilename);
            if (summaryFile.is_open()) {
                // Header
                summaryFile << "user_id,avg_cqi,total_frames,received_frames,on_time_frames,"
                            << "late_frames,lost_frames,delivery_ratio,on_time_ratio,loss_ratio,"
                            << "mean_error,avg_delay_ms,deadline_ms,delay_reliability,"
                            << "reliability_threshold,user_satisfied" << endl;
                
                // Values
                summaryFile << getParentModule()->getIndex() << "," // user_id
                            << avgCqi_ << ","
                            << totalFrames << ","
                            << receivedCount << ","
                            << onTimeCount << ","
                            << lateCount << ","
                            << lostCount << ","
                            << deliveryRatio << ","
                            << onTimeRatio << ","
                            << lossRatio << ","
                            << meanError << ","
                            << avgDelay << ","
                            << deadlineMs << ","
                            << delayReliability << ","
                            << reliabilityThreshold << ","
                            << (userSatisfied ? 1 : 0) << endl;
                
                summaryFile.close();
            }
        }
        
        // recordScalar calls removed as requested
        /*
        recordScalar("totalFrames", totalFrames);
        recordScalar("receivedFrames", receivedCount);
        ...
        */
    }

    void XRTrafficReceiver::finish()
    {
        ApplicationBase::finish();

        // Get average CQI from PHY layer (phyUe_ already resolved in handleStartOperation)
        avgCqi_ = 0.0;
        if (phyUe_ != nullptr) {
            avgCqi_ = phyUe_->getAverageCqi(DL);
        }

        detectLostFrames();
        computeAndRecordQoE();

        if (resultFile.is_open())
        {
            resultFile.close();
        }

        // Global stats aggregation
        if (finishedCount == userCount && !globalStatsPrinted)
        {
            double globalAvgMeanError = (totalExpectedFrames > 0) ? totalSumError / totalExpectedFrames : 0.0;
            double globalDelayReliability = (totalExpectedFrames > 0) ? (double)totalOnTimeFrames / totalExpectedFrames : 0.0;

            globalResultFile.open("global_qoe.csv", std::ios::out);
            if (globalResultFile.is_open())
            {
                globalResultFile << "num_users,satisfied_users,global_avg_mean_error,global_delay_reliability,total_frames,total_ontime_frames" << std::endl;
                globalResultFile << userCount << "," << totalSatisfiedUsers << "," << globalAvgMeanError << "," 
                               << globalDelayReliability << "," << totalExpectedFrames << "," << totalOnTimeFrames << std::endl;
                globalResultFile.close();
            }

            // Optional: Print global stats to stdout if desired, otherwise comment out
            /*
            std::cout << "\n========== Global XR Traffic QoE Summary ==========" << endl;
            ...
            */
            globalStatsPrinted = true;
        }
    }

    void XRTrafficReceiver::socketErrorArrived(UdpSocket *socket, Indication *indication)
    {
        EV_WARN << "Socket error occurred" << endl;
        delete indication;
    }

    void XRTrafficReceiver::socketClosed(UdpSocket *socket)
    {
        std::cout << "Socket closed" << endl;
    }

    double XRTrafficReceiver::getMaxMSE(const std::string &pcaFile, int minComponents)
    {
        // Get absolute path for debugging
        char cwd[PATH_MAX];
        if (getcwd(cwd, sizeof(cwd)) != NULL) {
            std::cout << "XRTrafficReceiver: Current working directory: " << cwd << endl;
        } else {
            EV_WARN << "XRTrafficReceiver: getcwd() error" << endl;
        }

        if (pcaFile.empty())
        {
            EV_WARN << "No pcaFile specified for autoElost, using default 1000.0" << endl;
            return 1000.0;
        }

        std::cout << "XRTrafficReceiver: Opening PCA file: " << pcaFile << endl;
        std::ifstream f(pcaFile);
        if (!f.is_open())
        {
            EV_WARN << "Cannot open PCA file: " << pcaFile
                    << ", using default 1000.0" << endl;
            return 1000.0;
        }

        std::string line;
        // Skip header
        if (std::getline(f, line)) {
             std::cout << "XRTrafficReceiver: Header line: " << line << endl;
        } else {
             EV_WARN << "XRTrafficReceiver: Empty PCA file!" << endl;
             f.close();
             return 1000.0;
        }

        // First pass: collect all unique non-zero component values and track max MSE
        // for the requested minComponents level
        double maxMSE = 0.0;
        int count = 0;
        int smallestNonZero = INT_MAX;  // track smallest component level in file
        double maxMSESmallest = 0.0;   // max MSE at that smallest level
        int countSmallest = 0;

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

            if (fields.size() < 3)
                continue;

            try
            {
                int components = std::stoi(fields[1]);
                double mse = std::stod(fields[2]);

                // Track the smallest non-zero component level in the file
                if (components > 0 && components < smallestNonZero)
                {
                    smallestNonZero = components;
                    maxMSESmallest = mse;
                    countSmallest = 1;
                }
                else if (components == smallestNonZero)
                {
                    if (mse > maxMSESmallest)
                        maxMSESmallest = mse;
                    countSmallest++;
                }

                if (components == minComponents)
                {
                    if (mse > maxMSE)
                        maxMSE = mse;
                    count++;
                }
            }
            catch (const std::exception &e)
            {
                continue;
            }
        }

        f.close();

        // If exact minComponents found, use it
        if (count > 0)
        {
            std::cout << "XRTrafficReceiver::getMaxMSE: Found " << count
                      << " rows at components=" << minComponents
                      << ", maxMSE=" << maxMSE << endl;
            return maxMSE;
        }

        // Fallback: use the smallest non-zero component level found in file
        if (countSmallest > 0)
        {
            std::cout << "XRTrafficReceiver::getMaxMSE: minComponents=" << minComponents
                      << " not found. Falling back to smallest level components="
                      << smallestNonZero << " (" << countSmallest
                      << " rows, maxMSE=" << maxMSESmallest << ")" << endl;
            return maxMSESmallest;
        }

        EV_WARN << "No valid component rows found in " << pcaFile
                << ", using default 1000.0" << endl;
        return 1000.0;
    }

} // namespace simu5g