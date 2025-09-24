package src;

simple ReceiverUE
{
    parameters:
        string logFile;
        int id;

        // Signals emitted by FrameReceiver.cc
        @signal[frameDelay](type=simtime_t);
        @signal[throughput](type=double);

        // Optional: record stats for analysis
        @statistic[frameDelay](title="Receiver frame delay";
                               source=frameDelay;
                               record=vector,histogram,mean;
                               unit=s);

        @statistic[throughput](title="Receiver throughput";
                               source=throughput;
                               record=vector,mean,last;
                               unit="bps");  // or "Bps" if you emit bytes/sec

    gates:
        input  in;   // data from gNB
        output out;  // ACK to gNB
}
