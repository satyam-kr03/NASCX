#include <omnetpp.h>
#include <vector>
#include <math.h>
#include <fstream>
#include <iomanip>

using namespace omnetpp;
using namespace std;

class RRH : public cSimpleModule {
private:
    // Per-UE queues (front = head-of-line)
    vector<vector<double>> storesize_bits;        // remaining size of each packet in BITS (used by your scheduler)
    vector<vector<double>> storearrival_s;        // arrival time (seconds)
    vector<vector<long>>   storepktid;            // cMessage::getId() for each packet
    vector<vector<int>>    storeorig_bytes;       // original packet size in BYTES (for CSV)

    int mu = 3;
    double band = 100; // MHz
    double subcarrierspace = 15 * pow(2, mu); // kHz
    int numrb = (int)band * 1e3 / (12 * subcarrierspace);
    int p = 8;
    int numgroup = numrb / p;
    double bandwidth = subcarrierspace * 12 * p; // kHz

    double SINR1[16] = {0, -6.7, -4.7, -2.3, 0.2, 2.4, 4.3, 5.9, 8.1, 10.3, 11.7, 14.1, 16.3, 18.7, 21.0, 22.7};
    double SE1[16]   = {0, 0.15, 0.23, 0.38, 0.6, 0.88, 1.18, 1.48, 1.91, 2.41, 2.73, 3.32, 3.9, 4.52, 5.12, 5.55};
    double sigma1 = 1;
    double sigma21 = sigma1 * sigma1;

    double slottime;
    vector<pair<int, double>> allocations;
    cMessage *slot = nullptr;
    int numxr = 0;
    double fps = 0;
    double cycletime = 0;

    cStdDev delayrec;                 // existing mean delay stat (seconds)
    vector<int> flag;
    vector<double> avgThroughput;     // bits/slot EWMA

    // CSV logging
    //ofstream csv;
    //const double DELAY_BOUND_S = 0.010; // 10 ms

protected:
    virtual void initialize() override;
    virtual void handleMessage(cMessage *msg) override;
    void scheduleResources();
    double datarate2(double linkspeed);
    void logPacketRow(int user, long pktid, int size_bytes, double delay_s);
    virtual void finish() override;
};

Define_Module(RRH);

void RRH::initialize() {
    numxr = getParentModule()->par("numxr").intValue();
    fps = getParentModule()->getSubmodule("ts", 0)->par("fps").doubleValue();
    slottime = pow(2, -mu) * 1e-3;
    cycletime = 1 / fps;

    slot = new cMessage("slot");
    scheduleAt(simTime().dbl() + slottime, slot);

    storesize_bits.resize(numxr);
    storearrival_s.resize(numxr);
    storepktid.resize(numxr);
    storeorig_bytes.resize(numxr);

    flag.assign(numxr, 0);
    avgThroughput.assign(numxr, 1e-9);

    allocations.reserve(numgroup);
    for (int i = 0; i < numgroup; i++) {
        allocations.push_back(make_pair(-1, 0));
    }

    // Open CSV and write header
    //csv.open("rrh_packet_log.csv", ios::out);
    //csv << "user,packet_id,size_bytes,delay_ms,success\n";
    //csv.flush();
}

void RRH::handleMessage(cMessage *msg) {
    if (strcmp(msg->getName(), "data") == 0) {
        cPacket *pkt = check_and_cast<cPacket *>(msg);
        int index = pkt->getSenderModule()->getIndex();

        // Bookkeeping for logging and scheduling
        long id = pkt->getId();                            // unique message id in simulation
        int size_bytes = pkt->getByteLength();             // bytes for CSV
        double size_bits = pkt->getBitLength();            // bits for scheduler math

        storesize_bits[index].push_back(size_bits);
        storearrival_s[index].push_back(simTime().dbl());
        storepktid[index].push_back(id);
        storeorig_bytes[index].push_back(size_bytes);

        delete msg;
    } else if (msg == slot) {
        scheduleResources();
        scheduleAt(simTime().dbl() + slottime, slot);
    }
}

void RRH::scheduleResources() {
    for (int i = 0; i < numgroup; i++) {
        double maxMetric = 0;
        int maxind = -1;
        double maxrate_bits_per_slot = 0;

        for (int j = 0; j < numxr; j++) {
            if (!storesize_bits[j].empty()) {
                // datarate2 returns bits/s; convert to bits/slot by multiplying by slottime
                double bits_per_sec = datarate2(bandwidth * 1000); // bandwidth in Hz
                double bits_per_slot = bits_per_sec / (1000.0 * pow(2, mu)); // since slottime = 1e-3 * 2^-mu
                double head_delay_s = simTime().dbl() - storearrival_s[j].front();

                // Simple PF-style with delay awareness (kept your form)
                double metric = (bits_per_sec / avgThroughput[j]) / (head_delay_s + 1e-9);

                if (metric > maxMetric) {
                    maxMetric = metric;
                    maxind = j;
                    maxrate_bits_per_slot = bits_per_slot;
                }
            }
        }

        if (maxind != -1) {
            allocations[i] = make_pair(maxind, maxrate_bits_per_slot);
            flag[maxind] = 1;

            double transmitted_bits = 0.0;

            // Serve head-of-line packets until we exhaust the group's per-slot capacity
            while (!storesize_bits[maxind].empty() && transmitted_bits < maxrate_bits_per_slot) {
                double remaining_head = storesize_bits[maxind].front();
                double capacity_left = maxrate_bits_per_slot - transmitted_bits;

                if (remaining_head > capacity_left) {
                    // Partial transmit; update remaining bits on the head packet
                    storesize_bits[maxind].front() = remaining_head - capacity_left;
                    transmitted_bits = maxrate_bits_per_slot;
                } else {
                    // Packet fully transmitted this slot
                    transmitted_bits += remaining_head;

                    // Compute delay for this completed packet
                    double arrival_s = storearrival_s[maxind].front();
                    double delay_s = simTime().dbl() - arrival_s;

                    long pid = storepktid[maxind].front();
                    int size_bytes = storeorig_bytes[maxind].front();

                    // Record OMNeT++ scalar for mean delay (seconds)
                    delayrec.collect(delay_s);

                    // Log CSV row (delay bound check here)
                    //logPacketRow(maxind, pid, size_bytes, delay_s);

                    // Pop this packet from all queues
                    storesize_bits[maxind].erase(storesize_bits[maxind].begin());
                    storearrival_s[maxind].erase(storearrival_s[maxind].begin());
                    storepktid[maxind].erase(storepktid[maxind].begin());
                    storeorig_bytes[maxind].erase(storeorig_bytes[maxind].begin());
                }
            }

            // EWMA of served bits/slot
            avgThroughput[maxind] = 0.99 * avgThroughput[maxind] + 0.01 * transmitted_bits;
        }
    }
}

double RRH::datarate2(double linkspeed) {
    // linkspeed is Hz (bandwidth)
    double u = uniform(0, 1);
    double h = sqrt(-2.0 * sigma21 * log(u));
    double noise = -174 + 10 * log10(linkspeed);
    double sinr = 43 - 61.38 - 90 - noise; // as in your code
    sinr += 20 * log10(h);
    double x = linkspeed; // Hz

    // Map SINR to SE * bandwidth (bits/s)
    if (sinr <= -6.7)      return SE1[1]  * x;
    else if (sinr <= -4.7) return SE1[2]  * x;
    else if (sinr <= -2.3) return SE1[4]  * x;
    else if (sinr <= 0.2)  return SE1[5]  * x;
    else if (sinr <= 2.4)  return SE1[6]  * x;
    else if (sinr <= 4.3)  return SE1[7]  * x;
    else if (sinr <= 5.9)  return SE1[8]  * x;
    else if (sinr <= 8.1)  return SE1[9]  * x;
    else if (sinr <= 10.3) return SE1[10] * x;
    else if (sinr <= 11.7) return SE1[11] * x;
    else if (sinr <= 14.1) return SE1[12] * x;
    else if (sinr <= 16.3) return SE1[13] * x;
    else if (sinr <= 18.7) return SE1[14] * x;
    else if (sinr <= 21.0) return SE1[15] * x;
    return SE1[15] * x;
}

//void RRH::logPacketRow(int user, long pktid, int size_bytes, double delay_s) {
    // success = 1 if delay <= 10 ms, else 0
    //int success = (delay_s <= DELAY_BOUND_S) ? 1 : 0;
    //double delay_ms = delay_s * 1000.0;

    // Write CSV line
    // Use fixed with a reasonable precision for ms
    //csv << user << ","<< pktid << ","<< size_bytes << ","<< fixed << setprecision(6) << delay_ms << ","<< success << "\n";
    //csv.flush();
//}

void RRH::finish() {
    recordScalar("mean delay (s)", delayrec.getMean());
    EV << "mean delay (s) = " << delayrec.getMean() << endl;
    //if (csv.is_open()) csv.close();
}
