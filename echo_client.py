__author__ = 'nightfade'

from echo_service_pb2 import IEchoClient
import logger


class EchoClient(IEchoClient):

    def __init__(self):
        self.streamout = None

    def set_streamout(self, streamout):
        self.streamout = streamout

    def respond(self, rpc_controller, echo_string, callback):
        """ called by RpcChannel.receive when a complete request reached.
        """
        logger.get_logger('EchoClient').debug('EchoClient.respond')
        if self.streamout:
            self.streamout.write(echo_string.message)

        if callback:
            callback()
