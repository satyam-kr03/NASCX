//
//                  Simu5G
//
// Authors: Giovanni Nardini, Giovanni Stea, Antonio Virdis (University of Pisa)
//
// This file is part of a software released under the license included in file
// "license.pdf". Please read LICENSE and README files before using it.
// The above files and the present reference are part of the software itself,
// and cannot be removed from it.
//

#ifndef _LTE_XRRECEIVER_H_
#define _LTE_XRRECEIVER_H_

#include <list>
#include <string.h>

#include <omnetpp.h>

#include <inet/networklayer/common/L3AddressResolver.h>
#include <inet/transportlayer/contract/udp/UdpSocket.h>

#include "apps/xr/XRPacket_m.h"

namespace simu5g
{

  using namespace omnetpp;

  class XRReceiver : public cSimpleModule
  {
    inet::UdpSocket socket;

    ~XRReceiver() override;

    int emodel_Ie_;
    int emodel_Bpl_;
    int emodel_A_;
    double emodel_Ro_;

    typedef std::list<XRPacket *> PacketsList;
    PacketsList mPacketsList_;
    PacketsList mPlayoutQueue_;
    unsigned int mCurrentTalkspurt_;
    unsigned int mBufferSpace_;
    simtime_t mSamplingDelta_;
    simtime_t mPlayoutDelay_;

    bool mInit_;

    unsigned int totalRcvdBytes_;
    simtime_t warmUpPer_;

    static simsignal_t XRFrameLossSignal_;
    static simsignal_t XRFrameDelaySignal_;
    static simsignal_t XRPlayoutDelaySignal_;
    static simsignal_t XRMosSignal_;
    static simsignal_t XRTaildropLossSignal_;
    static simsignal_t XRPlayoutLossSignal_;
    static simsignal_t XRJitterSignal_;
    static simsignal_t XRReceivedThroughputSignal_;

    void finish() override;

  protected:
    int numInitStages() const override { return inet::NUM_INIT_STAGES; }
    void initialize(int stage) override;
    void handleMessage(cMessage *msg) override;
    double eModel(simtime_t delay, double loss);
    void playout(bool finish);
  };

} // namespace

#endif
