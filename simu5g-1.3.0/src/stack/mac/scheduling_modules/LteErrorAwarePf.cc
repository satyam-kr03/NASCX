//
//                  Simu5G
//
// Custom XR-Aware Proportional Fair Scheduler Implementation
//

#include "stack/mac/scheduling_modules/LteErrorAwarePf.h"
#include "stack/mac/scheduler/LteSchedulerEnb.h"
#include "common/binder/Binder.h"
#include <cmath>
#include <iostream>

namespace simu5g
{

    using namespace omnetpp;

    // per-CID EMAs for normalization (keeps state across calls)
    static std::map<MacCid, double> emaBaseMean;
    static std::map<MacCid, double> emaBaseVar;
    static std::map<MacCid, double> emaRmseMean;
    static std::map<MacCid, double> emaRmseVar;
    static std::map<MacCid, double> emaSizeMean;
    static std::map<MacCid, double> emaSizeVar;
    static const double EMA_ALPHA = 0.12; // smoothing factor (tuneable)

    void LteErrorAwarePf::prepareSchedule()
    {
        // std::cout << "\n========================================" << std::endl;
        // std::cout << "LteErrorAwarePf::prepareSchedule START at time " << NOW << std::endl;
        // std::cout << "eNodeB ID: " << eNbScheduler_->mac_->getMacNodeId() << std::endl;
        // std::cout << "Direction: " << ((direction_ == DL) ? "DL" : "UL") << std::endl;
        // std::cout << "========================================\n"
        //           << std::endl;

        EV << NOW << " LteErrorAwarePf::prepareSchedule ############### eNodeB "
           << eNbScheduler_->mac_->getMacNodeId() << " ###############" << endl;
        EV << NOW << " LteErrorAwarePf::prepareSchedule Direction: "
           << ((direction_ == DL) ? " DL " : " UL ") << endl;

        // Get configuration parameters from NED file
        cModule *schedulerModule = eNbScheduler_->mac_->getParentModule()
                                       ->getSubmodule("mac")
                                       ->getSubmodule("scheduler");

        if (schedulerModule != nullptr)
        {
            beta_ = schedulerModule->par("errorAwareBeta").doubleValue();
            gamma_ = schedulerModule->par("errorAwareGamma").doubleValue();
            useLogScaling_ = schedulerModule->par("errorAwareUseLogScaling").boolValue();
            enableErrorAwareScheduling_ = schedulerModule->par("errorAwareEnableScheduling").boolValue();

            std::cout << "Configuration loaded from NED:" << std::endl;
            std::cout << "  beta = " << beta_ << std::endl;
            std::cout << "  gamma = " << gamma_ << std::endl;
            std::cout << "  useLogScaling = " << (useLogScaling_ ? "true" : "false") << std::endl;
            std::cout << "  enableErrorAwareScheduling = " << (enableErrorAwareScheduling_ ? "true" : "false") << std::endl;
        }
        else
        {
            // Default values if parameters not found
            useLogScaling_ = true;
            enableErrorAwareScheduling_ = true;

            // std::cout << "WARNING: Scheduler module not found, using defaults!" << std::endl;
        }

        // Clear structures
        grantedBytes_.clear();

        // Create a working copy of the active set
        activeConnectionTempSet_ = *activeConnectionSet_;

        // std::cout << "\nActive connections: " << carrierActiveConnectionSet_.size() << std::endl;

        // Build the score list by cycling through the active connections
        ScoreList score;

        for (const auto &cid : carrierActiveConnectionSet_)
        {
            std::cout << "\n--- Processing CID " << cid << " ---" << std::endl;

            MacNodeId nodeId = MacCidToNodeId(cid);
            OmnetId id = binder_->getOmnetId(nodeId);
            grantedBytes_[cid] = 0;

            std::cout << "  NodeId: " << nodeId << ", OmnetId: " << id << std::endl;

            if (nodeId == NODEID_NONE || id == 0)
            {
                std::cout << "  SKIPPED: Invalid node/omnet ID" << std::endl;
                // node has left the simulation - erase corresponding CIDs
                activeConnectionSet_->erase(cid);
                activeConnectionTempSet_.erase(cid);
                carrierActiveConnectionSet_.erase(cid);
                continue;
            }

            // if we are allocating the UL subframe, this connection may be either UL or D2D
            Direction dir;
            if (direction_ == UL)
                dir = (MacCidToLcid(cid) == D2D_SHORT_BSR) ? D2D : (MacCidToLcid(cid) == D2D_MULTI_SHORT_BSR) ? D2D_MULTI
                                                                                                              : direction_;
            else
                dir = DL;

            // check if node is still valid
            if (binder_->getOmnetId(nodeId) == 0)
            {
                std::cout << "  SKIPPED: No OmnetId in Binder" << std::endl;
                activeConnectionTempSet_.erase(cid);
                carrierActiveConnectionSet_.erase(cid);
                EV << "CID " << cid << " of node " << nodeId
                   << " removed from active connection set - no OmnetId in Binder." << endl;
                continue;
            }

            // compute available blocks for the current user
            const UserTxParams &info = eNbScheduler_->mac_->getAmc()->computeTxParams(
                nodeId, dir, carrierFrequency_);
            const std::set<Band> &bands = info.readBands();
            unsigned int codeword = info.getLayers().size();

            if (eNbScheduler_->allocatedCws(nodeId) == codeword)
            {
                std::cout << "  SKIPPED: All codewords allocated" << std::endl;
                continue;
            }

            auto it = bands.begin(), et = bands.end();

            bool cqiNull = false;
            for (unsigned int i = 0; i < codeword; i++)
            {
                if (info.readCqiVector()[i] == 0)
                    cqiNull = true;
            }
            if (cqiNull)
            {
                std::cout << "  SKIPPED: CQI is zero" << std::endl;
                continue;
            }

            // compute available blocks and bytes
            unsigned int availableBlocks = 0;
            unsigned int availableBytes = 0;

            for (auto antenna : info.readAntennaSet())
            {
                for (it = bands.begin(); it != et; ++it)
                {
                    unsigned int blocks = eNbScheduler_->readAvailableRbs(nodeId, antenna, *it);
                    availableBlocks += blocks;
                    availableBytes += eNbScheduler_->mac_->getAmc()->computeBytesOnNRbs(
                        nodeId, *it, blocks, dir, carrierFrequency_);
                }
            }

            std::cout << "  Available Blocks: " << availableBlocks << std::endl;
            std::cout << "  Available Bytes: " << availableBytes << std::endl;

            // Compute score using Error-aware method
            double s = computeScore(cid, availableBytes, availableBlocks, nodeId);

            std::cout << "  Final Score: " << s << std::endl;

            // Create score descriptor
            ScoreDesc desc(cid, s);
            score.push(desc);

            EV << NOW << " LteErrorAwarePf::prepareSchedule CID " << cid
               << " - Score = " << s << endl;
        }

        // std::cout << "\n========================================" << std::endl;
        // std::cout << "Scheduling phase - processing score queue" << std::endl;
        // std::cout << "========================================\n"
        //           << std::endl;

        // Schedule connections in score order
        while (!score.empty())
        {
            ScoreDesc current = score.top();
            MacCid cid = current.x_;

            std::cout << "\n>>> Granting resources to CID " << cid
                      << " (Score: " << current.score_ << ")" << std::endl;

            EV << NOW << " LteErrorAwarePf::prepareSchedule @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@" << endl;
            EV << NOW << " LteErrorAwarePf::prepareSchedule CID: " << cid << endl;
            EV << NOW << " LteErrorAwarePf::prepareSchedule Score: " << current.score_ << endl;

            // Grant data to that connection
            bool terminate = false;
            bool active = true;
            bool eligible = true;

            unsigned int granted = requestGrant(cid, 4294967295U, terminate, active, eligible);
            grantedBytes_[cid] += granted;

            std::cout << "    Granted: " << granted << " bytes" << std::endl;
            std::cout << "    Terminate: " << (terminate ? "YES" : "NO") << std::endl;
            std::cout << "    Active: " << (active ? "YES" : "NO") << std::endl;
            std::cout << "    Eligible: " << (eligible ? "YES" : "NO") << std::endl;

            EV << NOW << " LteErrorAwarePf::prepareSchedule Granted: " << granted << " bytes" << endl;

            // Exit if terminate flag is set
            if (terminate)
            {
                std::cout << "*** TERMINATING SCHEDULE ***" << std::endl;
                EV << NOW << " LteErrorAwarePf::prepareSchedule TERMINATE " << endl;
                break;
            }

            // Pop descriptor if not active or eligible
            if (!active || !eligible)
            {
                score.pop();
                if (!eligible)
                {
                    std::cout << "    Connection NOT ELIGIBLE - removed from queue" << std::endl;
                    EV << NOW << " LteErrorAwarePf::prepareSchedule NOT ELIGIBLE " << endl;
                }
            }

            // Set connection as inactive if indicated
            if (!active)
            {
                std::cout << "    Connection NOT ACTIVE - erased from active set" << std::endl;
                EV << NOW << " LteErrorAwarePf::prepareSchedule NOT ACTIVE" << endl;
                activeConnectionTempSet_.erase(current.x_);
                carrierActiveConnectionSet_.erase(current.x_);
            }
        }

        // std::cout << "\n========================================" << std::endl;
        // std::cout << "LteErrorAwarePf::prepareSchedule END" << std::endl;
        // std::cout << "========================================\n"
        //           << std::endl;
    }

    double LteErrorAwarePf::computeScore(MacCid cid, unsigned int availableBytes,
                                 unsigned int availableBlocks, MacNodeId nodeId)
    {
        std::cout << "\n  [computeScore] CID=" << cid << ", NodeId=" << nodeId << std::endl;

        // Initialize PF rate if needed
        if (pfRate_.find(cid) == pfRate_.end())
        {
            pfRate_[cid] = 0;
            std::cout << "    PF rate initialized to 0" << std::endl;
        }

        double baseScore = 0.0;

        // Compute base PF score
        if (pfRate_[cid] < scoreEpsilon_)
        {
            baseScore = 1.0 / scoreEpsilon_;
            std::cout << "    Base PF score (epsilon): " << baseScore << std::endl;
        }
        else if (availableBlocks > 0)
        {
            baseScore = ((double)availableBytes / availableBlocks) / pfRate_[cid];
            std::cout << "    Base PF score: " << baseScore
                      << " = (" << availableBytes << "/" << availableBlocks
                      << ") / " << pfRate_[cid] << std::endl;
        }
        else
        {
            baseScore = 0.0;
            std::cout << "    Base PF score: 0 (no available blocks)" << std::endl;
        }

        // Add small random jitter (as in original PF)
        double jitter = uniform(getEnvir()->getRNG(0), -scoreEpsilon_ / 2.0, scoreEpsilon_ / 2.0);
        baseScore += jitter;
        std::cout << "    After jitter: " << baseScore << " (jitter=" << jitter << ")" << std::endl;

        // If Error-aware scheduling is disabled, return base score
        if (!enableErrorAwareScheduling_)
        {
            std::cout << "    Error-aware scheduling DISABLED - returning base score" << std::endl;
            return baseScore;
        }

        // Try to get Error metrics from binder
        std::cout << "    Attempting to get Error metrics from Binder..." << std::endl;
        const XRMetrics *xrMetrics = binder_->getXRMetrics(nodeId);

        if (xrMetrics == nullptr)
        {
            std::cout << "    WARNING: No Error metrics available - using base PF score only" << std::endl;
            return baseScore;
        }

        std::cout << "      Error metrics found!" << std::endl;
        std::cout << "      MSE: " << xrMetrics->mse << std::endl;
        std::cout << "      Size (bytes): " << xrMetrics->sizeBytes << std::endl;

        std::cout << "      Proceeding with Error-aware scoring" << std::endl;

        // Get RMSE from metrics
        double mse = xrMetrics->mse;
        double rmse = sqrt(mse);
        double sizeBytes = static_cast<double>(xrMetrics->sizeBytes);

        std::cout << "      RMSE: " << rmse << " (sqrt of MSE)" << std::endl;

        // Optionally apply log scaling
        double rmseVal = useLogScaling_ ? log1p(rmse) : rmse;
        double sizeVal = useLogScaling_ ? log1p(sizeBytes) : sizeBytes;
        double baseVal = useLogScaling_ ? log1p(std::max(baseScore, 0.0)) : baseScore;

        if (useLogScaling_)
        {
            std::cout << "    Log scaling ENABLED:" << std::endl;
            std::cout << "      log1p(RMSE): " << rmseVal << std::endl;
            std::cout << "      log1p(Size): " << sizeVal << std::endl;
            std::cout << "      log1p(Base): " << baseVal << std::endl;
        }
        else
        {
            std::cout << "    Log scaling DISABLED (using raw values)" << std::endl;
        }
        
        // Helper to update EMA mean/var for a given map keyed by cid
        auto updateEma = [&](std::map<MacCid, double> &meanMap,
                             std::map<MacCid, double> &varMap,
                             double value)
        {
            if (meanMap.find(cid) == meanMap.end())
            {
                meanMap[cid] = value;
                varMap[cid] = 1e-6;
                std::cout << "      EMA initialized: mean=" << value << ", var=1e-6" << std::endl;
            }
            else
            {
                double prevMean = meanMap[cid];
                double newMean = EMA_ALPHA * value + (1.0 - EMA_ALPHA) * prevMean;
                double diff = value - newMean;
                double prevVar = varMap[cid];
                double newVar = EMA_ALPHA * (diff * diff) + (1.0 - EMA_ALPHA) * prevVar;
                meanMap[cid] = newMean;
                varMap[cid] = newVar;
                std::cout << "      EMA updated: mean " << prevMean << " → " << newMean
                          << ", var " << prevVar << " → " << newVar << std::endl;
            }
        };

        // Update EMAs
        std::cout << "    Updating Base EMA:" << std::endl;
        updateEma(emaBaseMean, emaBaseVar, baseVal);
        std::cout << "    Updating RMSE EMA:" << std::endl;
        updateEma(emaRmseMean, emaRmseVar, rmseVal);
        std::cout << "    Updating Size EMA:" << std::endl;
        updateEma(emaSizeMean, emaSizeVar, sizeVal);

        // Compute normalized values (z-like), protect against tiny stddev
        auto computeNorm = [&](std::map<MacCid, double> &meanMap,
                               std::map<MacCid, double> &varMap,
                               double value)
        {
            double variance = varMap[cid];

            // Bootstrap phase: insufficient history for normalization
            // Use raw scaled values until we have meaningful variance
            if (variance < 0.01)
            {
                std::cout << "      Bootstrap mode (var=" << variance << ") - using scaled value: " << value << std::endl;
                return value; // Return raw value during cold start
            }

            // Normal operation: z-score normalization
            double mean = meanMap[cid];
            double stddev = sqrt(variance);
            if (stddev < 1e-6)
                stddev = 1.0; // avoid blowup on near-constant streams
            double zScore = (value - mean) / stddev;
            std::cout << "      Z-score: (" << value << " - " << mean << ") / "
                      << stddev << " = " << zScore << std::endl;
            return zScore;
        };

        std::cout << "    Computing normalized Base:" << std::endl;
        double normBase = computeNorm(emaBaseMean, emaBaseVar, baseVal);
        std::cout << "    Computing normalized RMSE:" << std::endl;
        double normRmse = computeNorm(emaRmseMean, emaRmseVar, rmseVal);
        std::cout << "    Computing normalized Size:" << std::endl;
        double normSize = computeNorm(emaSizeMean, emaSizeVar, sizeVal);

        // Combine normalized terms with configurable weights from NED parameters
        double finalScore = beta_ * normBase + gamma_ * normRmse + (1.0 - beta_ - gamma_) * normSize;

        std::cout << "    Final score calculation:" << std::endl;
        std::cout << "      " << beta_ << " * " << normBase << " (base) + "
                  << gamma_ << " * " << normRmse << " (rmse) + "
                  << (1.0 - beta_ - gamma_) << " * " << normSize << " (size)" << std::endl;
        std::cout << "      = " << finalScore << std::endl;

        return finalScore;
    }

} // namespace