#ifndef __FRAMERECEIVER_H_
#define __FRAMERECEIVER_H_

#include <omnetpp.h>
#include <fstream>
#include <string>
#include <unordered_set>

using namespace omnetpp;

class FrameReceiver : public cSimpleModule
{
  private:
    std::string logFile;
    std::ofstream logStream;
    int receiverId;
    std::unordered_set<int> receivedFrames;

    // Metrics
    simsignal_t delaySignal;
    simsignal_t throughputSignal;
    int bytesReceived = 0;

  protected:
    virtual void initialize() override;
    virtual void handleMessage(cMessage *msg) override;
    virtual void finish() override;
};

#endif
