#ifndef __GNODEB_H_
#define __GNODEB_H_

#include <omnetpp.h>
#include <unordered_map>
#include <set>
#include "FrameMsg_m.h"

using namespace omnetpp;

class gNodeB : public cSimpleModule
{
  private:
    int numReceivers;
    simtime_t broadcastDelay;
    simtime_t ackTimeout;

    struct FrameState {
        FrameMsg *frameCopy;
        std::set<int> ackedReceivers;
        cMessage *timeoutEvent;
    };

    std::unordered_map<int, FrameState> frameTable; // key: frameId

  protected:
    virtual void initialize() override;
    virtual void handleMessage(cMessage *msg) override;
    void broadcastToAll(FrameMsg *msg);
    void handleAck(AckMsg *ack);
    void handleTimeout(cMessage *timeout);
    virtual void finish() override;
};

#endif
