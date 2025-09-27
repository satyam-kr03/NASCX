#include "FrameSender.h"

#include <algorithm>
#include <fstream>
#include <sstream>
#include "FrameMsg_m.h"

Define_Module(FrameSender);

void FrameSender::initialize()
{
    gdfFile = par("gdfFile").stdstringValue();
    sendInterval = par("sendInterval");

    // Optional parameter (safe even if it's not declared in NED)
    if (hasPar("endWhenDone"))
        endWhenDone = par("endWhenDone").boolValue();
    else
        endWhenDone = true;  // default behavior

    // Register signals
    rttSignal = registerSignal("ackRTT");
    retransmitSignal = registerSignal("retransmitCount");
    dropSignal = registerSignal("droppedFrame");

    loadGDFFile();

    sendTimer = new cMessage("sendTimer");
    scheduleAt(simTime() + sendInterval, sendTimer);
}

void FrameSender::handleMessage(cMessage *msg)
{
    if (msg == sendTimer) {
        // --- EOF guard BEFORE sending ---
        if (currentIndex > lastFrameIndex) {
            stopSendingAtEof();
            return;
        }

        sendNextFrame();

        // Only reschedule if there are still rows left to consider
        if (currentIndex <= lastFrameIndex)
            scheduleAt(simTime() + sendInterval, sendTimer);
        else
            stopSendingAtEof();

        return;
    }

    // ACK handling
    if (auto *ack = dynamic_cast<AckMsg *>(msg)) {
        int frameId = ack->getFrameId();
        int receiverId = ack->getReceiverId();

        if (receiverId == -1) {
            EV_INFO << "ACK: Frame " << frameId << " was received by all UEs.\n";
            ackedFrames.insert(frameId);

            auto it = sentTimestamps.find(frameId);
            if (it != sentTimestamps.end()) {
                simtime_t rtt = simTime() - it->second;
                emit(rttSignal, rtt);
            }
        }
        else if (receiverId == -2) {
            EV_INFO << "Timeout for frame " << frameId << ". Attempting retransmission.\n";
            int retry = retryCount[frameId]++;
            if (retry < maxRetries) {
                emit(retransmitSignal, 1);
                auto it = std::find_if(frameList.begin(), frameList.end(),
                    [frameId](const FrameInfo& f) { return f.frameId == frameId; });

                if (it != frameList.end()) {
                    // Requeue the same frame right at currentIndex
                    frameList.insert(frameList.begin() + currentIndex, *it);
                    lastFrameIndex = static_cast<int>(frameList.size()) - 1; // list grew
                }
            } else {
                EV_INFO << "Frame " << frameId << " reached max retries. Dropping.\n";
                emit(dropSignal, 1);
            }
        }

        delete msg;
        return;
    }

    // Anything else
    delete msg;
}

void FrameSender::loadGDFFile()
{
    std::ifstream file(gdfFile);
    if (!file.is_open()) {
        EV_WARN << "Could not open GDF file: " << gdfFile << "\n";
        lastFrameIndex = -1; // nothing to send
        return;
    }

    std::string line;
    while (std::getline(file, line)) {
        if (line.empty())
            continue;

        std::istringstream ss(line);
        FrameInfo f;
        char comma;

        // Expecting: frameId,timestamp,mse,sendFlag,packetSize
        ss >> f.frameId >> comma
           >> f.timestamp >> comma
           >> f.mse >> comma
           >> f.sendFlag >> comma
           >> f.packetSize;

        frameList.push_back(f);
    }

    file.close();

    lastFrameIndex = static_cast<int>(frameList.size()) - 1;
    EV_INFO << "Loaded " << frameList.size() << " frames from GDF. lastFrameIndex=" << lastFrameIndex << "\n";
}

void FrameSender::sendNextFrame()
{
    if (currentIndex >= static_cast<int>(frameList.size()))
        return;

    FrameInfo &f = frameList[currentIndex++];

    if (!f.sendFlag) {
        EV_INFO << "Frame " << f.frameId << " marked as drop. Skipping.\n";
        return;
    }

    FrameMsg *packet = new FrameMsg();
    packet->setFrameId(f.frameId);
    packet->setTimestamp(simTime().dbl());  // store current sim time as "send time"
    packet->setMse(f.mse);
    packet->setSendFlag(f.sendFlag);
    packet->setSenderId(getId());
    packet->setPacketSize(f.packetSize);
    packet->setByteLength(f.packetSize);

    sentTimestamps[f.frameId] = simTime();  // for RTT calc

    EV_INFO << "Sending frame " << f.frameId << " to gNodeB.\n";
    send(packet, "out");
}

void FrameSender::stopSendingAtEof()
{
    EV_INFO << "Reached end of GDF (currentIndex=" << currentIndex
            << ", lastFrameIndex=" << lastFrameIndex << "). Stopping SourceUE timer.\n";

    if (sendTimer) {
        cancelEvent(sendTimer);
        delete sendTimer;
        sendTimer = nullptr;
    }

    if (endWhenDone)
        endSimulation();
}
