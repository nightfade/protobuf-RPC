from google.protobuf import service


class RpcController(service.RpcController):

    def __init__(self, rpc_channel):
        self.rpc_channel = rpc_channel
