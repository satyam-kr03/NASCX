#ifndef __SIMU5G_XRTRAFFICSOURCE_H_
#define __SIMU5G_XRTRAFFICSOURCE_H_

#include <omnetpp.h>
#include <fstream>
#include <sstream>
#include <vector>
#include <map>
#include <string>
#include <algorithm>
#include "inet/applications/base/ApplicationBase.h"
#include "inet/transportlayer/contract/udp/UdpSocket.h"
#include "inet/networklayer/common/L3Address.h"
#include "inet/networklayer/common/L3AddressResolver.h"
#include "stack/mac/LteMacBase.h"
#include "stack/mac/LteMacEnb.h"
#include "common/binder/Binder.h"

using namespace omnetpp;
using namespace std;
using namespace inet;

namespace simu5g
{

    struct FrameInfo
    {
        int frame_number; // frame number from CSV
        int components;   // number of PCA components used
        double mse;       // MSE value from reconstruction
        int size_bytes;   // compressed frame size in bytes
    };

    class XRTrafficSource : public ApplicationBase, public UdpSocket::ICallback
    {
    private:
        int lastFrameUpdated = -1;

        // Timing and frame management
        cMessage *sendTimer;
        vector<FrameInfo> frames;            // Legacy: used in "fixed" mode
        int frame_number;
        double fps;
        simtime_t startTime;

        // Per-frame dynamic selection data
        map<int, map<int, FrameInfo>> allFrameData_;  // frame → components → FrameInfo
        vector<int> frameNumbers_;                     // Sorted unique frame numbers
        vector<int> availableComponents_;              // Available compression levels (excl. uncompressed)
        string selectionMode_;                         // "fixed", "random", or "prescribed"

        // Prescribed mode: frame_number → chosen components
        map<int, int> prescribedComponents_;
        string prescribedFile_;

        // Model mode parameters
        string modelServerUrl_;
        int modelNumUsers_;
        int modelDefaultCqi_;

        // Per-frame complexity data (loaded from CSV)
        map<int, double> frameComplexity_;   // frame_number → frame_complexity
        map<int, std::vector<double>> frameErrorVector_;  // frame_number → MSE at each CL [5,10,...,80] (16 elements)
        static const int NUM_CL_LEVELS = 16;
        double meanTrafficSize_;              // mean of frame_complexity across all frames
        double stdTrafficSize_;               // std of frame_complexity

        // Jitter parameters
        double jitter_mean;
        double jitter_sd;
        double jitter_min;
        double jitter_max;
        int seed_val;

        // Network parameters
        UdpSocket socket;
        int localPort;
        int destPort;
        L3Address destAddress;
        string destAddressStr;
        string pcaFile;
        int compressionLevel_; // Filter by components: 0=all, else filter (5,10,15,...,80)

        // Statistics
        simsignal_t sentPktSignal;
        simsignal_t sentBytesSignal;

        // ===== ADD THESE FOR BINDER SUPPORT =====
        // Reference to global Binder module
        Binder *binder_;

        // Cached MAC Node ID of this UE
        MacNodeId macNodeId_;

        // Cached pointer to gNB MAC module (for buffer/utilization queries)
        LteMacEnb *gnbMac_;

        // Helper methods
        Binder *getBinderModule();
        MacNodeId getMacNodeIdFromModule();
        void updateGnbMetrics();  // Query gNB for buffer, MCS, utilization, active UEs
        // ===== END ADDITIONS =====

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
        void loadPCAData(const string &pcaFile);
        void loadPrescribedData(const string &prescribedFile);
        double tran_gau_num(double mean, double sd, double minv, double maxv);
        void sendPacket();
        int getFrameCount() const;
        void scheduleNextPacket();
        int queryModelServer(int frameNum);
        std::string httpPost(const std::string& url, const std::string& jsonPayload);

    public:
        XRTrafficSource() : sendTimer(nullptr), frame_number(0), fps(60.0), pcaFile("pca_selected.csv"),
                            meanTrafficSize_(0), stdTrafficSize_(0), modelNumUsers_(5), modelDefaultCqi_(10) {}
        virtual ~XRTrafficSource();
    };

} // namespace simu5g

#endif