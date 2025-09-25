package simu5g.apps.XRTraffic;

import inet.applications.contract.IApp;

//
// XRTrafficSink is a UDP traffic receiver that analyzes frames for XR applications
// It measures delay against deadlines and calculates RMSE statistics
//
simple XRTrafficSink like IApp
{
    parameters:
        @class(XRTrafficSink);
        @display("i=block/sink");
        
        // Application parameters
        int localPort = default(4000);          // Port to listen on
        double rmsePerFrame = default(0.0);     // RMSE value per frame
        int packetsPerFrame = default(1);       // Number of packets per frame (likely 1 based on source)
        double deadline @unit(s) = default(16ms); // Deadline for frame delivery
        
        // Statistics
        @signal[meanError](type=double);
        @statistic[meanError](title="Mean Error"; record=vector,stats; interpolationmode=none);
        
    gates:
        input socketIn;
        output socketOut;
}