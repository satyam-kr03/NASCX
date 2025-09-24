#ifndef __RECEIVERUE_H_
#define __RECEIVERUE_H_

#include "FrameReceiver.h"

class ReceiverUE : public FrameReceiver
{
  protected:
    virtual void initialize() override;
    virtual void handleMessage(cMessage *msg) override;
};

#endif
