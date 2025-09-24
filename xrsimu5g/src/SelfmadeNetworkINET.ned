package src;

import selfmade.SourceUEInet;
import selfmade.ReceiverUEInet;
import selfmade.gNodeBInet;
import selfmade.SimpleWirelessChannel;
import inet.visualizer.canvas.integrated.IntegratedCanvasVisualizer;

network SelfmadeNetworkINET
{
    parameters:
        @display("bgb=900,400");

    submodules:
        visualizer: IntegratedCanvasVisualizer {
            @display("p=50,40");
        }

        src: SourceUEInet {
            parameters:
                gdfFile      = default("gdf/input.gdf");
                sendInterval = default(0.02s);
                @display("p=120,200");
        }

        gnb: gNodeBInet {
            parameters:
                numReceivers   = default(1);
                broadcastDelay = default(1ms);
                ackTimeout     = default(50ms);
                @display("p=420,200");
        }

        rx0: ReceiverUEInet {
            parameters:
                id      = 0;
                logFile = default("gdf/output_RX0.gdf");
                @display("p=720,200");
        }

    connections allowunconnected:
        // Source -> gNB
        src.out      --> SimpleWirelessChannel --> gnb.in;

        // gNB (vector) -> Receiver 0
        gnb.out[0]   --> SimpleWirelessChannel --> rx0.in;

        // Receiver 0 -> gNB ack path (vector)
        rx0.out      --> SimpleWirelessChannel --> gnb.ackIn[0];
        gnb.ackOut --> SimpleWirelessChannel --> src.in;
        // NOTE: No connection from gnb.ackOut to src, because SourceUEInet has no 'ackIn' gate.
}
