#include "ReceiverUE.h"

Define_Module(ReceiverUE);

void ReceiverUE::initialize() {
    FrameReceiver::initialize();  // delegate to base class
}

void ReceiverUE::handleMessage(cMessage *msg) {
    FrameReceiver::handleMessage(msg);  // delegate to base class
}
