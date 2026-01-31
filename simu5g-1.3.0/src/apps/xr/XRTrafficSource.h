#ifndef __SIMU5G_XRTRAFFICSOURCE_H_
#define __SIMU5G_XRTRAFFICSOURCE_H_

#include <omnetpp.h>
#include <fstream>
#include <sstream>
#include <vector>
#include <string>
#include <algorithm>
#include "inet/applications/base/ApplicationBase.h"
#include "inet/transportlayer/contract/udp/UdpSocket.h"
#include "inet/networklayer/common/L3Address.h"
#include "inet/networklayer/common/L3AddressResolver.h"
#include "stack/mac/LteMacBase.h"
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
        vector<FrameInfo> frames;
        int frame_number;
        double fps;
        simtime_t startTime;

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


        // ===== ADD THESE FOR BINDER SUPPORT =====
        // Reference to global Binder module
        Binder *binder_;

        // Cached MAC Node ID of this UE
        MacNodeId macNodeId_;

        // Helper methods
        Binder *getBinderModule();
        MacNodeId getMacNodeIdFromModule();
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
        double tran_gau_num(double mean, double sd, double minv, double maxv);
        void sendPacket();
        void scheduleNextPacket();

    public:
        XRTrafficSource() : sendTimer(nullptr), frame_number(0), fps(60.0), pcaFile("pca_selected.csv") {}
        virtual ~XRTrafficSource();
    };

} // namespace simu5g

#endif