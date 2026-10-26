"""Serve the explicit QA output directory; delay only static teaching PNGs."""
from pathlib import Path
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
import functools,sys,time
root=Path(sys.argv[1]).resolve();assert root.is_dir()
class Handler(SimpleHTTPRequestHandler):
 def do_GET(self):
  if '/teaching/'in self.path:time.sleep(1.5)
  super().do_GET()
 def end_headers(self):
  self.send_header('Cache-Control','no-store');super().end_headers()
ThreadingHTTPServer(('127.0.0.1',8898),functools.partial(Handler,directory=str(root))).serve_forever()
