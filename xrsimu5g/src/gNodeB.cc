#include "gNodeB.h"

#include "FrameMsg_m.h"

Define_Module(gNodeB);

void gNodeB::initialize()
{
    numReceivers = par("numReceivers");
    broadcastDelay = par("broadcastDelay");
    ackTimeout = par("ackTimeout");
}

void gNodeB::handleMessage(cMessage *msg)
{
    if (msg->isSelfMessage()) {
        handleTimeout(msg);
    } else if (dynamic_cast<FrameMsg *>(msg)) {
        FrameMsg *frame = check_and_cast<FrameMsg *>(msg);
        int frameId = frame->getFrameId();

        // Keep a copy of the frame for potential retransmission
        FrameState state;
        state.frameCopy = frame->dup();
        state.timeoutEvent = new cMessage(("timeout-" + std::to_string(frameId)).c_str());
        frameTable[frameId] = state;

        // Schedule timeout
        scheduleAt(simTime() + ackTimeout, state.timeoutEvent);

        // Broadcast to all receivers
        broadcastToAll(frame);
        delete frame;

    } else if (dynamic_cast<AckMsg *>(msg)) {
        AckMsg *ack = check_and_cast<AckMsg *>(msg);
        handleAck(ack);
    } else {
        EV << "Unknown message received at gNodeB.\n";
        delete msg;
    }
}

void gNodeB::broadcastToAll(FrameMsg *msg)
{
    for (int i = 0; i < numReceivers; ++i) {
        FrameMsg *copy = msg->dup();
        sendDelayed(copy, broadcastDelay, "out", i);
    }
}

void gNodeB::handleAck(AckMsg *ack)
{
    int frameId = ack->getFrameId();
    int recvId = ack->getReceiverId();

    auto it = frameTable.find(frameId);
    if (it != frameTable.end()) {
        FrameState &state = it->second;
        state.ackedReceivers.insert(recvId);

        // If all receivers have ACKed
        if (state.ackedReceivers.size() == (size_t)numReceivers) {
            EV << "All ACKs received for frame " << frameId << ". Informing source UE.\n";

            // Send ACK summary to source
            AckMsg *summaryAck = new AckMsg();
            summaryAck->setFrameId(frameId);
            summaryAck->setReceiverId(-1); // -1 to denote gNodeB → source
            send(summaryAck, "ackOut");

            // Cancel timeout and clean up
            cancelAndDelete(state.timeoutEvent);
            delete state.frameCopy;
            frameTable.erase(it);
        }
    }

    delete ack;
}

void gNodeB::handleTimeout(cMessage *timeout)
{
    int frameId = -1;

    // Find which frame this timeout belongs to
    for (auto it = frameTable.begin(); it != frameTable.end(); ++it) {
        if (it->second.timeoutEvent == timeout) {
            frameId = it->first;
            break;
        }
    }

    if (frameId == -1) {
        EV << "Unknown timeout event.\n";
        delete timeout;
        return;
    }

    EV << "ACK timeout for frame " << frameId << ". Triggering retransmission or notifying source.\n";

    // Send failure to source (could also resend later)
    AckMsg *failAck = new AckMsg();
    failAck->setFrameId(frameId);
    failAck->setReceiverId(-2); // -2 to denote timeout
    send(failAck, "ackOut");

    // Clean up
    delete frameTable[frameId].frameCopy;
    delete timeout;
    frameTable.erase(frameId);
}

void gNodeB::finish()
{
    for (auto &entry : frameTable) {
        cancelAndDelete(entry.second.timeoutEvent);
        delete entry.second.frameCopy;
    }
    frameTable.clear();
}
