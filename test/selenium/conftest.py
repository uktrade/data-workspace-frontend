import json
import multiprocessing
import os
import signal
import subprocess
import textwrap
from contextlib import contextmanager
from http.server import HTTPServer, BaseHTTPRequestHandler
from io import BytesIO
from urllib.parse import parse_qs

import pytest


@pytest.fixture(scope="module")
def create_application():
    # pylint: disable=consider-using-with
    proc = subprocess.Popen(
        ["/dataworkspace/start-test.sh"],
        env={
            **os.environ,
            "EXPLORER_CONNECTIONS": '{"Postgres": "my_database"}',
            "ZENPY_FORCE_NETLOC": "dataworkspace.test:8006",
            "ZENPY_FORCE_SCHEME": "http",
        },
    )

    yield

    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except ProcessLookupError:
        pass


def set_waffle_flag(flag_name, everyone=True):
    python_code = textwrap.dedent(
        f"""
        from waffle.models import Flag

        flag, _ = Flag.objects.get_or_create(name='{flag_name}', defaults=dict(everyone={everyone}))
        flag.everyone = {everyone}
        flag.save()
        """
    ).encode("ascii")

    # pylint: disable=consider-using-with
    give_perm = subprocess.Popen(
        ["django-admin", "shell"],
        env=os.environ,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
    )
    stdout, stderr = give_perm.communicate(python_code)
    code = give_perm.wait()

    return stdout, stderr, code


def create_dataset(dataset_id, dataset_name, table_id, database, user_access_type):
    _code = textwrap.dedent(
        f"""
        import uuid
        from django.db import connections
        from dataworkspace.apps.core.models import Database
        from dataworkspace.apps.datasets.models import (
            DataSet,
            SourceTable,
            DatasetReferenceCode,
        )
        from dataworkspace.apps.datasets.constants import DataSetType
        reference_code, _ = DatasetReferenceCode.objects.get_or_create(code='TEST')
        dataset, _ = DataSet.objects.update_or_create(
            id="{dataset_id}",
            defaults=dict(
                name="{dataset_name}",
                description="test_desc",
                short_description="test_short_desc",
                slug="{dataset_name}",
                published=True,
                reference_code=reference_code,
                type=DataSetType.MASTER,
                user_access_type="{user_access_type}"
            ),
        )
        source_table, _ = SourceTable.objects.update_or_create(
            id="{table_id}",
            defaults=dict(
                dataset=dataset,
                database=Database.objects.get(memorable_name="{database}"),
                schema="public",
                table="{dataset_name}",
            ),
        )
        with connections["{database}"].cursor() as cursor:
            cursor.execute("CREATE TABLE IF NOT EXISTS {dataset_name} (id int primary key)")
    """
    ).encode("ascii")
    # pylint: disable=consider-using-with
    give_perm = subprocess.Popen(
        ["django-admin", "shell"],
        env=os.environ,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
    )
    stdout, stderr = give_perm.communicate(_code)
    code = give_perm.wait()
    return stdout, stderr, code


def set_dataset_access_type(dataset_id, user_access_type):
    _code = textwrap.dedent(
        f"""
        from dataworkspace.apps.datasets.models import DataSet

        print(DataSet.objects.filter(id="{dataset_id}"))
        DataSet.objects.filter(id="{dataset_id}").update(user_access_type="{user_access_type}")
    """
    ).encode("ascii")
    # pylint: disable=consider-using-with
    give_perm = subprocess.Popen(
        ["django-admin", "shell"],
        env=os.environ,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
    )
    stdout, stderr = give_perm.communicate(_code)
    code = give_perm.wait()
    return stdout, stderr, code


def reset_data_explorer_credentials(user_sso_id):
    _code = textwrap.dedent(
        f"""
        import mock
        from django.contrib.auth.models import User
        from dataworkspace.apps.explorer.admin import clear_tool_cached_credentials

        clear_tool_cached_credentials(
            modeladmin=mock.Mock(),
            request=mock.Mock(),
            queryset=User.objects.filter(
                profile__sso_id='{user_sso_id}'
            ),
        )
    """
    ).encode("ascii")
    # pylint: disable=consider-using-with
    give_perm = subprocess.Popen(
        ["django-admin", "shell"],
        env=os.environ,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
    )
    stdout, stderr = give_perm.communicate(_code)
    code = give_perm.wait()
    return stdout, stderr, code


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
                    self.send_response(200, message="This is the login page")

                params = parse_qs(self.path.split("?")[1])

                location = params["redirect_uri"][0]
                state = params["state"][0]
                latest_code = next(codes)

                self.send_response(302)
                self.send_header("Location", f"{location}?state={state}&code={latest_code}")
                self.end_headers()

            def handle_token(self):
                nonlocal latest_code

                body = self.rfile.read(int(self.headers["Content-Length"])).decode("ascii")

                data = parse_qs(body)
                if data["code"][0] != latest_code:
                    self.send_response(403)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b"{}")

                token = next(tokens)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()

                response = BytesIO()
                response.write(json.dumps({"access_token": token}).encode("ascii"))

                self.wfile.write(response.getvalue())

            def handle_me(self):
                if self.headers["authorization"] in auth_to_me:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()

                    response = BytesIO()
                    response.write(
                        json.dumps(auth_to_me[self.headers["authorization"]]).encode("ascii")
                    )

                    self.wfile.write(response.getvalue())
                    return

                self.send_response(403)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b"{}")

            def do_GET(self):
                if self.path.startswith("/o/authorize"):
                    self.handle_authorize()
                elif self.path.startswith("/api/v1/user/me"):
                    self.handle_me()
                else:
                    raise ValueError(f"Unknown path: {self.path}")

            def do_POST(self):
                if self.path.startswith("/o/token"):
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


class ZendeskServer(multiprocessing.Process):
    def run(self):
        submitted_tickets = []

        class ZendeskHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                nonlocal submitted_tickets
                if self.path == "/_meta/read-submitted-tickets":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()

                    response = BytesIO()
                    response.write(json.dumps(submitted_tickets).encode("ascii"))

                    self.wfile.write(response.getvalue())
                    return

                self.send_response(200)
                self.end_headers()

            def do_POST(self):
                if self.path == "/api/v2/tickets.json":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()

                    submitted_tickets.append(
                        json.loads(
                            self.rfile.read(int(self.headers["content-length"])).decode("ascii")
                        )
                    )

                    with open("test/stubs/zendesk/create-ticket.json", "rb") as stub:
                        response = BytesIO()
                        response.write(stub.read())

                    self.wfile.write(response.getvalue())
                    return

                self.send_response(500)
                self.end_headers()

        httpd = HTTPServer(("0.0.0.0", 8006), ZendeskHandler)
        httpd.serve_forever()


@contextmanager
def create_zendesk():
    proc = ZendeskServer()
    proc.start()

    yield proc

    proc.kill()
