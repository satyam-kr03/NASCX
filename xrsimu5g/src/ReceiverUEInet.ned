package src;

import inet.mobility.contract.IMobility;

module ReceiverUEInet
{
    parameters:
        @display("i=device/pc");
        int id;
        string logFile;

    gates:
        input  in;
        output out;

    submodules:
        app: ReceiverUE {
            parameters:
                id = parent.id;
                logFile = parent.logFile;
            @display("p=60,50");
        }
        mobility: <default("RandomWaypointMobility")> like IMobility {
            parameters:
                @display("p=20,20");
        }

    connections allowunconnected:
        in --> app.in;
        app.out --> out;
}
