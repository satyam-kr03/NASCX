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

    Define_Module(XRTrafficReceiver);

    XRTrafficReceiver::XRTrafficReceiver()
        : expectedTotalFrames(100), nextExpectedFrame(1), trackingStarted(false), qoeComputed(false),
          avgCqi_(0.0), phyUe_(nullptr)
    {
    }

    XRTrafficReceiver::~XRTrafficReceiver()
    {
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

            EV_INFO << "XRTrafficReceiver: Initialized with deadline=" << deadlineMs
                    << "ms, expected frames=" << expectedTotalFrames << endl;
        }
    }

    void XRTrafficReceiver::handleStartOperation(LifecycleOperation *operation)
    {
        socket.setOutputGate(gate("socketOut"));
        socket.setCallback(this);
        socket.bind(localPort);

        EV_INFO << "XRTrafficReceiver: Socket bound to port " << localPort << endl;
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
        EV_DETAIL << "XRTrafficReceiver: Packet arrived from "
                  << packet->getTag<L3AddressInd>()->getSrcAddress()
                  << ", name: " << packet->getName() << endl;

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

        EV_DETAIL << "Frame " << frameNumber << ": frag " << fragIndex 
                  << "/" << totalFragments << ", components=" << components << endl;

        simtime_t recvTime = simTime();

        if (!trackingStarted)
        {
            trackingStarted = true;
            firstFrameTime = recvTime;
            EV_INFO << "XRTrafficReceiver: Started tracking at t=" << recvTime << endl;
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
            stats.delay = -1;
            stats.receivedOnTime = false;
            stats.effectiveError = 1000.0;
            stats.fragmentsReceived = 1;
            stats.totalFragments = totalFragments;

            receivedFrames[frameNumber] = stats;

            EV_DETAIL << "First fragment " << fragIndex << "/" << totalFragments
                      << " of frame " << frameNumber << endl;
        }
        else
        {
            receivedFrames[frameNumber].fragmentsReceived++;

            EV_DETAIL << "Fragment " << fragIndex << "/" << totalFragments
                      << " of frame " << frameNumber << " (total: "
                      << receivedFrames[frameNumber].fragmentsReceived << ")" << endl;
        }

        if (receivedFrames[frameNumber].fragmentsReceived == totalFragments)
        {
            double delay = (recvTime.dbl() - genTime) * 1000.0;
            receivedFrames[frameNumber].delay = delay;

            bool onTime = (delay <= deadlineMs);
            receivedFrames[frameNumber].receivedOnTime = onTime;
            receivedFrames[frameNumber].effectiveError = onTime ? mse : 1000.0;

            EV_DETAIL << "Frame " << frameNumber << " COMPLETE: delay=" << delay
                      << "ms, onTime=" << onTime << ", MSE=" << mse
                      << ", error=" << receivedFrames[frameNumber].effectiveError << endl;
        }

        delete packet;
    }

    void XRTrafficReceiver::detectLostFrames()
    {
        EV_INFO << "XRTrafficReceiver: Detecting lost frames..." << endl;
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
            }
        }

        std::cout << "Total lost frames: " << lostCount << " out of " << expectedTotalFrames << endl;
        EV_INFO << "Total lost frames: " << lostCount << " out of " << expectedTotalFrames << endl;
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

        for (int i = 1; i <= expectedTotalFrames; i++)
        {
            const auto &stats = receivedFrames[i];

            sumError += stats.effectiveError;

            if (stats.delay >= 0)
            {
                receivedCount++;
                sumDelay += stats.delay;

                if (stats.receivedOnTime)
                    onTimeCount++;
                else
                    lateCount++;
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

        double delayReliability = onTimeRatio;
        bool userSatisfied = (delayReliability >= reliabilityThreshold);

        if (userSatisfied)
            totalSatisfiedUsers++;

        printQoESummary(totalFrames, receivedCount, onTimeCount, lateCount, lostCount,
                        deliveryRatio, onTimeRatio, lossRatio, meanError, sumError,
                        avgDelay, delayReliability, userSatisfied);
    }

    void XRTrafficReceiver::printQoESummary(int totalFrames, int receivedCount, int onTimeCount,
                                             int lateCount, int lostCount, double deliveryRatio,
                                             double onTimeRatio, double lossRatio, double meanError,
                                             double sumError, double avgDelay, double delayReliability,
                                             bool userSatisfied)
    {
        std::cout << std::fixed << std::setprecision(4);
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

        // Get average CQI from PHY layer
        avgCqi_ = 0.0;
        try {
            cModule *ue = getParentModule();
            if (ue != nullptr) {
                cModule *cellularNic = ue->getSubmodule("cellularNic");
                if (cellularNic != nullptr) {
                    cModule *phyModule = cellularNic->getSubmodule("nrPhy");
                    if (phyModule == nullptr)
                        phyModule = cellularNic->getSubmodule("phy");
                    if (phyModule != nullptr) {
                        phyUe_ = dynamic_cast<LtePhyUe*>(phyModule);
                        if (phyUe_ != nullptr)
                            avgCqi_ = phyUe_->getAverageCqi(DL);
                    }
                }
            }
        } catch (...) {
            EV_WARN << "Could not retrieve average CQI from PHY layer" << endl;
        }

        detectLostFrames();
        computeAndRecordQoE();

        finishedCount++;

        if (finishedCount == userCount && !globalStatsPrinted)
        {
            double globalAvgMeanError = (totalExpectedFrames > 0) ? totalSumError / totalExpectedFrames : 0.0;
            double globalDelayReliability = (totalExpectedFrames > 0) ? (double)totalOnTimeFrames / totalExpectedFrames : 0.0;

            printGlobalQoESummary(globalAvgMeanError, globalDelayReliability);
            globalStatsPrinted = true;
        }
    }

    void XRTrafficReceiver::printGlobalQoESummary(double globalAvgMeanError, double globalDelayReliability)
    {
        std::cout << std::fixed << std::setprecision(4);
        std::cout << "\n========== Global XR Traffic QoE Summary ==========" << endl;
        std::cout << "Number of users:       " << userCount << endl;
        std::cout << "Satisfied users:       " << totalSatisfiedUsers << " / " << userCount << endl;
        std::cout << "Total expected frames: " << totalExpectedFrames << endl;
        std::cout << "Total on-time frames:  " << totalOnTimeFrames << endl;
        std::cout << "Global Delay Reliab:   " << (globalDelayReliability * 100) << "%" << endl;
        std::cout << "Global Avg Mean Error: " << globalAvgMeanError << endl;
        std::cout << "===================================================" << endl;
    }

    void XRTrafficReceiver::socketErrorArrived(UdpSocket *socket, Indication *indication)
    {
        EV_WARN << "Socket error occurred" << endl;
        delete indication;
    }

    void XRTrafficReceiver::socketClosed(UdpSocket *socket)
    {
        EV_INFO << "Socket closed" << endl;
    }

} // namespace simu5g