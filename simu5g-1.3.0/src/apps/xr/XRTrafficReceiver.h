#ifndef __SIMU5G_XRTRAFFICRECEIVER_H_
#define __SIMU5G_XRTRAFFICRECEIVER_H_

#include <omnetpp.h>
#include <iosfwd>
#include <map>
#include <string>
#include <vector>
#include "inet/applications/base/ApplicationBase.h"
#include "inet/transportlayer/contract/udp/UdpSocket.h"
#include "inet/networklayer/common/L3Address.h"
#include "common/binder/Binder.h"

// Forward declaration for PHY access
namespace simu5g { class LtePhyUe; }

namespace simu5g
{

    struct ReceivedFrameStats
    {
        int frameNumber;
        int pcaComponents;
        double mse;
        int sizeBytes;
        omnetpp::simtime_t genTime;
        omnetpp::simtime_t recvTime;
        double delay; // in seconds
        bool receivedOnTime;
        double effectiveError; // MSE if on time, Elost if late
        int fragmentsReceived;
        int totalFragments;
        unsigned int cqi; // instantaneous DL CQI at frame reception
        unsigned int buffer_bytes;
        unsigned int mcs_index;
        double dl_utilization;
        int n_active_ues;

        static ReceivedFrameStats createLost(int frameNum, double elost)
        {
            ReceivedFrameStats stats;
            stats.frameNumber = frameNum;
            stats.pcaComponents = 0;
            stats.mse = 0.0;
            stats.sizeBytes = 0;
            stats.genTime = 0;
            stats.recvTime = 0;
            stats.delay = -1;
            stats.receivedOnTime = false;
            stats.effectiveError = elost;
            stats.fragmentsReceived = 0;
            stats.totalFragments = 0;
            stats.cqi = 0;
            stats.buffer_bytes = 0;
            stats.mcs_index = 0;
            stats.dl_utilization = 0.0;
            stats.n_active_ues = 0;
            return stats;
        }
    };

    class XRTrafficReceiver : public ApplicationBase, public UdpSocket::ICallback
    {
    private:
        // Network parameters
        inet::UdpSocket socket;
        int localPort;

        // QoE parameters
        double deadlineMs; // Frame deadline in milliseconds
        double reliabilityThreshold; // Delay reliability threshold (e.g., 0.99 for 99%)
        double elostValue; // Error penalty for lost frames (max MSE)
        bool autoElost;    // Automatically set Elost to max MSE

        // Frame tracking
        std::map<int, ReceivedFrameStats> receivedFrames;
        int expectedTotalFrames;
        int nextExpectedFrame;
        bool trackingStarted;
        omnetpp::simtime_t firstFrameTime;

        // Flag to prevent double computation
        bool qoeComputed;

        // Result file
        std::ofstream resultFile;
        std::string resultFilename;

        // Static variables for global statistics
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

        // Binder reference for CQI feedback
        Binder *binder_;
        MacNodeId macNodeId_;

    protected:
        virtual void initialize(int stage) override;
        virtual int numInitStages() const override { return NUM_INIT_STAGES; }
        virtual void handleMessageWhenUp(omnetpp::cMessage *msg) override;
        virtual void finish() override;

        // Application lifecycle
        virtual void handleStartOperation(inet::LifecycleOperation *operation) override;
        virtual void handleStopOperation(inet::LifecycleOperation *operation) override;
        virtual void handleCrashOperation(inet::LifecycleOperation *operation) override;

        // UdpSocket::ICallback interface
        virtual void socketDataArrived(inet::UdpSocket *socket, inet::Packet *packet) override;
        virtual void socketErrorArrived(inet::UdpSocket *socket, inet::Indication *indication) override;
        virtual void socketClosed(inet::UdpSocket *socket) override;

        // Helper methods
        void processFrame(inet::Packet *packet);
        void detectLostFrames();
        void computeAndRecordQoE();
        double getMaxMSE(const std::string &pcaFile, int minComponents);

    public:
        XRTrafficReceiver();
        virtual ~XRTrafficReceiver();
    };

} // namespace simu5g

#endif