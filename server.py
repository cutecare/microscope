#!/usr/bin/env python

import sys
import io
import os
import shutil
from subprocess import Popen, PIPE
from string import Template
from struct import Struct
from threading import Thread
from time import sleep, time
from http.server import HTTPServer, BaseHTTPRequestHandler
from wsgiref.simple_server import make_server
import RPi.GPIO as GPIO
import json
import picamera
from ws4py.websocket import WebSocket
from ws4py.server.wsgirefserver import (
    WSGIServer,
    WebSocketWSGIHandler,
    WebSocketWSGIRequestHandler,
)
from ws4py.server.wsgiutils import WebSocketWSGIApplication

###########################################
# CONFIGURATION

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
PINS = [5,6,13,17,18,19,20,21,22,23,24,26,27]
PINSTATES = []

for pin in PINS:
    GPIO.setup(pin,GPIO.OUT,initial=GPIO.LOW)
for pin in range(0, 27):
    PINSTATES.append(0)

WIDTH = 2048
HEIGHT = 1536
WEB_WIDTH = 640
WEB_HEIGHT = 480
FRAMERATE = 24
HTTP_PORT = 80
WS_PORT = 8084
COLOR = u'#444'
BGCOLOR = u'#333'
JSMPEG_MAGIC = b'jsmp'
JSMPEG_HEADER = Struct('>4sHH')
VFLIP = False
HFLIP = False

###########################################


class StreamingHttpHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
            return
        elif self.path == '/assets/style.css':
            content_type = 'text/css'
            with io.open('assets/style.css', 'r') as f:
                content = f.read()
        elif self.path == '/assets/jsmpg.js':
            content_type = 'application/javascript'
            with io.open('assets/jsmpg.js', 'r') as f:
                content = f.read()
        elif self.path == '/assets/jquery-3.3.1.min.js':
            content_type = 'application/javascript'
            with io.open('assets/jquery-3.3.1.min.js', 'r') as f:
                content = f.read()
        elif self.path == '/index.html':
            content_type = 'text/html; charset=utf-8'
            with io.open('index.html', 'r') as f:
                tpl = Template(f.read())
                content = tpl.safe_substitute(dict(
                    WS_PORT=WS_PORT, WIDTH=WEB_WIDTH, HEIGHT=WEB_HEIGHT, COLOR=COLOR,
                    BGCOLOR=BGCOLOR))
        else:
            self.send_error(404, 'File not found')
            return
        content = content.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', len(content))
        self.send_header('Last-Modified', self.date_time_string(time()))
        self.end_headers()
        if self.command == 'GET':
            self.wfile.write(content)

    def do_POST(self):
        self.data_string = self.rfile.read(int(self.headers['Content-Length']))
        self.send_response(200)
        self.end_headers()
        data = json.loads(self.data_string.decode('utf-8'))
        pin = int(data['pin'])
        if self.path == '/toggle':
            PINSTATES[pin] = not PINSTATES[pin]
            GPIO.output(pin, PINSTATES[pin])
            print('Toggle pin %d' % pin)
        elif self.path == '/drive':
            directionPin = int(data['dirPin'])
            GPIO.output(directionPin, GPIO.HIGH if int(data['direction']) > 0 else GPIO.LOW )
            steps = int(data['steps'])
            for c in range(0, steps):
                GPIO.output(pin, GPIO.HIGH)
                sleep(0.02)
                GPIO.output(pin, GPIO.LOW)
                sleep(0.02)
            print('Drive on pin %d with direction %d' % (pin, int(data['direction'])) )

class StreamingHttpServer(HTTPServer):
    def __init__(self):
        super(StreamingHttpServer, self).__init__(
                ('', HTTP_PORT), StreamingHttpHandler)


class StreamingWebSocket(WebSocket):
    def opened(self):
        self.send(JSMPEG_HEADER.pack(JSMPEG_MAGIC, WEB_WIDTH, WEB_HEIGHT), binary=True)


class BroadcastOutput(object):
    def __init__(self, camera):
        print('Spawning background conversion process')
        self.converter = Popen([
            'ffmpeg',
            '-f', 'rawvideo',
            '-pix_fmt', 'yuv420p',
            '-s', '%dx%d' % camera.resolution,
            '-r', str(float(camera.framerate)),
            '-i', '-',
            '-f', 'mpeg1video',
            '-b', '800k',
            '-vf','crop=%d:%d:%d:%d' % (WEB_WIDTH, WEB_HEIGHT, (WIDTH - WEB_WIDTH) / 2, (HEIGHT - WEB_HEIGHT) / 2),
            '-r', str(float(camera.framerate)),
            '-'],
            stdin=PIPE, stdout=PIPE, stderr=io.open(os.devnull, 'wb'),
            shell=False, close_fds=True)

    def write(self, b):
        self.converter.stdin.write(b)

    def flush(self):
        print('Waiting for background conversion process to exit')
        self.converter.stdin.close()
        self.converter.wait()


class BroadcastThread(Thread):
    def __init__(self, converter, websocket_server):
        super(BroadcastThread, self).__init__()
        self.converter = converter
        self.websocket_server = websocket_server

    def run(self):
        try:
            while True:
                buf = self.converter.stdout.read1(32768)
                if buf:
                    self.websocket_server.manager.broadcast(buf, binary=True)
                elif self.converter.poll() is not None:
                    break
        finally:
            self.converter.stdout.close()


def main():
    print('Initializing camera')
    with picamera.PiCamera() as camera:
        camera.resolution = (WIDTH, HEIGHT)
        camera.framerate = FRAMERATE
        camera.vflip = VFLIP # flips image rightside up, as needed
        camera.hflip = HFLIP # flips image left-right, as needed
        sleep(1) # camera warm-up time
        print('Initializing websockets server on port %d' % WS_PORT)
        WebSocketWSGIHandler.http_version = '1.1'
        websocket_server = make_server(
            '', WS_PORT,
            server_class=WSGIServer,
            handler_class=WebSocketWSGIRequestHandler,
            app=WebSocketWSGIApplication(handler_cls=StreamingWebSocket))
        websocket_server.initialize_websockets_manager()
        websocket_thread = Thread(target=websocket_server.serve_forever)
        print('Initializing HTTP server on port %d' % HTTP_PORT)
        http_server = StreamingHttpServer()
        http_thread = Thread(target=http_server.serve_forever)
        print('Initializing broadcast thread')
        output = BroadcastOutput(camera)
        broadcast_thread = BroadcastThread(output.converter, websocket_server)
        print('Starting recording')
        camera.start_recording(output, 'yuv')
        try:
            print('Starting websockets thread')
            websocket_thread.start()
            print('Starting HTTP server thread')
            http_thread.start()
            print('Starting broadcast thread')
            broadcast_thread.start()
            while True:
                camera.wait_recording(1)
        except KeyboardInterrupt:
            pass
        finally:
            print('Stopping recording')
            camera.stop_recording()
            print('Waiting for broadcast thread to finish')
            broadcast_thread.join()
            print('Shutting down HTTP server')
            http_server.shutdown()
            print('Shutting down websockets server')
            websocket_server.shutdown()
            print('Waiting for HTTP server thread to finish')
            http_thread.join()
            print('Waiting for websockets thread to finish')
            websocket_thread.join()

if __name__ == '__main__':
    main()
