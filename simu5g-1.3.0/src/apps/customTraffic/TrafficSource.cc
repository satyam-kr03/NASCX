#include <omnetpp.h>
#include <inet/applications/base/ApplicationBase.h>
#include <inet/common/socket/SocketMap.h>
#include <inet/transportlayer/contract/udp/UdpSocket.h>
#include <inet/networklayer/common/L3AddressResolver.h>
#include <inet/common/packet/chunk/ByteCountChunk.h>

using namespace omnetpp;
using namespace inet;
using namespace std;

namespace simu5g
{

    class TrafficSource : public ApplicationBase
    {
    private:
        cMessage *interval;
        cOutVector datastore;

        // Socket for sending data
        UdpSocket socket;
        L3Address destAddress;
        int destPort = 3000;
        int localPort = 3000;

        // Parameters
        double load, fps, data_rate, inter_frame_time, mean_pkt_size, pkt_size_sd, pkt_size_min, pkt_size_max;
        double jitter_mean = 0, jitter_sd = 2, jitter_min = -4, jitter_max = 4;
        int M, seed_val, frame_number = 1;

    protected:
        virtual void initialize(int stage) override;
        virtual void handleMessageWhenUp(cMessage *msg) override;
        double tran_gau_num(double, double, double, double);

        // ApplicationBase methods
        virtual void finish() override;
        virtual void handleStartOperation(LifecycleOperation *operation) override;
        virtual void handleStopOperation(LifecycleOperation *operation) override;
        virtual void handleCrashOperation(LifecycleOperation *operation) override;
    };

    Define_Module(TrafficSource);

    void TrafficSource::initialize(int stage)
    {
        ApplicationBase::initialize(stage);

        if (stage == INITSTAGE_LOCAL)
        {
            fps = par("fps").doubleValue();
            inter_frame_time = (double)1 / fps;
            data_rate = par("data_rate").doubleValue();
            mean_pkt_size = data_rate / fps; // In Mb/f
            pkt_size_sd = .105 * mean_pkt_size;
            pkt_size_min = .5 * mean_pkt_size;
            pkt_size_max = 1.5 * mean_pkt_size;

            // Create timer message
            interval = new cMessage("interval");
            seed_val = 0;
        }
        else if (stage == INITSTAGE_APPLICATION_LAYER)
        {
            // Setup UDP socket
            socket.setOutputGate(gate("socketOut"));
            const char *destAddressStr = par("destAddress");
            destAddress = L3AddressResolver().resolve(destAddressStr);
            destPort = par("destPort");
            localPort = par("localPort");

            socket.bind(localPort);

            // REMOVE THIS SCHEDULING - It will be done in handleStartOperation
            // double jitter = tran_gau_num(jitter_mean, jitter_sd, jitter_min, jitter_max);
            // double first_pkt_delay = fmax(jitter / 1000, 0);
            // scheduleAt(simTime() + first_pkt_delay, interval);
        }
    }

    void TrafficSource::handleMessageWhenUp(cMessage *msg)
    {
        if (msg == interval)
        {
            // Create packet
            auto packet = new Packet("data");
            double pkt_size_val_mb = tran_gau_num(mean_pkt_size, pkt_size_sd, pkt_size_min, pkt_size_max);
            double pkt_size_val_bytes = (pkt_size_val_mb * 1e6) / 8;
            int pkt_size_val = (int)pkt_size_val_bytes;

            // Create payload and set packet size
            auto payload = makeShared<ByteCountChunk>(B(pkt_size_val));
            packet->insertAtBack(payload);

            // Send packet
            socket.sendTo(packet, destAddress, destPort);

            // Schedule next packet
            double jitter = tran_gau_num(jitter_mean, jitter_sd, jitter_min, jitter_max);
            double intvl = frame_number * inter_frame_time + jitter / 1000;
            scheduleAt(simTime() + intvl, interval);
            frame_number = frame_number + 1;
        }
        else
        {
            delete msg;
        }
    }

    double TrafficSource::tran_gau_num(double mean, double sd, double min, double max)
    {
        double myrand = normal(mean, sd, seed_val);
        while (myrand < min || myrand > max)
        {
            myrand = normal(mean, sd, seed_val);
        }
        return (myrand);
    }

    void TrafficSource::finish()
    {
        ApplicationBase::finish();
    }

    void TrafficSource::handleStartOperation(LifecycleOperation *operation)
    {
        // Start sending packets
        double jitter = tran_gau_num(jitter_mean, jitter_sd, jitter_min, jitter_max);
        double first_pkt_delay = fmax(jitter / 1000, 0);
        scheduleAt(simTime() + first_pkt_delay, interval);
    }

    void TrafficSource::handleStopOperation(LifecycleOperation *operation)
    {
        // Stop sending packets
        cancelEvent(interval);
    }

    void TrafficSource::handleCrashOperation(LifecycleOperation *operation)
    {
        // Stop sending packets
        cancelEvent(interval);
    }

}