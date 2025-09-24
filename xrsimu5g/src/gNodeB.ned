package src;

simple gNodeB
{
    parameters:
        int numReceivers;
        volatile double broadcastDelay @unit(s);
        volatile double ackTimeout @unit(s);
    gates:
        input  in;
        output out[numReceivers];   // vector to each RX
        input  ackIn[numReceivers]; // vector from each RX
        output ackOut;              // back to source
}
