package src;

import inet.mobility.contract.IMobility;

module SourceUEInet
{
    parameters:
        @display("i=device/laptop");
        string gdfFile;
        double sendInterval @unit(s);

    gates:
        input  in;
        output out;
        input  ackIn;
        output ackOut;

    submodules:
        app: SourceUE {
            parameters:
                gdfFile      = parent.gdfFile;
                sendInterval = parent.sendInterval;
            @display("p=60,50");
        }
        mobility: <default("RandomWaypointMobility")> like IMobility {
            parameters:
                @display("p=20,20");
                // concrete params come from .ini
        }

    connections allowunconnected:
        in         --> app.in;
        app.out    --> out;
        ackIn      --> app.ackIn;
        app.ackOut --> ackOut;
}
