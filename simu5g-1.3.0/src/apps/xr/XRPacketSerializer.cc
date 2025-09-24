//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Lesser General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Lesser General Public License for more details.
//
// You should have received a copy of the GNU Lesser General Public License
// along with this program.  If not, see http://www.gnu.org/licenses/.
//

#include "apps/xr/XRPacketSerializer.h"

#include <inet/common/packet/serializer/ChunkSerializerRegistry.h>

#include "apps/xr/XRPacket_m.h"

namespace simu5g
{

    using namespace inet;

    Register_Serializer(XRPacket, XRPacketSerializer);

    void XRPacketSerializer::serialize(MemoryOutputStream &stream, const Ptr<const Chunk> &chunk) const
    {
        auto startPosition = stream.getLength();
        const auto &xrPacket = staticPtrCast<const XRPacket>(chunk);
        stream.writeUint32Be(B(xrPacket->getChunkLength()).get());
        stream.writeUint32Be(xrPacket->getIDtalk());
        stream.writeUint32Be(xrPacket->getNframes());
        stream.writeUint32Be(xrPacket->getIDframe());
        stream.writeUint64Be(xrPacket->getPayloadTimestamp().raw());
        stream.writeUint64Be(xrPacket->getArrivalTime().raw());
        stream.writeUint64Be(xrPacket->getPlayoutTime().raw());
        stream.writeUint32Be(xrPacket->getPayloadSize());

        int64_t remainders = B(xrPacket->getChunkLength() - (stream.getLength() - startPosition)).get();
        if (remainders < 0)
            throw cRuntimeError("XRPacket length = %d smaller than required %d bytes", (int)B(xrPacket->getChunkLength()).get(), (int)B(stream.getLength() - startPosition).get());
        stream.writeByteRepeatedly('?', remainders);
    }

    const Ptr<Chunk> XRPacketSerializer::deserialize(MemoryInputStream &stream) const
    {
        auto startPosition = stream.getPosition();
        auto xrPacket = makeShared<XRPacket>();
        B dataLength = B(stream.readUint32Be());
        xrPacket->setIDtalk(stream.readUint32Be());
        xrPacket->setNframes(stream.readUint32Be());
        xrPacket->setIDframe(stream.readUint32Be());
        xrPacket->getPayloadTimestamp().setRaw(stream.readUint64Be());
        xrPacket->getArrivalTime().setRaw(stream.readUint64Be());
        xrPacket->getPlayoutTime().setRaw(stream.readUint64Be());
        xrPacket->setPayloadSize(stream.readUint32Be());

        B remainders = dataLength - (stream.getPosition() - startPosition);
        ASSERT(remainders >= B(0));
        stream.readByteRepeatedly('?', B(remainders).get());
        return xrPacket;
    }

} // namespace
