"""Opt-in, two real nginx layers + synthetic streaming upstream; no host network."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import urlopen
from native_gateway import native_gateway_config


def inside():
    class Upstream(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'
        def log_message(self, *_): pass
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('X-Accel-Buffering', 'no')
            self.send_header('Cache-Control', 'private, no-store')
            self.send_header('X-Fixture-Proxy-Hops', self.headers.get('X-Forwarded-For',''))
            self.send_header('Transfer-Encoding', 'chunked')
            self.end_headers()
            for revision in (1, 2):
                data = ('data: '+json.dumps({'revision':revision})+'\n\n').encode()
                self.wfile.write(f'{len(data):x}\r\n'.encode()+data+b'\r\n');self.wfile.flush()
                time.sleep(0.7)
            self.wfile.write(b'0\r\n\r\n');self.wfile.flush()
    server = ThreadingHTTPServer(('127.0.0.1', 9000), Upstream)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        outer = native_gateway_config('learn.example.com').replace('listen 80;', 'listen 8080;').replace('http://app:80','http://127.0.0.1:8081')
        inner = Path('/native-nginx.conf').read_text().replace('listen 80;', 'listen 8081;').replace('listen [::]:80;', 'listen [::]:8081;')
        (root/'logs').mkdir()
        temporary = '\n'.join(f'{kind}_temp_path {root}/{kind};' for kind in ('client_body','proxy','fastcgi','uwsgi','scgi'))
        config = 'worker_processes 1;\npid '+str(root/'nginx.pid')+';\nerror_log stderr error;\nevents { worker_connections 64; }\nhttp { access_log off;\n'+temporary+'\n'+inner+outer+'\n}'
        (root/'nginx.conf').write_text(config)
        process = subprocess.Popen(['nginx','-p',folder+'/', '-c',str(root/'nginx.conf'),'-g','daemon off;'])
        try:
            time.sleep(0.2)
            assert process.poll() is None, 'nginx failed to start'
            timings = {}
            for label, path in [('stream','/api/v1/attendance/sessions/1/events'),('control','/api/v1/synthetic-buffered')]:
                start = time.monotonic()
                with urlopen('http://127.0.0.1:8080'+path, timeout=5) as response:
                    assert 'no-store' in response.headers['Cache-Control']
                    assert len(response.headers['X-Fixture-Proxy-Hops'].split(',')) == 2, 'not two proxy layers'
                    first = response.readline(); elapsed = time.monotonic()-start
                    assert b'"revision": 1' in first, first
                    timings[label] = elapsed
                    if label == 'stream':
                        assert elapsed < 0.5, ('first frame buffered',elapsed)
                        response.readline()
                        assert b'"revision": 2' in response.readline()
                        assert time.monotonic()-start < 1.3, 'second frame buffered'
            print(json.dumps({'two_proxy_layers':True,'seconds_to_first_frame':timings,'native_inner_unchanged':True}))
        finally:
            process.terminate();process.wait(timeout=5);server.shutdown()


if __name__ == '__main__':
    if '--inside' in sys.argv:
        inside()
    else:
        root = Path(__file__).resolve().parents[2]
        subprocess.run([sys.executable,'-B',str(root/'deploy/staging/preflight.py')],check=True)
        image = os.getenv('LEARNHOUSE_API_TEST_IMAGE','coursemax-learnhouse:calendar-ui-owner-20261017')
        subprocess.run(['docker','image','inspect',image],check=True,stdout=subprocess.DEVNULL)
        subprocess.run(['docker','run','--rm','--pull=never','--network=none','--read-only',
            '--user',f'{os.getuid()}:{os.getgid()}','--cap-drop','ALL','--security-opt','no-new-privileges',
            '--memory','96m','--cpus','0.5','--pids-limit','64','--tmpfs','/tmp:rw,size=16m',
            '-v',f'{root}/deploy/staging:/fixture/deploy/staging:ro','-v',f'{root}/docker/nginx.conf:/native-nginx.conf:ro',
            '--entrypoint','/app/api/.venv/bin/python',image,'-B','/fixture/deploy/staging/test_attendance_stream_proxy.py','--inside'],check=True)
