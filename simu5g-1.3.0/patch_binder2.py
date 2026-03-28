import re

with open('/home/teaching/Projects/NASCX/simu5g-1.3.0/src/common/binder/Binder.h', 'r') as f:
    content = f.read()

content = content.replace(
'''struct XRVideoStats
    {
        double meanTrafficSize;
        double stdTrafficSize;
        double frameRate;
        double prevDelayMs;
        unsigned int bufferBytes;   // DL MAC buffer occupancy for this UE (bytes)
        unsigned int mcsIndex;      // Current MCS index (derived from CQI via AMC)
    };''',
'''struct XRVideoStats
    {
        double meanTrafficSize;
        double stdTrafficSize;
        double frameRate;
        double prevDelayMs;
        unsigned int bufferBytes;   // DL MAC buffer occupancy for this UE (bytes)
        unsigned int mcsIndex;      // Current MCS index (derived from CQI via AMC)
        double currentErrorAt80;
        double currentErrorRatio;
    };'''
)

with open('/home/teaching/Projects/NASCX/simu5g-1.3.0/src/common/binder/Binder.h', 'w') as f:
    f.write(content)
