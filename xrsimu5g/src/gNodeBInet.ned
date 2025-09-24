package src;

import inet.mobility.contract.IMobility;

module gNodeBInet
{
    parameters:
        @display("i=device/antennatower");
        int numReceivers;
        double broadcastDelay @unit(s);
        double ackTimeout     @unit(s);

    gates:
        input  in;
        output out[numReceivers];
        input  ackIn[numReceivers];
        output ackOut;

    submodules:
        app: gNodeB {
            parameters:
                numReceivers   = parent.numReceivers;
                broadcastDelay = parent.broadcastDelay;
                ackTimeout     = parent.ackTimeout;
            @display("p=60,50");
        }
        mobility: <default("StationaryMobility")> like IMobility {
            parameters:
                @display("p=20,20");
        }

    connections allowunconnected:
        in --> app.in;
        for i=0..numReceivers-1 {
            app.out[i] --> out[i];
            ackIn[i]   --> app.ackIn[i];
        }
        app.ackOut --> ackOut;
}
