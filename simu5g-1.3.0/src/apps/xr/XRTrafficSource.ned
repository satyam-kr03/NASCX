//
// XRTrafficSource module for Simu5G
// Generates XR traffic based on frame size and MSE data from CSV files
//

package simu5g.apps.xr;

import inet.applications.contract.IApp;

simple XRTrafficSource like IApp
{
    parameters:
        @display("i=block/source");
        @signal[sentPkt](type=long);
        @signal[sentBytes](type=long);
        @statistic[sentPkt](title="packets sent"; source=sentPkt; record=count,sum,vector; interpolationmode=none);
        @statistic[sentBytes](title="bytes sent"; source=sentBytes; record=count,sum,vector; interpolationmode=none);
        
        // Network parameters
        int localPort = default(3088);
        int destPort = default(3000);
        string destAddress;
        int maxPayloadSize @unit(B) = default(60000B);  // Max payload per packet to avoid IP fragmentation
        
        // Traffic generation parameters
        double fps = default(60.0);  // frames per second
        double startTime @unit(s) = default(0s);
        string pcaFile = default("pca_selected.csv");  // CSV file containing frame data
        int compressionLevel = default(0);  // Filter by components: 0=all, else filter (5,10,15,...,80)
        
        // Jitter parameters (in milliseconds)
        double jitterMean @unit(ms) = default(0ms);
        double jitterStd @unit(ms) = default(2ms);
        double jitterMin @unit(ms) = default(-4ms);
        double jitterMax @unit(ms) = default(4ms);
        int jitterSeed = default(0);
        
    gates:
        output socketOut;
        input socketIn;
}