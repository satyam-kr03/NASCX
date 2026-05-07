/**
 * @file XRTrafficSource.h
 * @brief XR video frame source module for Simu5G/OMNeT++ simulations.
 *
 * Reads PCA-compressed video frame data from CSV, selects compression
 * levels per-frame according to one of several modes (fixed, random,
 * prescribed, model), and transmits fragmented UDP packets to the
 * paired XRTrafficReceiver. Provides gNB-side metrics (buffer, MCS,
 * utilization) to the Binder for cross-layer feedback.
 */

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
#include "apps/xr/XRUtils.h"

namespace simu5g {

/**
 * @brief Per-frame compression metadata loaded from PCA sweep CSVs.
 */
struct FrameInfo
{
    int frameNumber_ = 0;   ///< Frame number from CSV
    int components = 0;     ///< Number of PCA components used
    double mse = 0.0;       ///< MSE from reconstruction
    int size_bytes = 0;     ///< Compressed frame size in bytes
};

/**
 * @brief XR video source that sends fragmented UDP frames.
 *
 * Selection modes:
 *   - "fixed":      Use a single compression level for all frames.
 *   - "random":     Pick a random CL per frame.
 *   - "prescribed": Follow a CSV schedule of per-frame CLs.
 *   - "model":      Query the FastAPI model server each frame.
 */
class XRTrafficSource : public inet::ApplicationBase, public inet::UdpSocket::ICallback
{
private:
    int lastFrameUpdated_ = -1;

    // Timing and frame management
    omnetpp::cMessage *sendTimer_ = nullptr;
    std::vector<FrameInfo> frames_;             ///< Legacy: used in "fixed" mode
    int frameNumber_ = 0;
    double fps_ = 60.0;
    omnetpp::simtime_t startTime_;

    // Per-frame dynamic selection data
    std::map<int, std::map<int, FrameInfo>> allFrameData_;   ///< frame → components → FrameInfo
    std::vector<int> frameNumbers_;                           ///< Sorted unique frame numbers
    std::vector<int> availableComponents_;                    ///< Available CLs (excl. uncompressed)
    std::string selectionMode_;                               ///< "fixed", "random", "prescribed", "model"

    // Prescribed mode: frame_number → chosen components
    std::map<int, int> prescribedComponents_;
    std::string prescribedFile_;

    // Model mode parameters
    std::string modelServerUrl_;
    int modelNumUsers_ = 5;
    int modelDefaultCqi_ = 10;

    // Per-frame complexity data (loaded from CSV)
    std::map<int, double> frameComplexity_;                       ///< frame_number → frame_complexity
    std::map<int, std::vector<double>> frameErrorVector_;         ///< frame_number → MSE at each CL (16 elements)
    double meanTrafficSize_ = 0.0;                                ///< Mean frame_complexity across all frames
    double stdTrafficSize_ = 0.0;                                 ///< Std frame_complexity

    // Jitter parameters
    double jitter_mean_ = 0.0;
    double jitter_sd_ = 0.0;
    double jitter_min_ = 0.0;
    double jitter_max_ = 0.0;
    int seed_val_ = 0;

    // Network parameters
    inet::UdpSocket socket_;
    int localPort_ = 0;
    int destPort_ = 0;
    inet::L3Address destAddress_;
    std::string destAddressStr_;
    std::string pcaFile_;
    int compressionLevel_ = 0;   ///< 0 = all, else filter to this CL

    // Statistics
    omnetpp::simsignal_t sentPktSignal_;
    omnetpp::simsignal_t sentBytesSignal_;

    // Binder integration
    Binder *binder_ = nullptr;           ///< Global Binder module reference
    MacNodeId macNodeId_ = 0;            ///< Cached MAC Node ID of this UE
    LteMacEnb *gnbMac_ = nullptr;        ///< Cached gNB MAC module pointer

    void updateGnbMetrics();

    /**
     * @brief Resolve compression parameters for a single frame.
     *
     * Encapsulates the selection logic for all four modes (fixed, random,
     * prescribed, model), returning the chosen FrameInfo. Extracted from
     * sendPacket() to eliminate four near-identical branches.
     *
    * @param frameIdx Index into frameNumbers_ for the current frame.
    * @param frameInfo Output struct containing chosen components, MSE, and size.
    * @return True if a valid frame selection was resolved.
     */
    bool resolveFrameInfo(int frameIdx, FrameInfo &frameInfo);

    // CSV parsing helpers (decomposed from loadPCAData)
    void parseCSV(const std::string &pcaFile);
    void buildErrorVectors();
    void computeVideoStats();

protected:
    /** @brief Initialize parameters, socket, and dataset state. */
    virtual void initialize(int stage) override;
    /** @brief Return the number of OMNeT++ init stages for this module. */
    virtual int numInitStages() const override { return NUM_INIT_STAGES; }
    /** @brief Handle self-messages and incoming UDP packets. */
    virtual void handleMessageWhenUp(omnetpp::cMessage *msg) override;
    /** @brief Finalize statistics and cleanup. */
    virtual void finish() override;

    // Application lifecycle
    /** @brief Start the application and schedule the first frame. */
    virtual void handleStartOperation(inet::LifecycleOperation *operation) override;
    /** @brief Stop transmission and close the socket. */
    virtual void handleStopOperation(inet::LifecycleOperation *operation) override;
    /** @brief Handle a crash event by closing the socket. */
    virtual void handleCrashOperation(inet::LifecycleOperation *operation) override;

    // UdpSocket::ICallback interface
    /** @brief Handle incoming UDP data (unexpected for a source). */
    virtual void socketDataArrived(inet::UdpSocket *socket, inet::Packet *packet) override;
    /** @brief Handle socket errors. */
    virtual void socketErrorArrived(inet::UdpSocket *socket, inet::Indication *indication) override;
    /** @brief Handle socket closure events. */
    virtual void socketClosed(inet::UdpSocket *socket) override;

    // Helpers
    /** @brief Load PCA reconstruction data from CSV. */
    void loadPCAData(const std::string &pcaFile);
    /** @brief Load prescribed compression schedule from CSV. */
    void loadPrescribedData(const std::string &prescribedFile);
    /** @brief Generate a truncated Gaussian random value. */
    double tran_gau_num(double mean, double sd, double minv, double maxv);
    /** @brief Send the next frame as UDP fragments. */
    void sendPacket();
    /** @brief Return the number of frames available for transmission. */
    int getFrameCount() const;
    /** @brief Schedule the next frame send event. */
    void scheduleNextPacket();
    /** @brief Query the model server for a compression decision. */
    int queryModelServer(int frameNum);
    /** @brief Perform an HTTP POST with a JSON payload. */
    std::string httpPost(const std::string &url, const std::string &jsonPayload);

public:
    XRTrafficSource() = default;
    virtual ~XRTrafficSource();
};

} // namespace simu5g

#endif // __SIMU5G_XRTRAFFICSOURCE_H_