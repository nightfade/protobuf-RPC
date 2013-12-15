__author__ = 'nightfade'

from example.echo_service_pb2 import IEchoService, IEchoClient_Stub
import logger


class EchoService(IEchoService):

    def echo(self, rpc_controller, echo_string, callback):
        """ called by RpcChannel.receive when a complete request reached.
        """
        logger.get_logger('EchoService').info('echo service is called')
        echo_string.message = echo_string.message
        client_stub = IEchoClient_Stub(rpc_controller.rpc_channel)
        client_stub.respond(rpc_controller, echo_string, callback=None)
        if callback:
            callback()
