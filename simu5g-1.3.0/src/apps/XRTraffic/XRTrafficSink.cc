#include <omnetpp.h>
#include <inet/applications/base/ApplicationBase.h>
#include <inet/transportlayer/contract/udp/UdpSocket.h>
#include <inet/common/TimeTag.h>
#include <inet/common/SequenceNumberTag_m.h>
#include <map>

using namespace omnetpp;
using namespace inet;

// A simple struct to hold information about frames being received
struct FrameInfo
{
    simtime_t creationTime;
    int packetsReceived = 0;
    int totalPackets = 0; // You'll need to figure out how to get this
    double rmse = 0.0;    // The RMSE value for this frame
};

namespace simu5g
{

    class XRTrafficSink : public ApplicationBase
    {
    private:
        UdpSocket socket;
        const int FRAME_ID_MULTIPLIER = 10000; // Same as in the source

        // Buffer to hold frames that are being reassembled
        std::map<int, FrameInfo> frameBuffer;

        // Statistics
        cOutVector meanErrorVector;
        double cumulativeRmse = 0.0;
        int totalFramesMissed = 0;
        int totalFramesReceived = 0;

        cHistogram frameDelayHistogram;

    protected:
        virtual void initialize(int stage) override;
        virtual void handleMessageWhenUp(cMessage *msg) override;
        virtual void finish() override;

        // Implement required pure virtual methods from ApplicationBase
        virtual void handleStartOperation(LifecycleOperation *operation) override {}
        virtual void handleStopOperation(LifecycleOperation *operation) override {}
        virtual void handleCrashOperation(LifecycleOperation *operation) override {}
    };

    Define_Module(XRTrafficSink);

    void XRTrafficSink::initialize(int stage)
    {
        ApplicationBase::initialize(stage);

        if (stage == INITSTAGE_APPLICATION_LAYER)
        {
            meanErrorVector.setName("meanError");
            frameDelayHistogram.setName("frameDelay");

            int localPort = par("localPort");
            socket.setOutputGate(gate("socketOut"));
            socket.bind(localPort);
        }
    }

    void XRTrafficSink::handleMessageWhenUp(cMessage *msg)
    {
        // 1. Cast the message to a Packet
        Packet *packet = check_and_cast<Packet *>(msg);

        // 2. Extract metadata from the packet's tags
        //    - CreationTimeTag for the timestamp
        //    - SequenceNumberInd for the combined Frame ID and Sequence Number
        auto creationTimeTag = packet->findTag<CreationTimeTag>();
        auto sequenceTag = packet->findTag<SequenceNumberInd>();

        // 3. Decode the Frame ID and Sequence Number from the combined value
        int combinedSeq = sequenceTag ? sequenceTag->getSequenceNumber() : -1;
        int frameId = combinedSeq / FRAME_ID_MULTIPLIER;
        int seqNum = combinedSeq % FRAME_ID_MULTIPLIER;
        simtime_t creationTime = creationTimeTag ? creationTimeTag->getCreationTime() : SIMTIME_ZERO;
        EV << "Received packet for FrameID=" << frameId << ", SeqNum=" << seqNum << ", CreationTime=" << creationTime << endl;

        // 4. Update the frameBuffer
        //    - If this is the first packet for a new frame, create an entry in the map.
        //    - Increment the packetsReceived count for that frame.
        //    - Store the creationTime and RMSE (you'll need to add RMSE to the source).
        FrameInfo &frame = frameBuffer[frameId];
        if (frame.packetsReceived == 0)
        {
            frame.creationTime = creationTime;
            frame.rmse = par("rmsePerFrame");            // You need to set this parameter in the source
            frame.totalPackets = par("packetsPerFrame"); // You need to set this parameter in the source
        }
        frame.packetsReceived++;
        EV << "FrameID=" << frameId << " now has " << frame.packetsReceived << " packets received." << endl;

        // 5. Check if the frame is complete
        //    - This is the tricky part. How do you know the total number of packets?
        //      You might need to send this value from the source as well.
        //    - If (packetsReceived == totalPacketsInFrame), the frame is complete.

        // 5. Check if the frame is complete
        if (frame.packetsReceived == frame.totalPackets)
        {
            // 6. Check the deadline and record statistics
            simtime_t delay = simTime() - frame.creationTime;
            frameDelayHistogram.collect(delay);
            simtime_t deadline = par("deadline").doubleValue(); // In seconds

            EV << "Frame " << frameId << " complete. Delay: " << delay << "s" << endl;

            // Record statistics
            totalFramesReceived++;

            if (delay > deadline)
            {
                // Deadline missed
                totalFramesMissed++;
                cumulativeRmse += frame.rmse;
                EV << "Deadline missed! RMSE: " << frame.rmse << endl;
            }

            // Calculate and record mean error
            double meanError = cumulativeRmse / totalFramesReceived;
            meanErrorVector.record(meanError);

            // Clean up the frame from buffer
            frameBuffer.erase(frameId);

            EV << "Total frames received: " << totalFramesReceived
               << ", missed: " << totalFramesMissed
               << ", mean error: " << meanError << endl;
        }

        delete packet;
    }

    void XRTrafficSink::finish()
    {
        // Record final statistics
        recordScalar("totalFramesReceived", totalFramesReceived);
        recordScalar("totalFramesMissed", totalFramesMissed);
        recordScalar("finalMeanError", totalFramesReceived > 0 ? cumulativeRmse / totalFramesReceived : 0);
        recordScalar("missedFramePercentage", totalFramesReceived > 0 ? (double)totalFramesMissed / totalFramesReceived * 100 : 0);
        frameDelayHistogram.recordAs("frameDelayHistogram");
    }

} // namespace
