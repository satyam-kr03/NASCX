package src;

import inet.node.inet.StandardHost;
import inet.networklayer.configurator.ipv4.Ipv4NetworkConfigurator;
import inet.physicallayer.wireless.ieee80211.packetlevel.Ieee80211ScalarRadioMedium;

network WifiSmokeTest
{
    parameters:
        @display("bgb=800,400");
    submodules:
        radioMedium: Ieee80211ScalarRadioMedium {
            @display("p=60,50");
        }
        configurator: Ipv4NetworkConfigurator {
            @display("p=60,120");
        }
        h1: StandardHost {
            parameters:
                @display("p=300,200");

                // NOTE: no app[] here; the INI will define apps
                // one WLAN and mobility are also set via INI
        }
        h2: StandardHost {
            parameters:
                @display("p=600,200");
                // same note: no app[] here
        }
}
