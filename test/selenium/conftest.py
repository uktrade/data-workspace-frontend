import json
import multiprocessing
import os
import signal
import subprocess
from contextlib import contextmanager
from http.server import HTTPServer, BaseHTTPRequestHandler
from io import BytesIO
from urllib.parse import parse_qs

import pytest


@pytest.fixture(scope='module')
def create_application():
    proc = subprocess.Popen(['/dataworkspace/start.sh'])

    yield

    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except ProcessLookupError:
        pass


class SSOServer(multiprocessing.Process):
    def run(self):
        (  # pylint: disable=unbalanced-tuple-unpacking
            is_logged_in,
            codes,
            tokens,
            auth_to_me,
        ) = self._args
        latest_code = None

        class SSOHandler(BaseHTTPRequestHandler):
            def handle_authorize(self):
                nonlocal latest_code

                if not is_logged_in:
                    self.send_response(200, message='This is the login page')

                params = parse_qs(self.path.split('?')[1])

                location = params['redirect_uri'][0]
                state = params['state'][0]
                latest_code = next(codes)

                self.send_response(302)
                self.send_header(
                    'Location', f"{location}?state={state}&code={latest_code}"
                )
                self.end_headers()

            def handle_token(self):
                nonlocal latest_code

                body = self.rfile.read(int(self.headers['Content-Length'])).decode(
                    'ascii'
                )

                data = parse_qs(body)
                if data['code'][0] != latest_code:
                    self.send_response(403)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{}')

                token = next(tokens)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()

                response = BytesIO()
                response.write(json.dumps({"access_token": token}).encode('ascii'))

                self.wfile.write(response.getvalue())

            def handle_me(self):
                print(123)
                print(self.path)
                print(self.headers)
                if self.headers['authorization'] in auth_to_me:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()

                    response = BytesIO()
                    response.write(
                        json.dumps(auth_to_me[self.headers['authorization']]).encode(
                            'ascii'
                        )
                    )

                    self.wfile.write(response.getvalue())
                    return

                self.send_response(403)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{}')

            def do_GET(self):
                if self.path.startswith('/o/authorize'):
                    self.handle_authorize()
                elif self.path.startswith('/api/v1/user/me'):
                    self.handle_me()
                else:
                    raise ValueError(f"Unknown path: {self.path}")

            def do_POST(self):
                if self.path.startswith('/o/token'):
                    self.handle_token()
                else:
                    raise ValueError(f"Unknown path: {self.path}")

        httpd = HTTPServer(("0.0.0.0", 8005), SSOHandler)
        httpd.serve_forever()


@contextmanager
def create_sso(is_logged_in, codes, tokens, auth_to_me):
    proc = SSOServer(args=(is_logged_in, codes, tokens, auth_to_me))
    proc.start()

    yield proc

    proc.kill()
