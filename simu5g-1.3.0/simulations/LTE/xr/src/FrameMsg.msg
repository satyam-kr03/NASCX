packet FrameMsg {
    int frameId;
    double timestamp;
    double mse;
    bool sendFlag;
    int senderId;
    int receiverId;
    int packetSize;
}

message AckMsg {
    int frameId;
    int receiverId;
}
