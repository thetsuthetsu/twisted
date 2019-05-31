import sys
from OpenSSL import crypto
from twisted.internet import endpoints, reactor, ssl
from twisted.internet.protocol import Protocol, Factory
from twisted.internet.defer import Deferred
from h2.config import H2Configuration
from h2.connection import H2Connection
from h2.events import (
    RequestReceived, DataReceived, WindowUpdated
)
import argparse
import time

READ_CHUNK_SIZE = 8192


def close_file(file, d):
    file.close()


class H2Protocol(Protocol):
    def __init__(self):
        config = H2Configuration(client_side=False)
        self.conn = H2Connection(config=config)
        self.known_proto = None
        self._flow_control_deferreds = {}

    def connectionMade(self):
        self.conn.initiate_connection()
        self.transport.write(self.conn.data_to_send())

    def dataReceived(self, data):
        if not self.known_proto:
            self.known_proto = True

        events = self.conn.receive_data(data)
        if self.conn.data_to_send:
            self.transport.write(self.conn.data_to_send())

        for event in events:
            if isinstance(event, RequestReceived):
                self.requestReceived(event.headers, event.stream_id)
            elif isinstance(event, DataReceived):
                self.dataFrameReceived(event.stream_id)
            elif isinstance(event, WindowUpdated):
                self.windowUpdated(event)

    def requestReceived(self, headers, stream_id):
        data = b'test1 data'
        response_headers = [
            (':status', '200'),
            ('content-length', str(len(data))),
            ('server', 'twisted-h2'),
        ]

        self.conn.send_headers(stream_id, response_headers)
        self.transport.write(self.conn.data_to_send())
        self.conn.send_data(stream_id, data, True)
        self.transport.write(self.conn.data_to_send())

        time.sleep(10)
        self.conn.send_data(stream_id, b'test2 data', True)
        self.transport.write(self.conn.data_to_send())

        return

    def dataFrameReceived(self, stream_id):
        self.conn.reset_stream(stream_id)
        self.transport.write(self.conn.data_to_send())

    def windowUpdated(self, event):
        """
        Handle a WindowUpdated event by firing any waiting data sending
        callbacks.
        """
        stream_id = event.stream_id

        if stream_id and stream_id in self._flow_control_deferreds:
            d = self._flow_control_deferreds.pop(stream_id)
            d.callback(event.delta)
        elif not stream_id:
            for d in self._flow_control_deferreds.values():
                d.callback(event.delta)

            self._flow_control_deferreds = {}

        return

    def wait_for_flow_control(self, stream_id):
        """
        Returns a Deferred that fires when the flow control window is opened.
        """
        d = Deferred()
        self._flow_control_deferreds[stream_id] = d
        return d


class H2Factory(Factory):
    def buildProtocol(self, addr):
        return H2Protocol()


parser = argparse.ArgumentParser(prog='push-server.py', usage='%(prog)s server_crt server_key rca_crt ica_crt [--port(def.443)]')
parser.add_argument("server_crt", help="path to server cert file(pem)", type=str)
parser.add_argument("server_key", help="path to server key file(pem)", type=str)
parser.add_argument("rca_crt", help="path to rca cert file(pem)", type=str)
parser.add_argument("ica_crt", help="path to ica cert file(pem)", type=str)
parser.add_argument("--port", help="listening port", type=int, default=443)
args = parser.parse_args()

with open(args.server_crt, 'r') as f:
    cert_data = f.read()
with open(args.server_key, 'r') as f:
    key_data = f.read()
with open(args.rca_crt, 'r') as f:
    rca_crt = f.read()
with open(args.ica_crt, 'r') as f:
    ica_crt = f.read()

cert = crypto.load_certificate(crypto.FILETYPE_PEM, cert_data)
key = crypto.load_privatekey(crypto.FILETYPE_PEM, key_data)
rca = crypto.load_certificate(crypto.FILETYPE_PEM, rca_crt)
ica = crypto.load_certificate(crypto.FILETYPE_PEM, ica_crt)
options = ssl.CertificateOptions(
    privateKey=key,
    certificate=cert,
    extraCertChain=[rca, ica],
    acceptableProtocols=[b'h2'],
)

endpoint = endpoints.SSL4ServerEndpoint(reactor, args.port, options, backlog=128)
endpoint.listen(H2Factory())
reactor.run()
