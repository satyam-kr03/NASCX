// simu5g-1.3.0/src/stack/mac/scheduling_modules/LteSemanticPF.h

#ifndef _LTE_LTESEMANTICPF_H_
#define _LTE_LTESEMANTICPF_H_

#include "stack/mac/scheduler/LteScheduler.h"
#include <cmath>   // For std::log and std::sqrt
#include <numeric> // For std::accumulate

namespace simu5g
{

    class LteSemanticPF : public LteScheduler
    {
    protected:
        typedef std::map<MacCid, double> PfRate;
        typedef SortedDesc<MacCid, double> ScoreDesc;
        typedef std::priority_queue<ScoreDesc> ScoreList;

        //! Long-term rates, used for the PF network score component.
        PfRate pfRate_;

        //! Granted bytes
        std::map<MacCid, unsigned int> grantedBytes_;

        //! Smoothing factor for the PF network score component.
        double pfAlpha_;

        //! Weighting factor for combining network and semantic scores (α from the paper).
        double semanticAlpha_;

        //! Small number to slightly blur scores.
        const double scoreEpsilon_ = 0.000001;

    public:
        // Scheduling functions
        void prepareSchedule() override;
        void commitSchedule() override;

        // Constructor
        LteSemanticPF(Binder *binder, double pfAlpha, double semanticAlpha) : LteScheduler(binder),
                                                                              pfAlpha_(pfAlpha),
                                                                              semanticAlpha_(semanticAlpha)
        {
        }
    };

} // namespace

#endif // _LTE_LTESEMANTICPF_H_