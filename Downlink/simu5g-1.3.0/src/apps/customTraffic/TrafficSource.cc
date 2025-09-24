
#include <omnetpp.h>

using namespace omnetpp;
using namespace std;

class TrafficSource : public cSimpleModule
{
private:
    cMessage *interval;
    cOutVector datastore;

    // Parameters
    double load, fps, data_rate, inter_frame_time, mean_pkt_size, pkt_size_sd, pkt_size_min, pkt_size_max;
    double jitter_mean = 0, jitter_sd = 2, jitter_min = -4, jitter_max = 4;
    int M, seed_val, frame_number = 1;

protected:
    virtual void initialize();
    virtual void handleMessage(cMessage *msg);
    double tran_gau_num(double, double, double, double);
};
Define_Module(TrafficSource);
void TrafficSource::initialize()
{
    //    seed_val=intuniform(0, 10);
    seed_val = 0;
    //    M = (int)par("num_tr_onu");
    //    load=par("load").doubleValue()/M;
    fps = par("fps").doubleValue();
    inter_frame_time = (double)1 / fps;
    data_rate = par("data_rate").doubleValue();
    mean_pkt_size = data_rate / fps; // In Mb/f
    pkt_size_sd = .105 * mean_pkt_size;
    pkt_size_min = .5 * mean_pkt_size;
    pkt_size_max = 1.5 * mean_pkt_size;
    interval = new cMessage("interval");
    double jitter = tran_gau_num(jitter_mean, jitter_sd, jitter_min, jitter_max);
    double first_pkt_delay = fmax(jitter / 1000, 0);
    // cout<<"interval="<<inter_frame_time<<"jitter="<<jitter<<"first_pkt_delay="<<first_pkt_delay<<endl;
    scheduleAt(simTime() + first_pkt_delay, interval);
}

void TrafficSource ::handleMessage(cMessage *msg)
{

    if (strcmp(msg->getName(), "interval") == 0)
    {
        cancelEvent(interval);
        // EV<<"interval \t"<<intvl<<" \t Off \t "<<xoff<<"\n";
        // szval=uniform(1,1500);
        cPacket *t = new cPacket("data");
        //        data_msg *t = new data_msg("data");

        double pkt_size_val_mb = tran_gau_num(mean_pkt_size, pkt_size_sd, pkt_size_min, pkt_size_max);
        // cout<<endl<<"=================================packet_size="<<pkt_size_val_mb<<endl;
        double pkt_size_val_double = (pkt_size_val_mb * 1e6) / 8;

        // cout<<"packet_size_val="<<pkt_size_val_double<<endl;
        int pkt_size_val = (int)pkt_size_val_double;
        t->setByteLength(pkt_size_val);
        //        t->setPktsize(pkt_size_val);
        //        t->setXr_Id(getIndex());
        // t->setSize(12000);///link
        // loadind=loadind+1;
        // datastore.record(loadind);
        send(t, "torrh");
        //        cout<<"packet sent from "<<getIndex()<<endl;
        // EV<<intvl;
        double jitter = tran_gau_num(jitter_mean, jitter_sd, jitter_min, jitter_max);
        double intvl = frame_number * inter_frame_time + jitter / 1000;
        // cout<<"pkt_size_val:"<<pkt_size_val<<"   "<<"interval:"<<intvl<<endl;
        // cout<<"intvl="<<intvl;
        scheduleAt(intvl, interval);
        frame_number = frame_number + 1;
    }
    else
    {
    }
}

double TrafficSource ::tran_gau_num(double mean, double sd, double min, double max)
{

    double myrand = normal(mean, sd, seed_val);
    while (myrand < min || myrand > max)
    {
        myrand = normal(mean, sd, seed_val);
    }
    return (myrand);
}
