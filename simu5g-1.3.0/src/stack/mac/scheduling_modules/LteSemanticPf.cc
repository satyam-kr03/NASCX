// simu5g-1.3.0/src/stack/mac/scheduling_modules/LteSemanticPF.cc

#include "stack/mac/scheduling_modules/LteSemanticPf.h"
#include "stack/mac/scheduler/LteSchedulerEnb.h"

namespace simu5g
{

    using namespace omnetpp;

    void LteSemanticPF::prepareSchedule()
    {
        std::cout << "LteSemanticPF::prepareSchedule eNodeB " << eNbScheduler_->mac_->getMacNodeId() << endl;
        std::cout << "LteSemanticPF::prepareSchedule Direction: " << ((direction_ == DL) ? " DL " : " UL ") << endl;

        grantedBytes_.clear();
        activeConnectionTempSet_ = *activeConnectionSet_;

        // --- Step 1: Calculate raw scores for all active connections ---
        std::map<MacCid, double> rawNetworkScores;
        std::map<MacCid, double> rawSemanticScores;

        if (carrierActiveConnectionSet_.empty())
        {
            return; // No users to schedule
        }

        for (const auto &cid : carrierActiveConnectionSet_)
        {
            MacNodeId nodeId = MacCidToNodeId(cid);
            if (binder_->getOmnetId(nodeId) == 0)
                continue;

            Direction dir = (direction_ == UL && (MacCidToLcid(cid) == D2D_SHORT_BSR || MacCidToLcid(cid) == D2D_MULTI_SHORT_BSR)) ? D2D : direction_;

            const UserTxParams &info = eNbScheduler_->mac_->getAmc()->computeTxParams(nodeId, dir, carrierFrequency_);
            if (info.readCqiVector().empty() || info.readCqiVector()[0] == 0)
                continue;

            // --- CORRECTED LOGIC for calculating available bytes and blocks ---
            // This logic is restored from the original LtePf.cc file.
            unsigned int availableBlocks = 0;
            unsigned int availableBytes = 0;
            const std::set<Band> &bands = info.readBands();
            for (auto antenna : info.readAntennaSet())
            {
                for (auto band : bands)
                {
                    unsigned int blocks = eNbScheduler_->readAvailableRbs(nodeId, antenna, band);
                    availableBlocks += blocks;
                    availableBytes += eNbScheduler_->mac_->getAmc()->computeBytesOnNRbs(nodeId, band, blocks, dir, carrierFrequency_);
                }
            }
            // --- End of corrected logic ---

            double networkScore = 0.0;
            if (pfRate_.find(cid) == pfRate_.end())
                pfRate_[cid] = 0;

            if (pfRate_[cid] < scoreEpsilon_)
            {
                networkScore = 1.0 / scoreEpsilon_;
            }
            else if (availableBlocks > 0)
            {
                networkScore = (double(availableBytes) / availableBlocks) / pfRate_[cid];
            }

            rawNetworkScores[cid] = std::log(networkScore + scoreEpsilon_);
            rawSemanticScores[cid] = 0.5; // Constant semantic score
        }

        if (rawNetworkScores.empty())
        {
            return; // No valid users to schedule
        }

        // --- Step 2: Normalize the scores using z-score normalization ---
        double net_sum = 0;
        for (auto const &[cid, score] : rawNetworkScores)
            net_sum += score;
        double net_mean = net_sum / rawNetworkScores.size();
        double net_sq_sum = 0;
        for (auto const &[cid, score] : rawNetworkScores)
            net_sq_sum += (score - net_mean) * (score - net_mean);
        double net_std_dev = std::sqrt(net_sq_sum / rawNetworkScores.size());

        double sem_sum = 0;
        for (auto const &[cid, score] : rawSemanticScores)
            sem_sum += score;
        double sem_mean = sem_sum / rawSemanticScores.size();
        double sem_sq_sum = 0;
        for (auto const &[cid, score] : rawSemanticScores)
            sem_sq_sum += (score - sem_mean) * (score - sem_mean);
        double sem_std_dev = std::sqrt(sem_sq_sum / rawSemanticScores.size());

        // --- Step 3: Calculate the unified score and populate the scheduling queue ---
        ScoreList scoreQueue;
        for (const auto &cid : carrierActiveConnectionSet_)
        {
            if (rawNetworkScores.find(cid) == rawNetworkScores.end())
                continue;

            double normalizedNetworkScore = 0.0;
            if (net_std_dev > scoreEpsilon_)
            {
                normalizedNetworkScore = (rawNetworkScores.at(cid) - net_mean) / net_std_dev;
            }

            double normalizedSemanticScore = 0.0;
            if (sem_std_dev > scoreEpsilon_)
            {
                normalizedSemanticScore = (rawSemanticScores.at(cid) - sem_mean) / sem_std_dev;
            }

            double unifiedScore = (semanticAlpha_ * normalizedNetworkScore) +
                                  ((1.0 - semanticAlpha_) * normalizedSemanticScore) +
                                  uniform(getEnvir()->getRNG(0), -scoreEpsilon_ / 2.0, scoreEpsilon_ / 2.0);

            scoreQueue.push(ScoreDesc(cid, unifiedScore));
            std::cout << "LteSemanticPF::prepareSchedule CID " << cid << " - Unified Score = " << unifiedScore
                      << " (NormNet: " << normalizedNetworkScore << ", NormSem: " << normalizedSemanticScore << ")" << endl;
        }

        // --- Step 4: Grant resources based on the unified score ---
        while (!scoreQueue.empty())
        {
            ScoreDesc current = scoreQueue.top();
            MacCid cid = current.x_;
            scoreQueue.pop();

            bool terminate = false, active = true, eligible = true;
            unsigned int granted = requestGrant(cid, 4294967295U, terminate, active, eligible);

            if (granted > 0)
                grantedBytes_[cid] += granted;
            if (terminate)
                break;
            if (!active)
            {
                activeConnectionTempSet_.erase(cid);
                carrierActiveConnectionSet_.erase(cid);
            }
        }
    }

    void LteSemanticPF::commitSchedule()
    {
        unsigned int total = eNbScheduler_->resourceBlocks_;

        for (const auto &[cid, granted] : grantedBytes_)
        {
            double shortTermRate = (total > 0) ? (double(granted) / double(total)) : 0.0;
            double &longTermRate = pfRate_[cid];
            longTermRate = (1.0 - pfAlpha_) * longTermRate + pfAlpha_ * shortTermRate;
        }

        *activeConnectionSet_ = activeConnectionTempSet_;
    }

} // namespace