import asyncio

from base64 import urlsafe_b64decode
import os
import signal
import textwrap

import aiohttp
import elasticsearch
from aiohttp import web
from elasticsearch import AsyncElasticsearch, helpers
from lxml import html
import redis.asyncio as redis


def client_session():
    session = aiohttp.ClientSession()

    async def _cleanup_session():
        await session.close()
        await asyncio.sleep(0.25)

    return session, _cleanup_session


async def create_sso(is_logged_in, codes, tokens, auth_to_me):
    number_of_times = 0
    latest_code = None

    async def handle_authorize(request):
        nonlocal number_of_times
        nonlocal latest_code

        number_of_times += 1

        if not is_logged_in:
            return web.Response(status=200, text="This is the login page")

        state = request.query["state"]
        latest_code = next(codes)
        return web.Response(
            status=302,
            headers={
                "Location": request.query["redirect_uri"] + f"?state={state}&code={latest_code}"
            },
        )

    async def handle_token(request):
        if (await request.post())["code"] != latest_code:
            return web.json_response({}, status=403)

        token = next(tokens)
        return web.json_response({"access_token": token}, status=200)

    async def handle_me(request):
        if request.headers["authorization"] in auth_to_me:
            return web.json_response(auth_to_me[request.headers["authorization"]], status=200)

        return web.json_response({}, status=403)

    sso_app = web.Application()
    sso_app.add_routes(
        [
            web.get("/o/authorize/", handle_authorize),
            web.post("/o/token/", handle_token),
            web.get("/api/v1/user/me/", handle_me),
        ]
    )
    sso_runner = web.AppRunner(sso_app)
    await sso_runner.setup()
    sso_site = web.TCPSite(sso_runner, "0.0.0.0", 8005)
    await sso_site.start()

    def get_number_of_times():
        return number_of_times

    return sso_runner.cleanup, get_number_of_times


async def create_server(port, routes):
    app = web.Application()
    app.add_routes(routes)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    return runner.cleanup


async def create_mirror():
    async def handle(request):
        return web.Response(text=f"Mirror path: {request.path}", status=200)

    mirror_app = web.Application()
    mirror_app.add_routes([web.get("/{path:.*}", handle)])
    mirror_runner = web.AppRunner(mirror_app)
    await mirror_runner.setup()
    mirror_site = web.TCPSite(mirror_runner, "0.0.0.0", 8006)
    await mirror_site.start()

    return mirror_runner.cleanup


async def create_sentry():
    sentry_requests = []

    async def handle(request):
        nonlocal sentry_requests
        sentry_requests.append(request)
        return web.Response(text="OK", status=200)

    sentry_app = web.Application()
    sentry_app.add_routes([web.post("/{path:.*}", handle)])
    sentry_runner = web.AppRunner(sentry_app)
    await sentry_runner.setup()
    sentry_site = web.TCPSite(sentry_runner, "0.0.0.0", 8009)
    await sentry_site.start()

    return sentry_runner.cleanup, sentry_requests


async def create_superset():
    superset_requests = []

    async def handle(request):
        nonlocal superset_requests
        superset_requests.append(request)
        return web.Response(text="OK", status=200)

    superset_app = web.Application()
    superset_app.add_routes([web.get("/{path:.*}", handle)])
    superset_runner = web.AppRunner(superset_app)
    await superset_runner.setup()
    superset_site = web.TCPSite(superset_runner, "0.0.0.0", 8008)
    await superset_site.start()

    return superset_runner.cleanup, superset_requests


async def create_mlflow():
    mlflow_requests = []

    async def handle(request):
        nonlocal mlflow_requests
        mlflow_requests.append(request)
        return web.Response(text="OK", status=200)

    mlflow_app = web.Application()
    mlflow_app.add_routes([web.get("/{path:.*}", handle)])
    mlflow_runner = web.AppRunner(mlflow_app)
    await mlflow_runner.setup()
    mlflow_site = web.TCPSite(mlflow_runner, "0.0.0.0", 8004)
    await mlflow_site.start()

    return mlflow_runner.cleanup, mlflow_requests


# Run the application as close as possible to production
# The environment must be the same as in the Dockerfile
async def create_application(env=lambda: {}):
    proc = await asyncio.create_subprocess_exec(
        "/dataworkspace/start-test.sh",
        env={**os.environ, **env()},
        preexec_fn=os.setsid,
    )

    async def _cleanup_application():
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            await asyncio.sleep(3)
            if os.path.exists("/home/django/celerybeat.pid"):
                # pylint: disable=unspecified-encoding
                with open("/home/django/celerybeat.pid") as f:
                    print(f.read())
                try:
                    os.unlink("/home/django/celerybeat.pid")
                except FileNotFoundError:
                    pass
        except ProcessLookupError:
            pass

    return _cleanup_application


async def make_all_tools_visible():
    python_code = textwrap.dedent(
        """\
        from dataworkspace.apps.applications.models import (
            ApplicationTemplate,
        )
        ApplicationTemplate.objects.all().update(visible=True)
        """
    ).encode("ascii")
    make_visible = await asyncio.create_subprocess_shell(
        "django-admin shell",
        env=os.environ,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await make_visible.communicate(python_code)
    code = await make_visible.wait()

    return stdout, stderr, code


async def until_succeeds(url):
    loop = asyncio.get_running_loop()
    fail_if_later = loop.time() + 120
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(connect=1.0)) as session:
        while True:
            try:
                async with session.request("GET", url) as response:
                    response.raise_for_status()
            except (aiohttp.ClientConnectorError, aiohttp.ClientResponseError):
                if loop.time() >= fail_if_later:
                    raise
                await asyncio.sleep(0.1)
            else:
                break


async def until_non_202(session, url):
    for _ in range(0, 600):
        async with session.request("GET", url) as response:
            if response.status != 202:
                return
        await asyncio.sleep(0.1)

    raise Exception()


async def flush_database():
    await (  # noqa
        await asyncio.create_subprocess_shell(
            "django-admin flush --no-input --database default", env=os.environ
        )
    ).wait()


async def flush_redis():
    redis_pool = redis.from_url("redis://data-workspace-redis:6379")
    async with redis_pool as conn:
        await conn.execute_command("FLUSHDB")


async def give_user_superuser_perms():
    python_code = textwrap.dedent(
        """\
        from django.contrib.auth.models import (
            User,
        )
        user = User.objects.get(profile__sso_id="7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2")
        user.is_superuser = True
        user.save()
        """
    ).encode("ascii")
    give_perm = await asyncio.create_subprocess_shell(
        "django-admin shell",
        env=os.environ,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await give_perm.communicate(python_code)
    code = await give_perm.wait()

    return stdout, stderr, code


async def give_user_app_perms():
    python_code = textwrap.dedent(
        """\
        from django.contrib.auth.models import (
            Permission,
        )
        from django.contrib.auth.models import (
            User,
        )
        from django.contrib.contenttypes.models import (
            ContentType,
        )
        from dataworkspace.apps.applications.models import (
            ApplicationInstance,
        )
        permission = Permission.objects.get(
            codename='start_all_applications',
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        user = User.objects.get(profile__sso_id="7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2")
        user.user_permissions.add(permission)
        """
    ).encode("ascii")
    give_perm = await asyncio.create_subprocess_shell(
        "django-admin shell",
        env=os.environ,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await give_perm.communicate(python_code)
    code = await give_perm.wait()

    return stdout, stderr, code


async def give_user_visualisation_developer_perms():
    python_code = textwrap.dedent(
        """\
        from django.contrib.auth.models import (
            Permission,
        )
        from django.contrib.auth.models import (
            User,
        )
        from django.contrib.contenttypes.models import (
            ContentType,
        )
        from dataworkspace.apps.applications.models import (
            ApplicationInstance,
        )
        permission = Permission.objects.get(
            codename='develop_visualisations',
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        user = User.objects.get(profile__sso_id="7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2")
        user.user_permissions.add(permission)
        """
    ).encode("ascii")
    give_perm = await asyncio.create_subprocess_shell(
        "django-admin shell",
        env=os.environ,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await give_perm.communicate(python_code)
    code = await give_perm.wait()

    return stdout, stderr, code


async def create_metadata_table():
    python_code = textwrap.dedent(
        """\
        from django.db import connections
        with connections["my_database"].cursor() as cursor:
            cursor.execute(
                '''
                CREATE SCHEMA IF NOT EXISTS dataflow;
                CREATE TABLE IF NOT EXISTS dataflow.metadata (
                    id int, table_schema text, table_name text,
                    source_data_modified_utc timestamp, dataflow_swapped_tables_utc timestamp,
                    data_type int
                );
                '''
            )
        """
    ).encode("ascii")
    give_perm = await asyncio.create_subprocess_shell(
        "django-admin shell",
        env=os.environ,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await give_perm.communicate(python_code)
    code = await give_perm.wait()

    return stdout, stderr, code


async def create_private_dataset(
    database, dataset_type, dataset_id, dataset_name, table_id, table_name
):
    python_code = textwrap.dedent(
        f"""\
        from dataworkspace.apps.core.models import Database
        from dataworkspace.apps.datasets.models import (
            DataSet,
            SourceTable,
            DatasetReferenceCode,
        )
        from dataworkspace.apps.datasets.constants import DataSetType
        reference_code, _ = DatasetReferenceCode.objects.get_or_create(code='TEST')
        dataset = DataSet.objects.create(
            name="{dataset_name}",
            description="test_desc",
            short_description="test_short_desc",
            slug="{dataset_name}",
            id="{dataset_id}",
            published=True,
            reference_code=reference_code,
            type=DataSetType.{dataset_type}.value,
        )
        SourceTable.objects.create(
            id="{table_id}",
            dataset=dataset,
            database=Database.objects.get(memorable_name="{database}"),
            schema="public",
            table="{table_name}",
        )
        """
    ).encode("ascii")

    give_perm = await asyncio.create_subprocess_shell(
        "django-admin shell",
        env=os.environ,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await give_perm.communicate(python_code)
    code = await give_perm.wait()

    return stdout, stderr, code


async def create_visusalisation(visualisation_name, user_access_type, link_type, link_identifier):
    python_code = textwrap.dedent(
        f"""\
        from dataworkspace.apps.core.models import Database
        from dataworkspace.apps.datasets.models import (
            VisualisationCatalogueItem, VisualisationLink
        )
        visualisation = VisualisationCatalogueItem.objects.create(
            name="{visualisation_name}",
            description="test_desc",
            short_description="test_short_desc",
            slug="{visualisation_name}",
            published=True,
            user_access_type="{user_access_type}",
        )
        VisualisationLink.objects.create(
            name="{visualisation_name}_link",
            identifier="{link_identifier}",
            visualisation_catalogue_item=visualisation,
            visualisation_type="{link_type}",
        )
        """
    ).encode("ascii")

    give_perm = await asyncio.create_subprocess_shell(
        "django-admin shell",
        env=os.environ,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await give_perm.communicate(python_code)
    code = await give_perm.wait()

    return stdout, stderr, code


async def give_user_dataset_perms(name):
    python_code = textwrap.dedent(
        f"""\
        from django.contrib.auth.models import (
            User,
        )
        from dataworkspace.apps.datasets.models import (
            DataSet,
            DataSetUserPermission,
        )
        user = User.objects.get(profile__sso_id="7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2")
        dataset = DataSet.objects.get(
            name="{name}",
        )
        DataSetUserPermission.objects.create(
            dataset=dataset,
            user=user,
        )
        """
    ).encode("ascii")

    give_perm = await asyncio.create_subprocess_shell(
        "django-admin shell",
        env=os.environ,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await give_perm.communicate(python_code)
    code = await give_perm.wait()

    return stdout, stderr, code


async def dataset_finder_opt_in_dataset(schema, table, opted_in=True):
    python_code = textwrap.dedent(
        f"""\
        from dataworkspace.apps.datasets.models import (
            SourceTable,
        )
        st = SourceTable.objects.get(
            schema="{schema}",
            table="{table}",
        )
        st.dataset_finder_opted_in = {opted_in}
        st.save()
        """
    ).encode("ascii")

    give_perm = await asyncio.create_subprocess_shell(
        "django-admin shell",
        env=os.environ,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await give_perm.communicate(python_code)
    code = await give_perm.wait()

    return stdout, stderr, code


async def give_user_visualisation_perms(name):
    python_code = textwrap.dedent(
        f"""\
        from django.contrib.auth.models import (
            User,
        )
        from dataworkspace.apps.applications.models import VisualisationTemplate
        from dataworkspace.apps.datasets.models import VisualisationUserPermission, VisualisationCatalogueItem
        user = User.objects.get(profile__sso_id="7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2")
        visualisationtemplate = VisualisationTemplate.objects.get(
            host_basename="{name}",
        )
        VisualisationUserPermission.objects.create(
            user=user,
            visualisation=VisualisationCatalogueItem.objects.get(visualisation_template=visualisationtemplate),
        )
        """
    ).encode("ascii")

    give_perm = await asyncio.create_subprocess_shell(
        "django-admin shell",
        env=os.environ,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await give_perm.communicate(python_code)
    code = await give_perm.wait()

    return stdout, stderr, code


async def create_visualisation_echo(name):
    python_code = textwrap.dedent(
        f"""\
        from dataworkspace.apps.applications.models import (
            VisualisationTemplate,
        )
        from dataworkspace.apps.datasets.models import VisualisationCatalogueItem
        template = VisualisationTemplate.objects.create(
            host_basename="{name}",
            nice_name="Test {name}",
            spawner="PROCESS",
            spawner_options='{{"CMD":["python3", "/test/echo_server.py"]}}',
            spawner_time=60,
            gitlab_project_id=3,
            visible=True
        )
        VisualisationCatalogueItem.objects.create(
            name="Test {name}",
            user_access_type="REQUIRES_AUTHORIZATION",
            slug="{name}",
            visualisation_template=template
        )
        """
    ).encode("ascii")
    give_perm = await asyncio.create_subprocess_shell(
        "django-admin shell",
        env=os.environ,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await give_perm.communicate(python_code)
    code = await give_perm.wait()

    return stdout, stderr, code


async def toggle_visualisation_visibility(name, visible=True):
    python_code = textwrap.dedent(
        f"""\
from dataworkspace.apps.applications.models import (
    VisualisationTemplate,
)
template = VisualisationTemplate.objects.get(
    host_basename="{name}"
)
template.visible = {visible}
template.save()
        """
    ).encode("ascii")
    give_perm = await asyncio.create_subprocess_shell(
        "django-admin shell",
        env=os.environ,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await give_perm.communicate(python_code)
    code = await give_perm.wait()

    return stdout, stderr, code


async def set_visualisation_wrap(name, wrap):
    python_code = textwrap.dedent(
        f"""\
        from dataworkspace.apps.applications.models import (
            VisualisationTemplate,
        )
        template = VisualisationTemplate.objects.get(
            host_basename="{name}"
        )
        template.wrap = "{wrap}"
        template.save()
        """
    ).encode("ascii")
    give_perm = await asyncio.create_subprocess_shell(
        "django-admin shell",
        env=os.environ,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await give_perm.communicate(python_code)
    code = await give_perm.wait()

    return stdout, stderr, code


async def create_visualisation_dataset(name, gitlab_project_id):
    python_code = textwrap.dedent(
        f"""\
        from dataworkspace.apps.applications.models import (
            VisualisationTemplate,
        )
        from dataworkspace.apps.datasets.models import VisualisationCatalogueItem
        template = VisualisationTemplate.objects.create(
            host_basename="{name}",
            nice_name="Test {name}",
            spawner="PROCESS",
            spawner_options='{{"CMD":["python3", "/test/dataset_server.py"]}}',
            spawner_time=60,
            gitlab_project_id={gitlab_project_id},
        )
        VisualisationCatalogueItem.objects.create(
            name="Test {name}",
            user_access_type="REQUIRES_AUTHORIZATION",
            slug="{name}",
            visualisation_template=template
        )
        """
    ).encode("ascii")
    give_perm = await asyncio.create_subprocess_shell(
        "django-admin shell",
        env=os.environ,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await give_perm.communicate(python_code)
    code = await give_perm.wait()

    return stdout, stderr, code


async def ensure_team_created(team_name: str):
    python_code = textwrap.dedent(
        f"""\

        from dataworkspace.apps.core.models import Team
        Team.objects.get_or_create(name="{team_name}")

        """
    ).encode("ascii")

    add_to_team = await asyncio.create_subprocess_shell(
        "django-admin shell",
        env=os.environ,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await add_to_team.communicate(python_code)
    code = await add_to_team.wait()

    return stdout, stderr, code


async def add_user_to_team(user_sso_id: str, team_name: str):
    python_code = textwrap.dedent(
        f"""\

        from django.contrib.auth import get_user_model
        from dataworkspace.apps.core.models import Team, TeamMembership

        User = get_user_model()

        user = User.objects.get(profile__sso_id="{user_sso_id}")

        team, _ = Team.objects.get_or_create(name="{team_name}")
        membership, _ = TeamMembership.objects.get_or_create(user=user, team=team)

        """
    ).encode("ascii")

    add_to_team = await asyncio.create_subprocess_shell(
        "django-admin shell",
        env=os.environ,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await add_to_team.communicate(python_code)
    code = await add_to_team.wait()

    return stdout, stderr, code


async def give_visualisation_dataset_perms(vis_name, dataset_name):
    python_code = textwrap.dedent(
        f"""\
        from django.contrib.auth.models import (
            User,
        )
        from dataworkspace.apps.applications.models import (
            ApplicationTemplate,
        )
        from dataworkspace.apps.datasets.models import (
            DataSet,
            DataSetApplicationTemplatePermission,
        )
        application_template = ApplicationTemplate.objects.get(host_basename="{vis_name}")
        dataset = DataSet.objects.get(
            name="{dataset_name}",
        )
        DataSetApplicationTemplatePermission.objects.create(
            application_template=application_template,
            dataset=dataset,
        )
        """
    ).encode("ascii")

    give_perm = await asyncio.create_subprocess_shell(
        "django-admin shell",
        env=os.environ,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await give_perm.communicate(python_code)
    code = await give_perm.wait()

    return stdout, stderr, code


async def give_visualisation_domain_perms(name, domains):
    python_code = textwrap.dedent(
        f"""\
        from dataworkspace.apps.applications.models import VisualisationTemplate
        from dataworkspace.apps.datasets.models import VisualisationCatalogueItem
        visualisationtemplate = VisualisationTemplate.objects.get(
            host_basename="{name}",
        )
        catalogue_item = VisualisationCatalogueItem.objects.get(
            visualisation_template=visualisationtemplate
        )
        catalogue_item.authorized_email_domains={str(domains)}
        catalogue_item.save()
        """
    ).encode("ascii")

    give_perm = await asyncio.create_subprocess_shell(
        "django-admin shell",
        env=os.environ,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await give_perm.communicate(python_code)
    code = await give_perm.wait()

    return stdout, stderr, code


async def set_waffle_flag(flag_name, everyone=True):
    python_code = textwrap.dedent(
        f"""
        from waffle.models import Flag

        flag = Flag.objects.create(name='{flag_name}', everyone={everyone})
        flag.save()
        """
    ).encode("ascii")

    give_perm = await asyncio.create_subprocess_shell(
        "django-admin shell",
        env=os.environ,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await give_perm.communicate(python_code)
    code = await give_perm.wait()

    return stdout, stderr, code


async def create_sample_datasets_and_visualisations():
    """Creates one of each type of dataset/visualisation

    WARNING: removes any pre-existing datasets/visualisations

    Creates 5 datasets/visualisations:
    1) Master dataset, available to all, with DIT source tag
    2) Master dataset, restricted access (with no grants), with HMRC source tag
    3) Datacut, available to all, with ONS source tag
    4) Reference data, available to all
    5) Visualisation, available to all.
    """
    python_code = textwrap.dedent(
        """
import random

from django.db import IntegrityError
import factory

from dataworkspace.apps.datasets.constants import DataSetType, TagType
from dataworkspace.apps.datasets.models import Tag
from dataworkspace.apps.datasets.models import DataSet
from dataworkspace.apps.datasets.models import ReferenceDataset
from dataworkspace.apps.datasets.models import VisualisationCatalogueItem
from dataworkspace.tests import factories


DataSet.objects.all().delete()
ReferenceDataset.objects.all().delete()
VisualisationCatalogueItem.objects.all().delete()

for dept in ('DIT', 'HMRC', 'ONS'):
    Tag.objects.get_or_create(name=dept)

source_tags = {st.name: st for st in Tag.objects.filter(type=TagType.SOURCE)}

def paragraph(_):
    from faker import Faker
    return Faker().paragraph(5)

try:
    master = factories.DataSetFactory(
        id=1,
        name="Master 1",
        slug="master-1",
        description=factory.LazyAttribute(paragraph),
        type=DataSetType.MASTER,
        published=True,
        user_access_type='REQUIRES_AUTHENTICATION',
    )
except IntegrityError:
    master = DataSet.objects.get(id=1)

master.tags.set([source_tags['DIT']])

try:
    master = factories.DataSetFactory(
        id=2,
        name="Master 2",
        slug="master-2",
        description=factory.LazyAttribute(paragraph),
        type=DataSetType.MASTER,
        published=True,
        user_access_type='REQUIRES_AUTHORIZATION',
    )
except IntegrityError:
    master = DataSet.objects.get(id=2)

master.tags.set([source_tags['HMRC']])

try:
    datacut = factories.DataSetFactory(
        id=3,
        name="Datacut 1",
        slug="datacut-1",
        description=factory.LazyAttribute(paragraph),
        type=DataSetType.DATACUT,
        published=True,
        user_access_type='REQUIRES_AUTHENTICATION',
    )
except IntegrityError:
    datacut = DataSet.objects.get(id=3)

datacut.tags.set([source_tags['ONS']])

try:
    factories.ReferenceDatasetFactory(
        id=1,
        name=f"Reference 1",
        slug=f"reference-1",
        description=factory.LazyAttribute(paragraph),
        published=True,
    )
except IntegrityError:
    pass

try:
    factories.VisualisationCatalogueItemFactory(
        id=1,
        name="Visualisation 1",
        description=factory.LazyAttribute(paragraph),
        published=True,
        user_access_type='REQUIRES_AUTHENTICATION',
    )
except IntegrityError:
    pass
        """
    ).encode("ascii")

    give_perm = await asyncio.create_subprocess_shell(
        "django-admin shell",
        env=os.environ,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await give_perm.communicate(python_code)
    code = await give_perm.wait()

    return stdout, stderr, code


def find_search_filter_labels(html_):
    doc = html.fromstring(html_)
    return {label.strip() for label in doc.xpath('//div[@id="live-search-wrapper"]//label/text()')}


async def create_application_db_user():
    """
    Create an application template, application instance, application db user
    and a postgres user. Used for testing syncing application logs.
    """
    python_code = textwrap.dedent(
        '''
            import uuid
            from django.db import connections
            from django.contrib.auth.models import User
            from dataworkspace.apps.core.models import DatabaseUser
            from dataworkspace.apps.datasets.models import Database
            from dataworkspace.apps.applications.utils import create_user_from_sso
            user = create_user_from_sso(
                '7f93c2c7-bc32-43f3-87dc-40d0b8fb2cd2',
                'test@test.com',
                [],
                'Peter',
                'Piper',
                'active',
                check_tools_access_if_user_exists=False,
            )
            user.is_staff = True
            user.is_superuser = True
            user.save()

            Database.objects.get_or_create(memorable_name='my_database')
            DatabaseUser.objects.get_or_create(
                owner=user,
                username='postgres',
            )

            with connections["my_database"].cursor() as cursor:
                cursor.execute(
                    """
                    ALTER USER postgres SET pgaudit.log = 'ALL, -MISC';
                    ALTER USER postgres SET pgaudit.log_catalog = off;
                    """
                )
        '''
    ).encode("ascii")
    shell = await asyncio.create_subprocess_shell(
        "django-admin shell",
        env=os.environ,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await shell.communicate(python_code)
    code = await shell.wait()

    return stdout, stderr, code


async def create_query_logs():
    """
    Run some queries to generate the pgaudit logs
    """
    python_code = textwrap.dedent(
        """
        from django.db import connections
        with connections["my_database"].cursor() as cursor:
            cursor.execute('CREATE TABLE IF NOT EXISTS query_log_test (id INT, name TEXT);')
            cursor.execute("INSERT INTO query_log_test VALUES(1, 'a record');")
            cursor.execute('SELECT * FROM query_log_test;')
        """
    ).encode("ascii")

    shell = await asyncio.create_subprocess_shell(
        "django-admin shell",
        env=os.environ,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await shell.communicate(python_code)
    code = await shell.wait()

    return stdout, stderr, code


async def sync_query_logs():
    """
    Run the celery task to sync tool query audit logs
    :return:
    """
    python_code = textwrap.dedent(
        """
        from django.core.cache import cache
        from dataworkspace.apps.applications.utils import _do_sync_tool_query_logs
        cache.delete('query_tool_logs_last_run')
        _do_sync_tool_query_logs()
        """
    ).encode("ascii")
    shell = await asyncio.create_subprocess_shell(
        "django-admin shell",
        env=os.environ,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await shell.communicate(python_code)
    code = await shell.wait()
    return stdout, stderr, code


async def setup_elasticsearch_indexes():
    """
    Setup some Elasticsearch indexes for Dataset Finder tests
    """
    client = AsyncElasticsearch(hosts=[{"host": "data-workspace-es", "port": 9200}])
    known_index_name = "20200101t120000--public--test_dataset--1"
    known_index_alias = "public--test_dataset"
    incoming_index_name = "20200101t120000--public--test_dataset--2"

    try:
        await client.indices.delete(known_index_name)
    except elasticsearch.exceptions.NotFoundError:
        pass

    await client.indices.create(known_index_name)

    success, failed = await helpers.async_bulk(
        client,
        (
            {
                "_index": known_index_name,
                "_id": i,
                "id": i,
                "data": f"my data {i}",
                "_all": f"my data {i}",
            }
            for i in range(100)
        ),
        stats_only=True,
    )
    assert success == 100
    assert failed == 0

    success, failed = await helpers.async_bulk(
        client,
        (
            {
                "_index": incoming_index_name,
                "_id": i,
                "id": i,
                "data": f"new row {i}",
                "_all": f"new row {i}",
            }
            for i in range(100)
        ),
        stats_only=True,
    )
    assert success == 100
    assert failed == 0

    await client.indices.put_alias(known_index_name, known_index_alias)

    await asyncio.sleep(2)


def b64_decode(b64_bytes):
    return urlsafe_b64decode(b64_bytes + (b"=" * ((4 - len(b64_bytes) % 4) % 4)))


async def add_user_to_mlflow_instance(user_sso_id: str, instance_name: str):
    python_code = textwrap.dedent(
        f"""\

        from django.contrib.auth import get_user_model
        from dataworkspace.apps.core.models import MLFlowInstance, MLFlowAuthorisedUser

        User = get_user_model()

        user = User.objects.get(profile__sso_id="{user_sso_id}")

        instance, _ = MLFlowInstance.objects.get_or_create(
            name="{instance_name}", hostname="mlflow--{instance_name}--internal.dataworkspace.test:8000"
        )
        _, _ = MLFlowAuthorisedUser.objects.get_or_create(user=user, instance=instance)

        """
    ).encode("ascii")

    add_to_mlflow_instance = await asyncio.create_subprocess_shell(
        "django-admin shell",
        env=os.environ,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await add_to_mlflow_instance.communicate(python_code)
    code = await add_to_mlflow_instance.wait()

    return stdout, stderr, code
