import time
import json
import socket
import SocketServer

from Foundation import *
from AppKit import *
from PyObjCTools import AppHelper
from Queue import Queue, Empty
from threading import Thread

class CommandListener(Thread):
    active = False
    def __init__(self, port=9001):
        super(CommandListener, self).__init__()
        try:
            self.server = self.SocketListener(('localhost', port), self.CommandHandler)
            self.ip, self.port = self.server.server_address
            self.active = True
        except socket.error, e:
            NSLog("Another process is listening on port %i (possibly another PlotDevice instance)"%port)
            NSLog("The plotdevice.py command line tool will not be able to communicate with this process")
            self.port = None

    def run(self):
        if self.active:
            self.server.serve_forever()

    def join(self, timeout=None):
        if self.active:
            self.server.shutdown()
        super(CommandListener, self).join(timeout)

    class CommandHandler(SocketServer.BaseRequestHandler):
        def handle(self):
            self.stdout_q = Queue()
            try:
                self.opts = json.loads(self.request.recv(1024).split('\n')[0])
            except ValueError:
                return
            self.opts['console'] = self.stdout_q
            AppHelper.callAfter(self.run_script, self.opts)

            txt = ''
            try:
                while txt is not None:
                    if txt:
                        self.request.sendall(txt)
                    try:
                        self.check_interrupt()
                        txt = self.stdout_q.get_nowait()
                    except Empty:
                        time.sleep(.1)
                        txt = ''
            except socket.error, e:
                pass # if client closed socket, stop sending

        def check_interrupt(self):
            try:
                self.request.setblocking(0)
                interrupt = self.request.recv(1024)
                AppHelper.callAfter(self.stop_script, self.opts)
            except socket.error, e:
                pass # no input from the client
            finally:
                self.request.settimeout(socket.getdefaulttimeout())

        def run_script(self, opts):
            url = NSURL.URLWithString_('file://%s'%opts['file']) # use doc.path instead...
            dc = NSApp().delegate()._docsController
            dc.openDocumentWithContentsOfURL_display_error_(url, True, None)
            stdout = opts['console']
            for doc in dc.documents():
                if doc.fileURL() and doc.fileURL().isEqualTo_(url):
                    if doc.vm.tty:
                        stdout.put("already running: %s"%opts['file'])
                        stdout.put(None)
                        break
                    if doc.vm.session and doc.vm.session.running:
                        stdout.put("already exporting: %s"%opts['file'])
                        stdout.put(None)
                        break
                    if opts['activate']:
                        NSApp().activateIgnoringOtherApps_(True)
                    doc.scriptedRun(opts)
                    break
            else:
                stdout.put("couldn't open script: %s"%opts['file'])
                stdout.put(None)

        def stop_script(self, opts):
            url = NSURL.URLWithString_('file://%s'%opts['file'])
            dc = NSApp().delegate()._docsController
            dc.openDocumentWithContentsOfURL_display_error_(url, True, None)
            for doc in dc.documents():
                if doc.fileURL() and doc.fileURL().isEqualTo_(url):
                    doc.vm.live = False
                    doc.stopScript()


    class SocketListener(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
        daemon_threads = True # Ctrl-C will cleanly kill all spawned threads
        allow_reuse_address = True # much faster rebinding
