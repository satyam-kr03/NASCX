//
//                  Simu5G
//
// Authors: Giovanni Nardini, Giovanni Stea, Antonio Virdis (University of Pisa)
//
// This file is part of a software released under the license included in file
// "license.pdf". Please read LICENSE and README files before using it.
// The above files and the present reference are part of the software itself,
// and cannot be removed from it.
//

#include "apps/xr/XRReceiver.h"

namespace simu5g
{

    Define_Module(XRReceiver);

    using namespace std;
    using namespace inet;

    simsignal_t XRReceiver::XRFrameLossSignal_ = registerSignal("XRFrameLoss");
    simsignal_t XRReceiver::XRFrameDelaySignal_ = registerSignal("XRFrameDelay");
    simsignal_t XRReceiver::XRPlayoutDelaySignal_ = registerSignal("XRPlayoutDelay");
    simsignal_t XRReceiver::XRMosSignal_ = registerSignal("XRMos");
    simsignal_t XRReceiver::XRTaildropLossSignal_ = registerSignal("XRTaildropLoss");
    simsignal_t XRReceiver::XRJitterSignal_ = registerSignal("XRJitter");
    simsignal_t XRReceiver::XRPlayoutLossSignal_ = registerSignal("XRPlayoutLoss");
    simsignal_t XRReceiver::XRReceivedThroughputSignal_ = registerSignal("XRReceivedThroughput");

    XRReceiver::~XRReceiver()
    {
        while (!mPlayoutQueue_.empty())
        {
            delete mPlayoutQueue_.front();
            mPlayoutQueue_.pop_front();
        }

        while (!mPacketsList_.empty())
        {
            delete mPacketsList_.front();
            mPacketsList_.pop_front();
        }
    }

    void XRReceiver::initialize(int stage)
    {
        if (stage != inet::INITSTAGE_APPLICATION_LAYER)
            return;

        emodel_Ie_ = par("emodel_Ie_");
        emodel_Bpl_ = par("emodel_Bpl_");
        emodel_A_ = par("emodel_A_");
        emodel_Ro_ = par("emodel_Ro_");

        mBufferSpace_ = par("dim_buffer");
        mSamplingDelta_ = par("sampling_time");
        mPlayoutDelay_ = par("playout_delay");

        mInit_ = true;

        int port = par("localPort");
        EV << "XRReceiver::initialize - binding to port: local:" << port << endl;
        if (port != -1)
        {
            socket.setOutputGate(gate("socketOut"));
            socket.bind(port);
        }

        totalRcvdBytes_ = 0;
        warmUpPer_ = getSimulation()->getWarmupPeriod();
    }

    void XRReceiver::handleMessage(cMessage *msg)
    {
        if (msg->isSelfMessage())
            return;

        Packet *pPacket = check_and_cast<Packet *>(msg);

        // read XR header
        auto XRHeader = pPacket->popAtFront<XRPacket>();

        if (mInit_)
        {
            mCurrentTalkspurt_ = XRHeader->getIDtalk();
            mInit_ = false;
        }

        if (mCurrentTalkspurt_ != XRHeader->getIDtalk())
        {
            playout(false);
            mCurrentTalkspurt_ = XRHeader->getIDtalk();
        }

        EV << "XRReceiver::handleMessage - Packet received: TALK[" << XRHeader->getIDtalk() << "] - FRAME[" << XRHeader->getIDframe() << " size: " << XRHeader->getChunkLength() << " bytes]\n";

        // emit throughput sample
        totalRcvdBytes_ += (int)B(XRHeader->getChunkLength()).get();
        double interval = SIMTIME_DBL(simTime() - warmUpPer_);
        if (interval > 0.0)
        {
            double tputSample = (double)totalRcvdBytes_ / interval;
            emit(XRReceivedThroughputSignal_, tputSample);
        }

        // emit frame delay
        simtime_t arrivalTime = simTime();
        double sample = SIMTIME_DBL(arrivalTime - XRHeader->getPayloadTimestamp());
        emit(XRFrameDelaySignal_, sample);

        auto packetToBeQueued = XRHeader->dup();
        packetToBeQueued->setArrivalTime(arrivalTime);
        mPacketsList_.push_back(packetToBeQueued);

        delete pPacket;
    }

    void XRReceiver::playout(bool finish)
    {
        if (mPacketsList_.empty())
            return;

        double sample;

        XRPacket *pPacket = mPacketsList_.front();

        simtime_t firstPlayoutTime = pPacket->getArrivalTime() + mPlayoutDelay_;
        unsigned int n_frames = pPacket->getNframes();
        unsigned int playoutLoss = 0;
        unsigned int tailDropLoss = 0;
        unsigned int channelLoss;

        if (finish)
        {
            unsigned int maxId = 0;
            for (const auto &packet : mPacketsList_)
                maxId = std::max(maxId, packet->getIDframe());
            channelLoss = maxId + 1 - mPacketsList_.size();
        }
        else
            channelLoss = pPacket->getNframes() - mPacketsList_.size();

        sample = ((double)channelLoss / (double)n_frames);
        emit(XRFrameLossSignal_, sample);

        // Vector for managing duplicates
        std::vector<bool> isArrived;
        isArrived.resize(n_frames, false);

        simtime_t last_jitter = 0.0;
        simtime_t max_jitter = -1000.0;

        while (!mPacketsList_.empty())
        {
            pPacket = mPacketsList_.front();

            unsigned int IDframe = pPacket->getIDframe();

            pPacket->setPlayoutTime(firstPlayoutTime + IDframe * mSamplingDelta_);

            last_jitter = pPacket->getArrivalTime() - pPacket->getPlayoutTime();
            max_jitter = std::max(max_jitter, last_jitter);

            // avoid printing during finish (as it will print to the standard output)
            if (!finish)
                EV << "XRReceiver::playout - Jitter measured: " << last_jitter << " TALK[" << pPacket->getIDtalk() << "] - FRAME[" << IDframe << "]\n";

            if (IDframe < n_frames)
            {
                // Duplicates management
                if (isArrived[IDframe])
                {
                    // avoid printing during finish (as it will print to the standard output)
                    if (!finish)
                        EV << "XRReceiver::playout - Duplicated Packet: TALK[" << pPacket->getIDtalk() << "] - FRAME[" << IDframe << "]\n";
                    delete pPacket;
                }
                else if (last_jitter > 0.0)
                {
                    ++playoutLoss;
                    // avoid printing during finish (as it will print to the standard output)
                    if (!finish)
                        EV << "XRReceiver::playout - out of time packet deleted: TALK[" << pPacket->getIDtalk() << "] - FRAME[" << IDframe << "]\n";
                    emit(XRJitterSignal_, last_jitter);
                    delete pPacket;
                }
                else
                {
                    while (!mPlayoutQueue_.empty() && pPacket->getArrivalTime() > mPlayoutQueue_.front()->getPlayoutTime())
                    {
                        ++mBufferSpace_;
                        delete mPlayoutQueue_.front();
                        mPlayoutQueue_.pop_front();
                    }

                    if (mBufferSpace_ > 0)
                    {
                        // avoid printing during finish (as it will print to the standard output)
                        if (!finish)
                        {
                            EV << "XRReceiver::playout - Sampleable packet inserted into buffer: TALK[" << pPacket->getIDtalk() << "] - FRAME[" << IDframe
                               << "] - arrival time[" << pPacket->getArrivalTime() << "] -  sampling time[" << pPacket->getPlayoutTime() << "]\n";
                        }
                        --mBufferSpace_;

                        // duplicates management
                        isArrived[IDframe] = true;

                        mPlayoutQueue_.push_back(pPacket);
                    }
                    else
                    {
                        ++tailDropLoss;
                        // avoid printing during finish (as it will print to the standard output)
                        if (!finish)
                        {
                            EV << "XRReceiver::playout - Buffer is full, discarding packet: TALK[" << pPacket->getIDtalk() << "] - FRAME["
                               << IDframe << "] - arrival time[" << pPacket->getArrivalTime() << "]\n";
                        }
                        delete pPacket;
                    }
                }
            }

            mPacketsList_.pop_front();
        }

        double proportionalLoss = ((double)tailDropLoss + (double)playoutLoss + (double)channelLoss) / (double)n_frames;
        // avoid printing during finish (as it will print to the standard output)
        if (!finish)
        {
            EV << "XRReceiver::playout - proportionalLoss " << proportionalLoss << "(tailDropLoss=" << tailDropLoss << " - playoutLoss="
               << playoutLoss << " - channelLoss=" << channelLoss << ")\n\n";
        }

        double mos = eModel(mPlayoutDelay_, proportionalLoss);
        emit(XRPlayoutDelaySignal_, mPlayoutDelay_);

        sample = ((double)playoutLoss / (double)n_frames);
        emit(XRPlayoutLossSignal_, sample);

        sample = mos;
        emit(XRMosSignal_, sample);

        sample = ((double)tailDropLoss / (double)n_frames);
        emit(XRTaildropLossSignal_, sample);

        // avoid printing during finish (as it will print to the standard output)
        if (!finish)
        {
            EV << "XRReceiver::playout - Computed MOS: eModel( " << mPlayoutDelay_ << " , " << tailDropLoss << "+" << playoutLoss << "+"
               << channelLoss << " ) = " << mos << "\n";

            EV << "XRReceiver::playout - Playout Delay Adaptation \n"
               << "\t Old Playout Delay: " << mPlayoutDelay_ << "\n\t Max Jitter Measured: "
               << max_jitter << "\n\n";
        }

        mPlayoutDelay_ += max_jitter;
        if (mPlayoutDelay_ < 0.0)
            mPlayoutDelay_ = 0.0;
        // avoid printing during finish (as it will print to the standard output)
        if (!finish)
            EV << "\t New Playout Delay: " << mPlayoutDelay_ << "\n\n";
    }

    double XRReceiver::eModel(simtime_t delay, double loss)
    {
        double delayms = 1000 * SIMTIME_DBL(delay);

        // Compute the Id parameter
        int u = ((delayms - 177.3) > 0 ? 1 : 0);
        double id = 0.0;
        id = 0.024 * delayms + 0.11 * (delayms - 177.3) * u;

        // Packet loss p in %
        double p = loss * 100;
        // Compute the Ie,eff parameter
        double ie_eff = emodel_Ie_ + (95 - emodel_Ie_) * p / (p + emodel_Bpl_);

        // Compute the R factor
        double Rfactor = emodel_Ro_ - id - ie_eff + emodel_A_;

        // Compute the MOS value
        double mos = 0.0;

        if (Rfactor < 0)
        {
            mos = 1.0;
        }
        else if (Rfactor > 100)
        {
            mos = 4.5;
        }
        else
        {
            mos = 1 + 0.035 * Rfactor + 7 * pow(10, (double)-6) * Rfactor * (Rfactor - 60) * (100 - Rfactor);
        }

        mos = (mos < 1) ? 1 : mos;

        return mos;
    }

    void XRReceiver::finish()
    {
        // last talkspurt playout
        playout(true);
    }

} // namespace
