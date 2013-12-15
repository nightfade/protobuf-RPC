import struct

from google.protobuf import service
from rpc_controller import RpcController
import logger


class RpcParser(object):

    ST_HEAD = 0
    ST_DATA = 1

    def __init__(self, rpc_service, headfmt, indexfmt):
        self.logger = logger.get_logger('RpcParser')
        self.service = rpc_service
        self.headfmt = headfmt
        self.indexfmt = indexfmt
        self.headsize = struct.calcsize(self.headfmt)
        self.indexsize = struct.calcsize(self.indexfmt)

        self.buff = ''
        self.stat = RpcParser.ST_HEAD
        self.datasize = 0

    def feed(self, data):
        rpc_calls = []
        self.buff += data
        while True:
            if self.stat == RpcParser.ST_HEAD:
                self.logger.debug('ST_HEAD: %d/%d' % (len(self.buff), self.headsize))
                if len(self.buff) < self.headsize:
                    break

                head_data = self.buff[:self.headsize]
                self.datasize = struct.unpack(self.headfmt, head_data)[0]

                self.buff = self.buff[self.headsize:]
                self.stat = RpcParser.ST_DATA

            if self.stat == RpcParser.ST_DATA:
                self.logger.debug('ST_DATA: %d/%d ' % (len(self.buff), self.datasize))
                if len(self.buff) < self.datasize:
                    break

                index_data = self.buff[:self.indexsize]
                request_data = self.buff[self.indexsize: self.datasize]

                index = struct.unpack(self.indexfmt, index_data)[0]
                service_descriptor = self.service.GetDescriptor()

                # throw IndexError if index is invalid
                method_descriptor = service_descriptor.methods[index]
                request = self.service.GetRequestClass(method_descriptor)()

                # throw AttributeError if failed to decode or message is not initialized
                request.ParseFromString(request_data)
                if not request.IsInitialized():
                    raise AttributeError('invalid request data')

                self.buff = self.buff[self.datasize:]
                self.stat = RpcParser.ST_HEAD

                rpc_calls.append((method_descriptor, request))
        return rpc_calls


class RpcChannel(service.RpcChannel):

    HEAD_FMT = '!I'
    INDEX_FMT = '!H'
    HEAD_LEN = struct.calcsize(HEAD_FMT)
    INDEX_LEN = struct.calcsize(INDEX_FMT)

    def __init__(self, service_local, conn):
        super(RpcChannel, self).__init__()
        self.logger = logger.get_logger('RpcChannel')
        self.service_local = service_local
        self.conn = conn

        self.conn.attach_rpc_channel(self)
        self.rpc_controller = RpcController(self)

        self.rpc_parser = RpcParser(self.service_local, RpcChannel.HEAD_FMT, RpcChannel.INDEX_FMT)

    def getpeername(self):
        if self.conn:
            return self.conn.getpeername()
        return None, None

    def on_disconnected(self):
        self.conn = None

    def disconnect(self):
        if self.conn:
            self.conn.disconnect()

    def CallMethod(self,
                   method_descriptor,
                   rpc_controller,
                   request,
                   response_class,
                   done):
        """  called by stub, server_remote interface is maintained by stub """
        index = method_descriptor.index
        data = request.SerializeToString()
        size = RpcChannel.INDEX_LEN + len(data)

        self.conn.send_data(struct.pack(RpcChannel.HEAD_FMT, size))
        self.conn.send_data(struct.pack(RpcChannel.INDEX_FMT, index))
        self.conn.send_data(data)
        # should wait here to receive response if using a synchronous RPC with return value

    def receive(self, data):
        """ receive request from remote and call server_local interface """
        try:
            rpc_calls = self.rpc_parser.feed(data)
        except (AttributeError, IndexError), e:
            self.logger.warning('error occured when parsing request, give up and disconnect.')
            self.disconnect()
            return

        for method_descriptor, request in rpc_calls:
            # should call the callback and send response to client if using a synchronous RPC with return value
            self.service_local.CallMethod(method_descriptor, self.rpc_controller, request, callback=None)
