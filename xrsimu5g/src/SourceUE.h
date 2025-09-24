#ifndef __SOURCEUE_H_
#define __SOURCEUE_H_

#include "FrameSender.h"

class SourceUE : public FrameSender
{
  protected:
    virtual void initialize() override;
    virtual void handleMessage(cMessage *msg) override;
};

#endif
