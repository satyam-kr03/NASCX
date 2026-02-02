//
//                  Simu5G
//
// Custom Error-Aware Proportional Fair Scheduler
// Based on LtePf but with MSE/RMSE-based score modification
//

#ifndef _LTE_ERROR_AWARE_PF_H_
#define _LTE_ERROR_AWARE_PF_H_

#include "stack/mac/scheduling_modules/LtePf.h"

namespace simu5g
{

    class LteErrorAwarePf : public LtePf
    {
    protected:
        // Whether to use logarithmic scaling for RMSE
        // This can help balance the contribution of RMSE vs. PF ratio
        bool useLogScaling_;

        // Flag to enable/disable Error-aware scheduling
        // Useful for A/B testing or fallback scenarios
        bool enableErrorAwareScheduling_;

        // Weight for base PF score in final score calculation
        double beta_;

        // Weight for RMSE within Error terms in final score calculation
        double gamma_;

    public:
        // Constructor - inherits from LtePf
        LteErrorAwarePf(Binder *binder, double pfAlpha = 0.95, double beta = 0.6, double gamma = 0.4)
            : LtePf(binder, pfAlpha), useLogScaling_(true), enableErrorAwareScheduling_(true), beta_(beta), gamma_(gamma) {}

        // Virtual destructor for proper polymorphic behavior
        virtual ~LteErrorAwarePf() = default;

        /**
         * Prepares the scheduling decision by computing scores
         * with Error metrics (MSE/RMSE) incorporated
         */
        virtual void prepareSchedule() override;
        
        /**
         * Computes the score for a connection, incorporating RMSE
         *
         * @param cid Connection ID
         * @param availableBytes Bytes that can be transmitted
         * @param availableBlocks Number of available resource blocks
         * @param nodeId MAC Node ID of the UE
         * @return Computed score
         */
        virtual double computeScore(MacCid cid, unsigned int availableBytes,
                                    unsigned int availableBlocks, MacNodeId nodeId);
    };

} // namespace

#endif