package src;

simple GdfUdpSinkApp like inet.applications.contract.IApp
{
    parameters:
        string outputFile;               // e.g. "gdf/output_RX0.gdf"
        int    localPort = default(5000);

        // Optional alternate auto-stop: end sim when no packets arrive for a while
        bool   stopWhenIdle = default(false);
        double idleGrace @unit(s) = default(0.5s);
        @display("i=block/sink");
    gates:
        input  socketIn  @labels(UDP_I_DATA,UDP_I_ERROR);
        output socketOut @labels(UDP_O_DATA);
}
