#include "inet/common/InitStages.h"
#include "inet/common/TimeTag_m.h"
#include "inet/common/packet/Packet.h"
#include "inet/transportlayer/contract/udp/UdpSocket.h"

#include <fstream>
#include <regex>

using namespace inet;

class GdfUdpSinkApp : public cSimpleModule, public UdpSocket::ICallback
{
  protected:
    UdpSocket socket;
    std::string outputFile;
    int localPort = 0;
    std::ofstream out;
    std::regex nameRe{R"(GdfFrame-(\d+))"};

    // Optional idle-stop
    bool      stopWhenIdle = false;
    simtime_t idleGrace = 0.5;
    cMessage *done = nullptr;

    virtual int numInitStages() const override { return NUM_INIT_STAGES; }

    virtual void initialize(int stage) override {
        if (stage == INITSTAGE_LOCAL) {
            outputFile   = par("outputFile").stdstringValue();
            localPort    = par("localPort");
            stopWhenIdle = par("stopWhenIdle");
            idleGrace    = par("idleGrace");
            done = new cMessage("sink-idle-done");
        }
        else if (stage == INITSTAGE_APPLICATION_LAYER) {
            out.open(outputFile, std::ios::out | std::ios::trunc);
            if (!out.is_open())
                throw cRuntimeError("Cannot open output file: %s", outputFile.c_str());
            out << "frameId,timestamp,bytes,latencyMs\n";

            socket.setOutputGate(gate("socketOut"));
            socket.setCallback(this);
            socket.bind(localPort);

            if (stopWhenIdle) {
                // Start idle timer; will be pushed out on each arrival
                scheduleAt(simTime() + idleGrace, done);
            }
        }
    }

    virtual void handleMessage(cMessage *msg) override {
        if (msg == done) {
            EV_INFO << "Sink idle for " << idleGrace << ", ending simulation\n";
            endSimulation();
            return;
        }
        socket.processMessage(msg);
    }

    // UdpSocket::ICallback
    virtual void socketDataArrived(UdpSocket *, Packet *pk) override {
        int frameId = -1;
        std::cmatch m;
        if (std::regex_search(pk->getName(), m, nameRe))
            frameId = std::stoi(m[1]);

        auto ct = pk->findTag<CreationTimeTag>(); // Ptr<const CreationTimeTag>
        simtime_t latency = ct ? (simTime() - ct->getCreationTime()) : SIMTIME_ZERO;

        out << frameId << "," << simTime() << ","
            << (int)pk->getByteLength() << ","
            << (latency.dbl()*1000.0) << "\n";

        // Bump idle timer
        if (stopWhenIdle) {
            if (done->isScheduled())
                cancelEvent(done);
            scheduleAt(simTime() + idleGrace, done);
        }

        delete pk;
    }

    virtual void socketErrorArrived(UdpSocket*, Indication*) override {}
    virtual void socketClosed(UdpSocket*) override {}

    virtual void finish() override {
        if (done) {
            cancelAndDelete(done);
            done = nullptr;
        }
        if (out.is_open()) out.close();
    }
};

Define_Module(GdfUdpSinkApp);
