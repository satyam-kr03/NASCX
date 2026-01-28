//
// XRTrafficReceiver module for Simu5G
// Receives XR traffic and computes QoE metrics based on frame delays and losses
//

package simu5g.apps.xr;

import inet.applications.contract.IApp;

simple XRTrafficReceiver like IApp
{
    parameters:
        @display("i=block/sink");
        
        // Statistics signals
        @signal[rcvdPkt](type=long);
        @signal[rcvdBytes](type=long);
        @signal[frameDelay](type=double);
        @signal[frameMse](type=double);
        @signal[frameError](type=double);
        @signal[frameOnTime](type=long);
        @signal[meanError](type=double);
        @signal[delayReliability](type=double);
        @signal[userSatisfied](type=long);
        
        // Statistics recording
        @statistic[rcvdPkt](title="packets received"; source=rcvdPkt; record=count,sum,vector; interpolationmode=none);
        @statistic[rcvdBytes](title="bytes received"; source=rcvdBytes; record=count,sum,vector; interpolationmode=none);
        @statistic[frameDelay](title="frame delay"; source=frameDelay; record=vector,histogram,mean,max; unit=ms; interpolationmode=none);
        @statistic[frameMse](title="frame MSE"; source=frameMse; record=vector,histogram,mean; interpolationmode=none);
        @statistic[frameError](title="frame effective error"; source=frameError; record=vector,histogram,mean; interpolationmode=none);
        @statistic[frameOnTime](title="frame on time"; source=frameOnTime; record=vector,sum,mean; interpolationmode=none);
        @statistic[meanError](title="mean error (QoE)"; source=meanError; record=last; interpolationmode=none);
        @statistic[delayReliability](title="delay reliability"; source=delayReliability; record=last; interpolationmode=none);
        @statistic[userSatisfied](title="user satisfied (99% on-time)"; source=userSatisfied; record=last; interpolationmode=none);
        
        // Network parameters
        int localPort = default(3000);
        
        // QoE parameters
        double deadlineMs @unit(ms) = default(2.5ms);  // Frame deadline in milliseconds (2.5ms for low-latency XR)
        double reliabilityThreshold = default(0.99);   // Delay reliability threshold (99%)
        bool autoElost = default(true);  // Automatically set Elost to max MSE
        double elostValue = default(0);  // Manual Elost value (used if autoElost=false)
        int expectedFrames = default(1200);  // Expected number of frames (20s * 60fps)
        
        // Output parameters
        string resultFile = default("");  // CSV file for detailed results (empty = no file)
        
    gates:
        output socketOut;
        input socketIn;
}