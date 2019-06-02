import time

from twisted.web.resource import Resource


class ClockPage(Resource):
    isLeaf = True
    def render_GET(self, request):
        return (b"<!DOCTYPE html><html><head><meta charset='utf-8'>"
                b"<title></title></head><body>" + time.ctime().encode('utf-8'))


resource = ClockPage()