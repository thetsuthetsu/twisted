from twisted.web.resource import Resource
from twisted.python import log
from twisted.web import server
from twisted.internet import reactor
from twisted.internet import endpoints
import threading
import argparse
import sys
import os
import time

END_POINT_SPEC_FORM = "ssl:{}:privateKey={}:certKey={}"
#END_POINT_SPEC_FORM = "tcp:{}:interface={}"


class PushServer:
    def __init__(self, site):
        self.site = site
        self.endpoint_spec = END_POINT_SPEC_FORM.format(args.port, args.certKey, args.privKey)
        self.server = endpoints.serverFromString(reactor, self.endpoint_spec)

    def start(self):
        self.server.listen(self.site)
        reactor.run(installSignalHandlers=False)


class Index(Resource):
    isLeaf = True

    def __init__(self):
        self.client_delegate = None

    def render_GET(self, request):
        self.client_delegate = ClientDelegate(request)
        return server.NOT_DONE_YET
        # return b"hello world (in HTTP2)"

    def get_client_delegate(self):
        return self.client_delegate


class ClientDelegate:

    def __init__(self, r):
        self.request = r

    def end(self, status, revision):
        try:
            rev = ''
            if revision is not False:
                rev = ', "revision" : "' + revision + '"'
            msg = '({ "status" : "' + status + '"' + rev + '})'
            self.request.write(msg.encode())
            self.request.finish()
        except BaseException as ex:
            print(ex)

    def notify(self, revision):
        self.end('changed', revision)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='Http2Hello', usage='%(prog)s certKey privKey [--port(def.443)]')
    parser.add_argument("certKey", help="path to cert key file(pem)", type=str)
    parser.add_argument("privKey", help="path to private Key file(pem)", type=str)
    parser.add_argument("--port", help="listening port", type=int, default=443)

    try:
        args = parser.parse_args()
        if not os.path.exists(args.certKey):
            raise FileNotFoundError(args.certKey)
        if not os.path.exists(args.privKey):
            raise FileNotFoundError(args.privKey)

        log.startLogging(sys.stdout)

        index = Index()
        pushServer = PushServer(server.Site(index))
        thread_1 = threading.Thread(target=pushServer.start)
        thread_1.start()

        while True:
            print("input any ID...")
            id = input()
            client_delegate = index.get_client_delegate()
            if client_delegate is not None:
                client_delegate.notify(id)
            else:
                print("client_delegate is None.")

    except BaseException as ex:
        print(ex)
