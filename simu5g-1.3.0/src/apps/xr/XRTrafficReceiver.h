#ifndef __SIMU5G_XRTRAFFICRECEIVER_H_
#define __SIMU5G_XRTRAFFICRECEIVER_H_

#include <omnetpp.h>
#include <map>
#include <vector>
#include "inet/applications/base/ApplicationBase.h"
#include "inet/transportlayer/contract/udp/UdpSocket.h"
#include "inet/networklayer/common/L3Address.h"

namespace simu5g { class LtePhyUe; }

using namespace omnetpp;
using namespace std;
using namespace inet;

namespace simu5g
{

    struct ReceivedFrameStats
    {
        int frameNumber;
        int pcaComponents;
        double mse;
        int sizeBytes;
        simtime_t genTime;
        simtime_t recvTime;
        double delay;
        bool receivedOnTime;
        double effectiveError;
        int fragmentsReceived;
        int totalFragments;
    };

    class XRTrafficReceiver : public ApplicationBase, public UdpSocket::ICallback
    {
    private:
        UdpSocket socket;
        int localPort;

        double deadlineMs;
        double reliabilityThreshold;

        map<int, ReceivedFrameStats> receivedFrames;
        int expectedTotalFrames;
        int nextExpectedFrame;
        bool trackingStarted;
        simtime_t firstFrameTime;

        bool qoeComputed;

        // Static variables for global statistics
        static double totalSumError;
        static int totalExpectedFrames;
        static int totalOnTimeFrames;
        static int totalSatisfiedUsers;
        static int userCount;
        static bool globalStatsPrinted;
        static int finishedCount;
        
        double avgCqi_;
        LtePhyUe* phyUe_;

    protected:
        virtual void initialize(int stage) override;
        virtual int numInitStages() const override { return NUM_INIT_STAGES; }
        virtual void handleMessageWhenUp(cMessage *msg) override;
        virtual void finish() override;

        virtual void handleStartOperation(LifecycleOperation *operation) override;
        virtual void handleStopOperation(LifecycleOperation *operation) override;
        virtual void handleCrashOperation(LifecycleOperation *operation) override;

        virtual void socketDataArrived(UdpSocket *socket, Packet *packet) override;
        virtual void socketErrorArrived(UdpSocket *socket, Indication *indication) override;
        virtual void socketClosed(UdpSocket *socket) override;

        void processFrame(Packet *packet);
        void detectLostFrames();
        void computeAndRecordQoE();
        
        void printQoESummary(int totalFrames, int receivedCount, int onTimeCount,
                             int lateCount, int lostCount, double deliveryRatio,
                             double onTimeRatio, double lossRatio, double meanError,
                             double sumError, double avgDelay, double delayReliability,
                             bool userSatisfied);
        void printGlobalQoESummary(double globalAvgMeanError, double globalDelayReliability);

    public:
        XRTrafficReceiver();
        virtual ~XRTrafficReceiver();
    };

} // namespace simu5g

#endif