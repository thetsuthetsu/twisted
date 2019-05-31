from twisted.web.resource import Resource
from twisted.python import log
from twisted.web import server
from twisted.internet import reactor
from twisted.internet import endpoints
import argparse
import sys
import os


class ClientRequester(Resource):
    isLeaf = True

    def __init__(self, i):
        Resource.__init__(self)
        self.internal = i

    def render_GET(self, request):
        channel = getChannelID('/subscriptions/channel/', request.uri)
        if (channel == False):
            return '{ "status" : "error" }'

        self.internal.addClientDelegate(channel, ClientDelegate(request))

        return server.NOT_DONE_YET

class ClientDelegate:

    def __init__(self, r):
        self.request = r
        # JSONP stuff, check errors bla bla bla
        self.callbackName = r.args['callback'][0]

    def end(self, status, revision):
        try:
            rev = ''
            if revision != False:
                rev = ', "revision" : "' + revision + '"'
            self.request.write(self.callbackName + '({ "status" : "' + status + '"' + rev + '})')
            self.request.finish()
        except:
            print "Client lost patience"

    def notify(self, revision):
        self.end('changed', revision)


class NotificationRequester(Resource):
    isLeaf = True

    def __init__(self):
        Resource.__init__(self)
        self.clients = { }

    def render_GET(self, request):
        channel = getChannelID('/notifications/channel/', request.uri)
        revision = request.args['revision'][0]

        if (channel == False):
            return '{ "status" : "error" }'

        print "Waking up clients on channel " + channel

        if (channel in self.clients):
            oldL = self.clients[channel]
            self.clients[channel] = [ ]
            for client in oldL:
                client.notify(revision)

        return '{ "status" : "ok" }'

    def addClientDelegate(self, channel, delegate):
        if (channel in self.clients):
            self.clients[channel].append(delegate)
        else:
            self.clients[channel] = [ delegate ]

        print "Registered new client into channel " + channel
        print "Current clients:"
        print self.clients