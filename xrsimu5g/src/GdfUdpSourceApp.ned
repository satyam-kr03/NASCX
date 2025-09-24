package src;

simple GdfUdpSourceApp like inet.applications.contract.IApp
{
    parameters:
        string inputFile;          // e.g. "gdf/input.gdf"
        string destAddr;           // e.g. "h2"
        int    destPort = default(5000);
        int    localPort = default(-1);      // -1 = auto-bind
        bool   stopWhenDone = default(true); // NEW: stop sim when last row sent
        double stopGrace @unit(s) = default(0.2s); // NEW: extra time before stopping
        @display("i=block/source");
    gates:
        input  socketIn  @labels(UDP_I_DATA,UDP_I_ERROR);
        output socketOut @labels(UDP_O_DATA);
}
