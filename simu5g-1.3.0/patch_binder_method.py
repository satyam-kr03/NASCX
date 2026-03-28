with open('/home/teaching/Projects/NASCX/simu5g-1.3.0/src/common/binder/Binder.h', 'r') as f:
    text = f.read()

text = text.replace(
    '''        void setXRVideoPrevDelayMs(MacNodeId nodeId, double prevDelayMs);

        /**''',
    '''        void setXRVideoPrevDelayMs(MacNodeId nodeId, double prevDelayMs);
        void setXRErrorMetrics(MacNodeId nodeId, double errorAt80, double errorRatio);

        /**'''
)

with open('/home/teaching/Projects/NASCX/simu5g-1.3.0/src/common/binder/Binder.h', 'w') as f:
    f.write(text)
