#include <omnetpp.h>
#include <inet/applications/base/ApplicationBase.h>
#include <inet/common/socket/SocketMap.h>
#include <inet/transportlayer/contract/udp/UdpSocket.h>
#include <inet/networklayer/common/L3AddressResolver.h>
#include <inet/common/packet/chunk/ByteCountChunk.h>
#include <inet/common/TimeTag.h>
#include <inet/common/packet/tag/TagSet.h>
#include <inet/common/ProtocolTag_m.h>
#include <inet/common/SequenceNumberTag_m.h>
#include <inet/common/packet/tag/TagSet.h>
#include <inet/common/TagBase_m.h>

#include <cmath> // Needed for ceil

using namespace omnetpp;
using namespace inet;
using namespace std;

namespace simu5g
{

    class TrafficSource : public ApplicationBase
    {
    private:
        cMessage *sendFrameEvent; // Renamed for clarity

        // Socket for sending data
        UdpSocket socket;
        L3Address destAddress;
        int destPort = 3000;
        int localPort = 3000;

        // --- CHANGED: Parameters based on paper's traffic model ---
        double fps;
        double interFrameInterval;
        double meanFrameSizeBytes;
        double frameSizeSdBytes;
        double minFrameSizeBytes;
        double maxFrameSizeBytes;
        double jitterMeanMs, jitterSdMs, jitterMinMs, jitterMaxMs;

        int frameNumber = 0;
        simtime_t startTime;

        // Packetization parameter
        int maxPacketSize = 1400; // Max size of a single packet in bytes (simulates MTU)

    protected:
        virtual void initialize(int stage) override;
        virtual void handleMessageWhenUp(cMessage *msg) override;
        double generateTruncatedNormal(double mean, double sd, double min, double max);

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
            // --- CHANGED: Using frame size parameters directly from the paper ---
            // These could be made into .ini parameters for more flexibility
            fps = par("fps").doubleValue();
            interFrameInterval = 1.0 / fps;

            // Values from Table II of the paper
            meanFrameSizeBytes = 62.5 * 1024; // 62.5 KB
            minFrameSizeBytes = 23.0 * 1024;  // 23 KB
            maxFrameSizeBytes = 92.8 * 1024;  // 92.8 KB
            frameSizeSdBytes = 15840;         // Using the max of the std range 2585-15840 B

            // Jitter values from Table II
            jitterMeanMs = 0; // The paper states mean 4ms with a range of +/-4ms, implying mean 0 jitter
            jitterSdMs = 2;
            jitterMinMs = -4;
            jitterMaxMs = 4;

            // maxPacketSize = maxPacketSize; // Could be parameterized if needed

            sendFrameEvent = new cMessage("sendFrameEvent");
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
        }
    }

    void TrafficSource::handleMessageWhenUp(cMessage *msg)
    {
        if (msg == sendFrameEvent)
        {
            // Capture the creation time once for the entire frame for accuracy
            simtime_t frameCreationTime = simTime();

            // 1. Generate the total size for this XR frame
            double totalFrameSize = generateTruncatedNormal(meanFrameSizeBytes, frameSizeSdBytes, minFrameSizeBytes, maxFrameSizeBytes);
            int bytesRemaining = (int)totalFrameSize;
            int numPackets = ceil(totalFrameSize / maxPacketSize);

            EV << "New Frame generated: FrameNumber=" << frameNumber << ", TotalSize=" << bytesRemaining << " bytes, NumPackets=" << numPackets << endl;

            // 2. Loop to create and send multiple smaller packets (packetization)
            for (int i = 0; i < numPackets; i++)
            {
                auto packet = new Packet("XR_Packet");
                int packetSize = std::min(bytesRemaining, maxPacketSize);

                auto payload = makeShared<ByteCountChunk>(B(packetSize));
                packet->insertAtBack(payload);

                // --- KEY CHANGES ---
                // Add the same timestamp to all packets of the frame
                packet->addTag<CreationTimeTag>()->setCreationTime(frameCreationTime);

                // Add Frame ID and Sequence Number for reassembly at the sink
                // We already added CreationTimeTag above, so no need to add it again
                // Instead, use SequenceNumberInd for storing the frame number

                // Store frame number and sequence info in a tag
                // Store frame number and sequence info in a tag
                auto sequenceTag = packet->addTag<SequenceNumberInd>();
                sequenceTag->setSequenceNumber(frameNumber * 10000 + i); // Encode both values: frameNumber and packet sequence in frame
                socket.sendTo(packet, destAddress, destPort);
                bytesRemaining -= packetSize;
            }

            // 3. Schedule the next frame generation event
            frameNumber++;
            double jitterMs = generateTruncatedNormal(jitterMeanMs, jitterSdMs, jitterMinMs, jitterMaxMs);
            simtime_t nextFrameTime = startTime + (frameNumber * interFrameInterval) + (jitterMs / 1000.0);
            scheduleAt(nextFrameTime, sendFrameEvent);
        }
        else
        {
            delete msg;
        }
    }

    double TrafficSource::generateTruncatedNormal(double mean, double sd, double min, double max)
    {
        // This is a simple rejection sampling method
        while (true)
        {
            double value = normal(mean, sd);
            if (value >= min && value <= max)
                return value;
        }
    }

    void TrafficSource::finish()
    {
        ApplicationBase::finish();
    }

    void TrafficSource::handleStartOperation(LifecycleOperation *operation)
    {
        startTime = simTime();
        double jitterMs = generateTruncatedNormal(jitterMeanMs, jitterSdMs, jitterMinMs, jitterMaxMs);

        // --- CORRECTED LOGIC ---
        // Calculate the initial send time
        simtime_t initialSendTime = simTime() + (jitterMs / 1000.0);

        // Ensure the event is not scheduled in the past by taking the maximum
        // of the calculated time and the current time.
        scheduleAt(std::max(simTime(), initialSendTime), sendFrameEvent);
    }

    void TrafficSource::handleStopOperation(LifecycleOperation *operation)
    {
        cancelEvent(sendFrameEvent);
    }

    void TrafficSource::handleCrashOperation(LifecycleOperation *operation)
    {
        cancelEvent(sendFrameEvent);
    }

} // namespace