#include "inet/common/InitStages.h"
#include "inet/common/TimeTag_m.h"
#include "inet/common/packet/Packet.h"
#include "inet/common/packet/chunk/BytesChunk.h"
#include "inet/networklayer/common/L3AddressResolver.h"
#include "inet/transportlayer/contract/udp/UdpSocket.h"

#include <fstream>
#include <sstream>
#include <vector>
#include <algorithm>

using namespace inet;

class GdfUdpSourceApp : public cSimpleModule, public UdpSocket::ICallback
{
  protected:
    UdpSocket socket;
    std::string inputFile;
    L3Address destAddr;
    int destPort = 0;
    int localPort = -1;

    bool      stopWhenDone = true;
    simtime_t stopGrace = 0.2;

    struct Row { int frameId; simtime_t t; double mse; int send; int size; };
    std::vector<Row> plan;
    cMessage *tick = nullptr;
    cMessage *done = nullptr;

  protected:
    virtual int numInitStages() const override { return NUM_INIT_STAGES; }

    virtual void initialize(int stage) override {
        if (stage == INITSTAGE_LOCAL) {
            inputFile    = par("inputFile").stdstringValue();
            destPort     = par("destPort");
            localPort    = par("localPort");
            stopWhenDone = par("stopWhenDone");
            stopGrace    = par("stopGrace");
            tick = new cMessage("gdf-tick");
            done = new cMessage("gdf-done");
        }
        else if (stage == INITSTAGE_APPLICATION_LAYER) {
            const char *da = par("destAddr");
            if (!L3AddressResolver().tryResolve(da, destAddr))
                throw cRuntimeError("Cannot resolve destAddr='%s'", da);

            socket.setOutputGate(gate("socketOut"));
            socket.setCallback(this);
            socket.bind(localPort < 0 ? 0 : localPort);

            loadCsv();
            scheduleNext();

            // Hard stop at (last timestamp + grace) as a backup
            if (stopWhenDone && !plan.empty())
                scheduleAt(plan.back().t + stopGrace, done);
        }
    }

    void loadCsv() {
        std::ifstream f(inputFile);
        if (!f.is_open())
            throw cRuntimeError("Cannot open input GDF: %s", inputFile.c_str());

        std::string line;
        if (!std::getline(f, line))
            throw cRuntimeError("Empty GDF file: %s", inputFile.c_str());

        while (std::getline(f, line)) {
            if (line.empty()) continue;
            std::istringstream ss(line);
            std::string tok;
            Row r{};

            if (!std::getline(ss, tok, ',')) continue; r.frameId = std::stoi(tok);
            if (!std::getline(ss, tok, ',')) continue; r.t       = SimTime(std::stod(tok));
            if (!std::getline(ss, tok, ',')) continue; r.mse     = std::stod(tok);
            if (!std::getline(ss, tok, ',')) continue; r.send    = std::stoi(tok);
            if (!std::getline(ss, tok, ',')) continue; r.size    = std::stoi(tok);

            if (r.send && r.size > 0)
                plan.push_back(r);
        }
        std::sort(plan.begin(), plan.end(),
                  [](const Row& a, const Row& b){ return a.t < b.t; });
        EV_INFO << "GdfUdpSourceApp: " << plan.size() << " rows to send\n";
        EV_INFO << "GDF last timestamp = " << (plan.empty()? SimTime(-1) : plan.back().t) << "\n"; // breadcrumb
    }

    void scheduleNext() {
        if (!plan.empty())
            scheduleAt(plan.front().t, tick);
    }

    void sendOne(const Row& r) {
        auto name = std::string("GdfFrame-") + std::to_string(r.frameId);
        auto *pk = new Packet(name.c_str());
        auto bytes = std::vector<uint8_t>(r.size, 0);
        pk->insertAtBack(makeShared<BytesChunk>(bytes));
        pk->addTag<CreationTimeTag>()->setCreationTime(simTime());
        socket.sendTo(pk, destAddr, destPort);
    }

    virtual void handleMessage(cMessage *msg) override {
        if (msg == tick) {
            if (plan.empty()) return;
            Row r = plan.front();
            plan.erase(plan.begin());
            sendOne(r);
            if (plan.empty()) {
                if (stopWhenDone && !done->isScheduled()) {
                    EV_INFO << "All rows sent; ending at " << (simTime()+stopGrace) << "\n"; // breadcrumb
                    scheduleAt(simTime() + stopGrace, done);
                }
            } else {
                scheduleNext();
            }
        }
        else if (msg == done) {
            endSimulation();
        }
        else {
            socket.processMessage(msg);
        }
    }

    // UdpSocket::ICallback
    virtual void socketDataArrived(UdpSocket*, Packet*) override {}
    virtual void socketErrorArrived(UdpSocket*, Indication*) override {}
    virtual void socketClosed(UdpSocket*) override {}

    virtual void finish() override {
        cancelAndDelete(tick);
        cancelAndDelete(done);
    }
};

Define_Module(GdfUdpSourceApp);
