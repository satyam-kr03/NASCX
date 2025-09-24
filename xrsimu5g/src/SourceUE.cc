#include "SourceUE.h"

Define_Module(SourceUE);

void SourceUE::initialize() {
    FrameSender::initialize();  // call base class initialization
}

void SourceUE::handleMessage(cMessage *msg) {
    FrameSender::handleMessage(msg);  // delegate to base class logic
}
