with open('/home/teaching/Projects/NASCX/simu5g-1.3.0/src/common/binder/Binder.cc', 'r') as f:
    text = f.read()

text += '''
void Binder::setXRErrorMetrics(MacNodeId nodeId, double errorAt80, double errorRatio)
{
    if (xrVideoStats_.find(nodeId) != xrVideoStats_.end()) {
        xrVideoStats_[nodeId].currentErrorAt80 = errorAt80;
        xrVideoStats_[nodeId].currentErrorRatio = errorRatio;
    }
}
'''

with open('/home/teaching/Projects/NASCX/simu5g-1.3.0/src/common/binder/Binder.cc', 'w') as f:
    f.write(text)
