//
//                  Simu5G
//
// Authors: Giovanni Nardini, Giovanni Stea, Antonio Virdis (University of Pisa)
//
// This file is part of a software released under the license included in file
// "license.pdf". Please read LICENSE and README files before using it.
// The above files and the present reference are part of the software itself,
// and cannot be removed from it.
//

package simu5g.apps.xr;

import inet.applications.contract.IApp;

//
// This module represents a model for the receiver of Voice-over-IP (XR) traffic.
// It receives packets sent by a ~XRSender application via UDP and records statistics
// such as packet loss, end-to-end latency, jitter, and throughput. Furthermore, it computes
// and emits a MOS (Mean Opinion Score) value, which represents the Quality-of-Experience of
// the end users.
//
simple XRReceiver like IApp
{
    parameters:
        int localPort = default(3000);
        int emodel_Ie_ = default(5);  // TODO from some ITU standard, figure it out
        int emodel_Bpl_ = default(10);
        int emodel_A_ = default(5);
        double emodel_Ro_ = default(93.2);
        double playout_delay @unit("s") = default(0s);
        int dim_buffer @unit(pk) = default(20pk); // in the number of packets
        double sampling_time @unit("s") = default(0.02s);

        @signal[XRFrameLoss];
        @statistic[XRFrameLoss](title="XR Frame Loss"; unit="ratio"; source="XRFrameLoss"; record=mean);
        @signal[XRFrameDelay];
        @statistic[XRFrameDelay](title="XR Frame Delay"; unit="s"; source="XRFrameDelay"; record=mean,vector);
        @signal[XRPlayoutDelay];
        @statistic[XRPlayoutDelay](title="XR Playout Delay"; unit="s"; source="XRPlayoutDelay"; record=mean,);
        @signal[XRPlayoutLoss];
        @statistic[XRPlayoutLoss](title="XR Playout Loss"; unit="ratio"; source="XRPlayoutLoss"; record=mean);
        @signal[XRJitter];
        @statistic[XRJitter](title="XR Jitter"; unit="s"; source="XRJitter"; record=mean);
        @signal[XRMos];
        @statistic[XRMos](title="XR Mos Signal"; unit="MOS"; source="XRMos"; record=mean);
        @signal[XRTaildropLoss];
        @statistic[XRTaildropLoss](title="XR Tail Drop Loss"; unit="ratio"; source="XRTaildropLoss"; record=mean);
        @signal[XRReceivedThroughput];
        @statistic[XRReceivedThroughput](title="Throughput received at the application level"; unit="Bps"; source="XRReceivedThroughput"; record=mean,vector);
        @display("i=block/source");
    gates:
        output socketOut;
        input socketIn;
}

