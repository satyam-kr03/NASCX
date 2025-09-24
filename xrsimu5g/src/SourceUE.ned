package src;

simple SourceUE
{
    parameters:
        string gdfFile;
        volatile double sendInterval @unit(s);
        bool endWhenDone = default(true);  // auto-stop when GDF ends

        // Signals emitted by FrameSender.cc
        @signal[ackRTT](type=simtime_t);
        @signal[retransmitCount](type=long);
        @signal[droppedFrame](type=long);

        // Optional: record stats for analysis
        @statistic[ackRTT](title="ACK RTT";
                           source=ackRTT;
                           record=vector,histogram,mean;
                           unit=s);

        @statistic[retransmitCount](title="Retransmissions";
                                    source=retransmitCount;
                                    record=sum,count,last);

        @statistic[droppedFrame](title="Dropped frames";
                                 source=droppedFrame;
                                 record=sum,count,last);

    gates:
        input  in;        // receives ACKs from gNodeB.ackOut
        output out;       // sends frames to gNodeB.in
        input  ackIn;     // (kept for your compound wiring)
        output ackOut;    // (kept for your compound wiring)
}
