#ifndef __SIMU5G_XRTRAFFICRECEIVER_H_
#define __SIMU5G_XRTRAFFICRECEIVER_H_

#include <omnetpp.h>
#include <map>
#include <vector>
#include "inet/applications/base/ApplicationBase.h"
#include "inet/transportlayer/contract/udp/UdpSocket.h"
#include "inet/networklayer/common/L3Address.h"
#include <fstream>

// Forward declaration for PHY access
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
        double delay; // in seconds
        bool receivedOnTime;
        double effectiveError; // MSE if on time, Elost if late
        int fragmentsReceived;
        int totalFragments;
    };

    class XRTrafficReceiver : public ApplicationBase, public UdpSocket::ICallback
    {
    private:
        // Network parameters
        UdpSocket socket;
        int localPort;

        // QoE parameters
        double deadlineMs; // Frame deadline in milliseconds
        double reliabilityThreshold; // Delay reliability threshold (e.g., 0.99 for 99%)
        double elostValue; // Error penalty for lost frames (max MSE)
        bool autoElost;    // Automatically set Elost to max MSE

        // Frame tracking
        map<int, ReceivedFrameStats> receivedFrames;
        int expectedTotalFrames;
        int nextExpectedFrame;
        bool trackingStarted;
        simtime_t firstFrameTime;

        // Flag to prevent double computation
        bool qoeComputed;

        // Statistics signals
        simsignal_t rcvdPktSignal;
        simsignal_t rcvdBytesSignal;
        simsignal_t frameDelaySignal;
        simsignal_t frameMseSignal;
        simsignal_t frameErrorSignal;
        simsignal_t frameOnTimeSignal;
        simsignal_t meanErrorSignal;
        simsignal_t delayReliabilitySignal;
        simsignal_t userSatisfiedSignal;

        // Result file
        ofstream resultFile;
        string resultFilename;

        // Static variables for global statistics
        static double totalAvgMse;
        static double totalSumError;
        static int totalExpectedFrames;
        static int totalOnTimeFrames;
        static int totalSatisfiedUsers;
        static int userCount;
        static bool globalStatsPrinted;
        static int finishedCount;
        static std::ofstream globalResultFile;
        
        // CQI tracking
        double avgCqi_;
        LtePhyUe* phyUe_;

    protected:
        virtual void initialize(int stage) override;
        virtual int numInitStages() const override { return NUM_INIT_STAGES; }
        virtual void handleMessageWhenUp(cMessage *msg) override;
        virtual void finish() override;

        // Application lifecycle
        virtual void handleStartOperation(LifecycleOperation *operation) override;
        virtual void handleStopOperation(LifecycleOperation *operation) override;
        virtual void handleCrashOperation(LifecycleOperation *operation) override;

        // UdpSocket::ICallback interface
        virtual void socketDataArrived(UdpSocket *socket, Packet *packet) override;
        virtual void socketErrorArrived(UdpSocket *socket, Indication *indication) override;
        virtual void socketClosed(UdpSocket *socket) override;

        // Helper methods
        void processFrame(Packet *packet);
        void detectLostFrames();
        void computeAndRecordQoE();
        double getMaxMSE();

    public:
        XRTrafficReceiver();
        virtual ~XRTrafficReceiver();
    };

} // namespace simu5g

#endif