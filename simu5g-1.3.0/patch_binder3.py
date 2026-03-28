import re

with open('/home/teaching/Projects/NASCX/simu5g-1.3.0/src/common/binder/Binder.h', 'r') as f:
    content = f.read()

content = content.replace(
'''    struct XRVideoStats
    {
        double meanTrafficSize;
        double stdTrafficSize;
        double frameRate;
        double prevDelayMs;
        unsigned int bufferBytes;   // DL MAC buffer occupancy for this UE (bytes)
        unsigned int mcsIndex;      // Current MCS index (derived from CQI via AMC)

        XRVideoStats() : meanTrafficSize(0), stdTrafficSize(0), frameRate(60), prevDelayMs(10.0), bufferBytes(0), mcsIndex(0) {}
        XRVideoStats(double m, double s, double fr) : meanTrafficSize(m), stdTrafficSize(s), frameRate(fr), prevDelayMs(10.0), bufferBytes(0), mcsIndex(0) {}
    };''',
'''    struct XRVideoStats
    {
        double meanTrafficSize;
        double stdTrafficSize;
        double frameRate;
        double prevDelayMs;
        unsigned int bufferBytes;   // DL MAC buffer occupancy for this UE (bytes)
        unsigned int mcsIndex;      // Current MCS index (derived from CQI via AMC)
        double currentErrorAt80;
        double currentErrorRatio;

        XRVideoStats() : meanTrafficSize(0), stdTrafficSize(0), frameRate(60), prevDelayMs(10.0), bufferBytes(0), mcsIndex(0), currentErrorAt80(1000.0), currentErrorRatio(2.0) {}
        XRVideoStats(double m, double s, double fr) : meanTrafficSize(m), stdTrafficSize(s), frameRate(fr), prevDelayMs(10.0), bufferBytes(0), mcsIndex(0), currentErrorAt80(1000.0), currentErrorRatio(2.0) {}
    };'''
)

with open('/home/teaching/Projects/NASCX/simu5g-1.3.0/src/common/binder/Binder.h', 'w') as f:
    f.write(content)
