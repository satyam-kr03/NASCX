#include "XRTrafficReceiver.h"
#include "apps/xr/XRHeader_m.h"
#include "inet/common/ModuleAccess.h"
#include "inet/common/packet/Packet.h"
#include "inet/common/TimeTag_m.h"
#include "inet/networklayer/common/L3AddressTag_m.h"
#include "inet/transportlayer/common/L4PortTag_m.h"
#include "inet/common/lifecycle/NodeStatus.h"
#include "stack/phy/LtePhyUe.h"
#include <algorithm>
#include <fstream>
#include <iomanip>
#include <numeric>

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
          avgCqi_(0.0), phyUe_(nullptr)
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

            nextExpectedFrame = 1;
            trackingStarted = false;
            userCount++;

            rcvdPktSignal = registerSignal("rcvdPkt");
            rcvdBytesSignal = registerSignal("rcvdBytes");
            frameDelaySignal = registerSignal("frameDelay");
            frameMseSignal = registerSignal("frameMse");
            frameErrorSignal = registerSignal("frameError");
            frameOnTimeSignal = registerSignal("frameOnTime");
            meanErrorSignal = registerSignal("meanError");
            delayReliabilitySignal = registerSignal("delayReliability");
            userSatisfiedSignal = registerSignal("userSatisfied");

            resultFilename = par("resultFile").stdstringValue();
            if (!resultFilename.empty())
            {
                resultFile.open(resultFilename);
                if (resultFile.is_open())
                {
                    resultFile << "frameNumber,components,mse,sizeBytes,genTime,recvTime,"
                               << "delay_ms,receivedOnTime,effectiveError,deadline_ms" << endl;
                }
            }

            std::cout << "XRTrafficReceiver: Initialized with deadline=" << deadlineMs
                      << "ms, expected frames=" << expectedTotalFrames << endl;
        }
    }

    void XRTrafficReceiver::handleStartOperation(LifecycleOperation *operation)
    {
        socket.setOutputGate(gate("socketOut"));
        socket.setCallback(this);
        socket.bind(localPort);

        std::cout << "XRTrafficReceiver: Socket bound to port " << localPort << endl;
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
            stats.effectiveError = 1000.0; // default penalty for frames that never complete
            stats.fragmentsReceived = 1;
            stats.totalFragments = totalFragments;

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

            bool onTime = (delay <= deadlineMs);
            receivedFrames[frameNumber].receivedOnTime = onTime;

            double effectiveError;
            if (onTime)
            {
                effectiveError = mse;
            }
            else
            {
                // Fixed error of 1000 for late frames
                effectiveError = 1000.0;
            }
            receivedFrames[frameNumber].effectiveError = effectiveError;

            emit(rcvdPktSignal, 1);
            emit(rcvdBytesSignal, (long)sizeBytes);
            emit(frameDelaySignal, delay);
            emit(frameMseSignal, mse);
            emit(frameErrorSignal, effectiveError);
            emit(frameOnTimeSignal, onTime ? 1 : 0);

            if (resultFile.is_open())
            {
                resultFile << frameNumber << "," << components << "," << mse << ","
                           << sizeBytes << "," << fixed << setprecision(9) << genTime << ","
                           << recvTime.dbl() << "," << setprecision(6) << delay << ","
                           << (onTime ? 1 : 0) << "," << effectiveError << ","
                           << deadlineMs << endl;
            }

            std::cout << "Frame " << frameNumber << " COMPLETE: delay=" << delay
                      << "ms, onTime=" << onTime << ", MSE=" << mse
                      << ", error=" << effectiveError << endl;
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
                lostStats.effectiveError = 1000.0;

                receivedFrames[i] = lostStats;
                lostCount++;

                if (resultFile.is_open())
                {
                    resultFile << i << ",0,0,0,0,0,-1,0,1000,"
                               << deadlineMs << endl;
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

        emit(meanErrorSignal, meanError);

        // Calculate delay reliability and user satisfaction
        double delayReliability = onTimeRatio;  // Percentage of frames delivered on-time
        bool userSatisfied = (delayReliability >= reliabilityThreshold);  // 99% threshold
        
        emit(delayReliabilitySignal, delayReliability);
        emit(userSatisfiedSignal, userSatisfied ? 1 : 0);

        // Update global satisfied user count
        if (userSatisfied) {
            totalSatisfiedUsers++;
        }

        recordScalar("totalFrames", totalFrames);
        recordScalar("receivedFrames", receivedCount);
        recordScalar("onTimeFrames", onTimeCount);
        recordScalar("lateFrames", lateCount);
        recordScalar("lostFrames", lostCount);
        recordScalar("deliveryRatio", deliveryRatio);
        recordScalar("onTimeRatio", onTimeRatio);
        recordScalar("lossRatio", lossRatio);
        recordScalar("meanError", meanError);
        recordScalar("avgDelay_ms", avgDelay);
        recordScalar("deadline_ms", deadlineMs);
        recordScalar("delayReliability", delayReliability);
        recordScalar("reliabilityThreshold", reliabilityThreshold);
        recordScalar("userSatisfied", userSatisfied ? 1 : 0);

        std::cout << "\n========== XR Traffic QoE Summary ==========" << endl;
        std::cout << "Module:            " << getFullPath() << endl;
        std::cout << "Total frames:      " << totalFrames << endl;
        std::cout << "Received frames:   " << receivedCount << " (" << (deliveryRatio * 100) << "%)" << endl;
        std::cout << "On-time frames:    " << onTimeCount << " (" << (onTimeRatio * 100) << "%)" << endl;
        std::cout << "Late frames:       " << lateCount << " (error=1000 each)" << endl;
        std::cout << "Lost frames:       " << lostCount << " (error=1000 each, " << (lossRatio * 100) << "%)" << endl;
        std::cout << "Mean Error (QoE):  " << meanError << " (sumError=" << sumError << ")" << endl;
        std::cout << "Avg Delay:         " << avgDelay << " ms" << endl;
        std::cout << "Deadline:          " << deadlineMs << " ms" << endl;
        std::cout << "Delay Reliability: " << (delayReliability * 100) << "% (threshold: " << (reliabilityThreshold * 100) << "%)" << endl;
        std::cout << "User Satisfied:    " << (userSatisfied ? "YES" : "NO") << endl;
        std::cout << "Avg DL CQI:        " << avgCqi_ << endl;
        std::cout << "=========================================" << endl;
    }

    void XRTrafficReceiver::finish()
    {
        ApplicationBase::finish();

        // Get average CQI from PHY layer (try nrPhy first, then phy)
        avgCqi_ = 0.0;
        try {
            cModule *ue = getParentModule();  // app[0] is directly inside ue[x]
            if (ue != nullptr) {
                cModule *cellularNic = ue->getSubmodule("cellularNic");
                if (cellularNic != nullptr) {
                    // Try NR PHY first, then LTE PHY
                    cModule *phyModule = cellularNic->getSubmodule("nrPhy");
                    if (phyModule == nullptr) {
                        phyModule = cellularNic->getSubmodule("phy");
                    }
                    if (phyModule != nullptr) {
                        phyUe_ = dynamic_cast<LtePhyUe*>(phyModule);
                        if (phyUe_ != nullptr) {
                            avgCqi_ = phyUe_->getAverageCqi(DL);
                        }
                    }
                }
            }
        } catch (...) {
            EV_WARN << "Could not retrieve average CQI from PHY layer" << endl;
        }

        detectLostFrames();
        computeAndRecordQoE();

        if (resultFile.is_open())
        {
            resultFile.close();
        }

        finishedCount++; // Increment BEFORE the check

        if (finishedCount == userCount && !globalStatsPrinted) // Changed condition
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

            std::cout << "\n========== Global XR Traffic QoE Summary ==========" << endl;
            std::cout << "Number of users:       " << userCount << endl;
            std::cout << "Satisfied users:       " << totalSatisfiedUsers << " / " << userCount << endl;
            std::cout << "Total expected frames: " << totalExpectedFrames << endl;
            std::cout << "Total on-time frames:  " << totalOnTimeFrames << endl;
            std::cout << "Global Delay Reliab:   " << (globalDelayReliability * 100) << "%" << endl;
            std::cout << "Global Avg Mean Error: " << globalAvgMeanError << endl;
            std::cout << "===================================================" << endl;
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

} // namespace simu5g