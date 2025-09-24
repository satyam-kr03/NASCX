package simu5g.apps.customTraffic;

import inet.applications.contract.IApp;

simple TrafficSource like IApp
{
    parameters:
        @class(TrafficSource);
        @display("i=block/source");
        
        // Configuration parameters
        double fps = default(60);
        double data_rate = default(20); // Mbps
        
        // Network parameters
        string destAddress = default("server"); // Destination IP address
        int destPort = default(3000);          // Destination port
        int localPort = default(3000);         // Local port
        
        // Lifecycle
        string interfaceTableModule = default(absPath(".interfaceTable"));
        
    gates:
        input socketIn;
        output socketOut;
}