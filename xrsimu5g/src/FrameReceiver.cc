#include "FrameReceiver.h"

#include "FrameMsg_m.h"

Define_Module(FrameReceiver);

void FrameReceiver::initialize()
{
    logFile = par("logFile").stdstringValue();
    receiverId = par("id");

    logStream.open(logFile);
    if (!logStream.is_open()) {
        EV << "Failed to open log file: " << logFile << "\n";
    } else {
        logStream << "frameId,timestamp,mse,receivedFlag\n";
    }

    delaySignal = registerSignal("frameDelay");
    throughputSignal = registerSignal("throughput");
}

void FrameReceiver::handleMessage(cMessage *msg)
{
    FrameMsg *pkt = check_and_cast<FrameMsg *>(msg);
    int frameId = pkt->getFrameId();

    if (receivedFrames.find(frameId) != receivedFrames.end()) {
        EV << "Duplicate frame " << frameId << " received. Ignoring.\n";
        delete pkt;
        return;
    }

    // Simulate packet loss
    if (uniform(0, 1) < 0.01) {
        EV << "Simulated drop for frame " << frameId << "\n";
        delete pkt;
        return;
    }

    receivedFrames.insert(frameId);

    simtime_t delay = simTime() - pkt->getTimestamp();
    emit(delaySignal, delay);

    bytesReceived += pkt->getPacketSize();
    emit(throughputSignal, bytesReceived / simTime().dbl()); // Throughput estimate

    if (logStream.is_open()) {
        logStream << frameId << ","
                  << pkt->getTimestamp() << ","
                  << pkt->getMse() << ","
                  << "1\n";
    }

    AckMsg *ack = new AckMsg();
    ack->setFrameId(frameId);
    ack->setReceiverId(receiverId);

    send(ack, "out");
    delete pkt;
}

void FrameReceiver::finish()
{
    if (logStream.is_open())
        logStream.close();
}
