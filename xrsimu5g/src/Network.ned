package src;
network SelfmadeNetwork {
    submodules:
        src: SourceUE {
            parameters:
                gdfFile = "gdf/input.gdf";
                sendInterval = 0.02s;
        }
        gnb: gNodeB {
            parameters:
                numReceivers = 1;
                broadcastDelay = 1ms;
                ackTimeout = 50ms;
        }
        rx0: ReceiverUE {
            parameters:
                id = 0;
                logFile = "gdf/output_RX0.gdf";
        }
    connections:
        src.out --> SimpleWirelessChannel --> gnb.in;
        gnb.out[0] --> SimpleWirelessChannel --> rx0.in;
        rx0.out --> SimpleWirelessChannel --> gnb.ackIn[0];
        gnb.ackOut --> SimpleWirelessChannel --> src.in;
}

