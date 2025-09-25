#include <omnetpp.h>
#include <fstream>
#include <sstream>
#include <vector>
#include <string>

using namespace omnetpp;
using namespace std;

struct FrameInfo {
    int size_bytes;   // packet size in bytes (from userX.csv)
    double mse;       // mse value (from mse_userX.csv)
};

class TrafficSource : public cSimpleModule
{
private:
    cMessage *interval;
    vector<FrameInfo> frames;

    // --- Jitter ---
    double jitter_mean = 0;   // ms
    double jitter_sd   = 2;   // ms
    double jitter_min  = -4;  // ms
    double jitter_max  = 4;   // ms
    int    seed_val    = 0;   // RNG seed for normal()

    int frame_number = 0;
    double fps = 60.0;  // fixed FPS

protected:
    virtual void initialize() override;
    virtual void handleMessage(cMessage *msg) override;
    void loadCSVs(const string& sizeFile, const string& mseFile);

    // truncated Gaussian in milliseconds (same as old)
    double tran_gau_num(double mean, double sd, double minv, double maxv);
};

Define_Module(TrafficSource);

void TrafficSource::initialize()
{
    // Build filenames from module index: userN.csv and mse_userN.csv
    int idx = getIndex();
    string sizeFile = string("user") + to_string(idx) + ".csv";       // packet sizes (bytes)
    string mseFile  = string("mse_user") + to_string(idx) + ".csv";   // mse values

    loadCSVs(sizeFile, mseFile);

    interval = new cMessage("interval");

    if (!frames.empty()) {
        // First send at (1/fps) + jitter(ms)/1000  — jitter added like in old logic
        double jitter_ms = tran_gau_num(jitter_mean, jitter_sd, jitter_min, jitter_max);
        double sendTime  = (1.0 / fps) + (jitter_ms / 1000.0);
        scheduleAt(sendTime, interval);
    }
}

void TrafficSource::handleMessage(cMessage *msg)
{
    if (strcmp(msg->getName(), "interval") == 0)
    {
        cancelEvent(interval);

        if (frame_number < (int)frames.size()) {
            // Create packet
            cPacket *t = new cPacket("data");
            t->setByteLength(frames[frame_number].size_bytes);  // size already in BYTES
            t->addPar("mse") = frames[frame_number].mse;
            t->addPar("genTime") = simTime().dbl();

            send(t, "torrh");

            // Schedule next with jitter added to nominal (k+1)/fps time
            frame_number++;
            if (frame_number < (int)frames.size()) {
                double jitter_ms = tran_gau_num(jitter_mean, jitter_sd, jitter_min, jitter_max);
                // Nominal time for next frame is (frame_number+1)/fps, then add jitter
                double nextNominal = (frame_number + 1) * (1.0 / fps);
                double sendTime    = nextNominal + (jitter_ms / 1000.0);
                scheduleAt(sendTime, interval);
            }
        }
    }
}

double TrafficSource::tran_gau_num(double mean, double sd, double minv, double maxv)
{
    // Truncated Gaussian
    double x = normal(mean, sd, seed_val);
    while (x < minv || x > maxv) {
        x = normal(mean, sd, seed_val);
    }
    return x;
}

void TrafficSource::loadCSVs(const string& sizeFile, const string& mseFile)
{
    // Read sizes (bytes)
    vector<int> sizes;
    {
        ifstream f(sizeFile);
        string line;
        while (getline(f, line)) {
            if (line.empty()) continue;
            sizes.push_back(stoi(line));
        }
    }

    // Read MSEs
    vector<double> mses;
    {
        ifstream f(mseFile);
        string line;
        while (getline(f, line)) {
            if (line.empty()) continue;
            mses.push_back(stod(line));
        }
    }

    // Pair by the common length (min)
    size_t n = min(sizes.size(), mses.size());
    frames.reserve(n);
    for (size_t i = 0; i < n; ++i) {
        FrameInfo fi;
        fi.size_bytes = sizes[i];
        fi.mse = mses[i];
        frames.push_back(fi);
    }
}
