/**
 * @file XRUtils.h
 * @brief Shared utilities for XR application modules.
 *
 * Provides common constants and helper functions used by both
 * XRTrafficSource and XRTrafficReceiver to eliminate code duplication.
 */

#ifndef XR_UTILS_H_
#define XR_UTILS_H_

#include <omnetpp.h>
#include "common/binder/Binder.h"

namespace simu5g {

/// Number of PCA features in an uncompressed frame (224 * 224 * 3)
static constexpr int UNCOMPRESSED_COMPONENTS = 150528;

/// Number of discrete compression levels (5, 10, ..., 80)
static constexpr int NUM_CL_LEVELS = 16;

/// Step between adjacent compression levels
static constexpr int CL_STEP = 5;

/**
 * @brief Resolve the Binder module from the simulation.
 *
 * Walks the module hierarchy to find the Binder singleton.
 * Returns nullptr if the Binder cannot be found.
 *
 * @param simulation Pointer to the active cSimulation instance.
 * @return Pointer to the Binder module, or nullptr.
 */
inline Binder* resolveBinderModule(omnetpp::cSimulation* simulation)
{
    // The Binder is registered as a global module in Simu5G
    omnetpp::cModule* binderMod = simulation->getModuleByPath("binder");
    if (binderMod) {
        Binder* binder = dynamic_cast<Binder*>(binderMod);
        return binder;
    }
    return nullptr;
}

} // namespace simu5g

#endif // XR_UTILS_H_
