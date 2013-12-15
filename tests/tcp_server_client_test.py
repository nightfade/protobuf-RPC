__author__ = 'nightfade'

import unittest
import asyncore

from example.echo_service_pb2 import EchoString, IEchoService_Stub
from rpc.tcp_server import TcpServer
from rpc.tcp_client import TcpClient
from rpc.tcp_connection import TcpConnection
from rpc.rpc_controller import RpcController
from example.echo_service import EchoService
from example.echo_client import EchoClient


class DummyService(object):
    pass


class DummyStub(object):
    def __init__(self, rpc_channel):
        pass


class EchoRecorder(object):
    def __init__(self):
        self.record = []

    def write(self, message):
        self.record.append(message)


class TcpServerClientTest(unittest.TestCase):

    def setUp(self):
        self.ip = '127.0.0.1'
        self.port = 65432

    def test_connection(self):
        server = TcpServer(self.ip, self.port, DummyService)
        client = TcpClient(self.ip, self.port, DummyService, DummyStub)
        client.async_connect()

        asyncore.loop(timeout=0.1, count=10)

        self.assertEqual(client.status, TcpConnection.ST_ESTABLISHED)

        server.close()
        client.close()

    def test_echo(self):
        TcpServer(self.ip, self.port, EchoService)
        client = TcpClient(self.ip, self.port, EchoClient, IEchoService_Stub)

        client.async_connect()

        echo_recorder = EchoRecorder()
        rpc_count = 0

        for i in xrange(10):
            asyncore.loop(0.1, count=1)
            if client.stub:
                if not client.service.streamout:
                    client.service.set_streamout(echo_recorder)
                request = EchoString()
                request.message = str(rpc_count)
                controller = RpcController(client.rpc_channel)
                client.stub.echo(controller, request, None)
                rpc_count += 1

        asyncore.loop(0.1, count=30)

        self.assertEqual(len(echo_recorder.record), rpc_count)

        echo_recorder.record.sort(cmp=lambda x, y: int(x) < int(y))
        for i in xrange(rpc_count):
            self.assertEqual(echo_recorder.record[i], str(i))
