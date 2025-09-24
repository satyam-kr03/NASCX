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

#ifndef __INET_XRPACKETSERIALIZER_H
#define __INET_XRPACKETSERIALIZER_H

#include <inet/common/packet/serializer/FieldsChunkSerializer.h>

namespace simu5g
{

  /**
   * Converts between XRPacket and binary (network byte order) packet.
   */
  class XRPacketSerializer : public inet::FieldsChunkSerializer
  {
  protected:
    void serialize(inet::MemoryOutputStream &stream, const inet::Ptr<const inet::Chunk> &chunk) const override;
    const inet::Ptr<inet::Chunk> deserialize(inet::MemoryInputStream &stream) const override;
  };

} // namespace

#endif // ifndef __INET_XRPACKETSERIALIZER_H
