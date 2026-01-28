import inet.common.INETDefs;
import inet.common.packet.chunk.Chunk;

namespace simu5g;

class XRHeader extends inet::FieldsChunk {
    int frameNumber;
    int pcaComponents;
    double mse;
    int sizeBytes;
    double genTime;
    int fragIndex;
    int totalFragments;
}