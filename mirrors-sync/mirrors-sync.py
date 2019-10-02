import asyncio
import contextlib
from collections import (
    namedtuple,
)
from datetime import (
    datetime,
)
import hashlib
import hmac
import html
import json
import logging
import os
import re
import sys
import signal
from time import (
    time,
)
import urllib

import aiohttp
import aioxmlrpc.client
from bs4 import (
    BeautifulSoup,
)

AwsCredentials = namedtuple('AwsCredentials', [
    'access_key_id', 'secret_access_key', 'pre_auth_headers',
])

S3Bucket = namedtuple('AwsS3Bucket', [
    'region', 'host', 'verify_certs', 'name',
])

S3Context = namedtuple('Context', [
    'session', 'credentials', 'bucket',
])


async def aws_request(logger, session, service, region, host, verify_certs,
                      credentials, method, full_path, query, api_pre_auth_headers,
                      payload, payload_hash):
    creds = await credentials(logger, session)
    pre_auth_headers = {
        **api_pre_auth_headers,
        **creds.pre_auth_headers,
    }

    headers = _aws_sig_v4_headers(
        creds.access_key_id, creds.secret_access_key, pre_auth_headers,
        service, region, host, method, full_path, query, payload_hash,
    )

    querystring = urllib.parse.urlencode(query, safe='~', quote_via=urllib.parse.quote)
    encoded_path = urllib.parse.quote(full_path, safe='/~')
    url = f'https://{host}{encoded_path}' + (('?' + querystring) if querystring else '')

    # aiohttp seems to treat both ssl=False and ssl=True as config to _not_ verify certificates
    ssl = {} if verify_certs else {'ssl': False}
    return session.request(method, url, headers=headers, data=payload, **ssl)


def _aws_sig_v4_headers(access_key_id, secret_access_key, pre_auth_headers,
                        service, region, host, method, path, query, payload_hash):
    algorithm = 'AWS4-HMAC-SHA256'

    now = datetime.utcnow()
    amzdate = now.strftime('%Y%m%dT%H%M%SZ')
    datestamp = now.strftime('%Y%m%d')
    credential_scope = f'{datestamp}/{region}/{service}/aws4_request'

    pre_auth_headers_lower = {
        header_key.lower(): ' '.join(header_value.split())
        for header_key, header_value in pre_auth_headers.items()
    }
    required_headers = {
        'host': host,
        'x-amz-content-sha256': payload_hash,
        'x-amz-date': amzdate,
    }
    headers = {**pre_auth_headers_lower, **required_headers}
    header_keys = sorted(headers.keys())
    signed_headers = ';'.join(header_keys)

    def signature():
        def canonical_request():
            canonical_uri = urllib.parse.quote(path, safe='/~')
            quoted_query = sorted(
                (urllib.parse.quote(key, safe='~'), urllib.parse.quote(value, safe='~'))
                for key, value in query.items()
            )
            canonical_querystring = '&'.join(f'{key}={value}' for key, value in quoted_query)
            canonical_headers = ''.join(f'{key}:{headers[key]}\n' for key in header_keys)

            return f'{method}\n{canonical_uri}\n{canonical_querystring}\n' + \
                   f'{canonical_headers}\n{signed_headers}\n{payload_hash}'

        def sign(key, msg):
            return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

        string_to_sign = f'{algorithm}\n{amzdate}\n{credential_scope}\n' + \
                         hashlib.sha256(canonical_request().encode('utf-8')).hexdigest()

        date_key = sign(('AWS4' + secret_access_key).encode('utf-8'), datestamp)
        region_key = sign(date_key, region)
        service_key = sign(region_key, service)
        request_key = sign(service_key, 'aws4_request')
        return sign(request_key, string_to_sign).hex()

    return {
        **pre_auth_headers,
        'x-amz-date': amzdate,
        'x-amz-content-sha256': payload_hash,
        'Authorization': f'{algorithm} Credential={access_key_id}/{credential_scope}, '
                         f'SignedHeaders={signed_headers}, Signature=' + signature(),
    }


async def s3_request_full(logger, context, method, path, query, api_pre_auth_headers,
                          payload, payload_hash):

    with logged(logger, 'Request: %s %s %s %s %s',
                [method, context.bucket.host, path, query, api_pre_auth_headers]):
        async with await _s3_request(logger, context, method, path, query, api_pre_auth_headers,
                                     payload, payload_hash) as result:
            return result, await result.read()


async def _s3_request(logger, context, method, path, query, api_pre_auth_headers,
                      payload, payload_hash):
    bucket = context.bucket
    return await aws_request(
        logger, context.session, 's3', bucket.region, bucket.host, bucket.verify_certs,
        context.credentials, method, f'/{bucket.name}{path}', query, api_pre_auth_headers,
        payload, payload_hash)


def s3_hash(payload):
    return hashlib.sha256(payload).hexdigest()


@contextlib.contextmanager
def logged(logger, message, logger_args):
    try:
        logger.debug(message + '...', *logger_args)
        status = 'done'
        logger_func = logger.debug
        yield
    except asyncio.CancelledError:
        status = 'cancelled'
        logger_func = logger.debug
        raise
    except BaseException:
        status = 'failed'
        logger_func = logger.exception
        raise
    finally:
        logger_func(message + '... (%s)', *(logger_args + [status]))


def get_ecs_role_credentials(url):

    aws_access_key_id = None
    aws_secret_access_key = None
    token = None
    expiration = datetime(1900, 1, 1)

    async def get(logger, session):
        nonlocal aws_access_key_id
        nonlocal aws_secret_access_key
        nonlocal token
        nonlocal expiration

        now = datetime.now()

        if now > expiration:
            method = 'GET'
            with logged(logger, 'Requesting temporary credentials from %s', [url]):
                async with session.request(method, url) as response:
                    response.raise_for_status()
                    creds = json.loads(await response.read())

            aws_access_key_id = creds['AccessKeyId']
            aws_secret_access_key = creds['SecretAccessKey']
            token = creds['Token']
            expiration = datetime.strptime(creds['Expiration'], '%Y-%m-%dT%H:%M:%SZ')

        return AwsCredentials(
            access_key_id=aws_access_key_id,
            secret_access_key=aws_secret_access_key,
            pre_auth_headers={
                'x-amz-security-token': token,
            },
        )

    return get


async def async_main(loop, logger):
    session = aiohttp.ClientSession(loop=loop)

    credentials = get_ecs_role_credentials(
        'http://169.254.170.2' + os.environ['AWS_CONTAINER_CREDENTIALS_RELATIVE_URI'])
    bucket = S3Bucket(
        region=os.environ['MIRRORS_BUCKET_REGION'],
        host=os.environ['MIRRORS_BUCKET_HOST'],
        verify_certs=True,
        name=os.environ['MIRRORS_BUCKET_NAME'],
    )
    s3_context = S3Context(
        session=session,
        credentials=credentials,
        bucket=bucket,
    )

    if os.environ['MIRROR_ANACONDA_R'] == 'True':
        await conda_mirror(logger, session, s3_context, 'https://conda.anaconda.org/r/', 'r/')

    if os.environ['MIRROR_ANACONDA_CONDA_FORGE'] == 'True':
        await conda_mirror(logger, session, s3_context, 'https://conda.anaconda.org/conda-forge/', 'conda-forge/')

    if os.environ['MIRROR_ANACONDA_CONDA_ANACONDA'] == 'True':
        await conda_mirror(logger, session, s3_context, 'https://conda.anaconda.org/anaconda/', 'anaconda/')

    if os.environ['MIRROR_CRAN'] == 'True':
        await cran_mirror(logger, session, s3_context)

    if os.environ['MIRROR_PYPI'] == 'True':
        await pypi_mirror(logger, session, s3_context)

    await session.close()
    await asyncio.sleep(0)


async def pypi_mirror(logger, session, s3_context):

    def normalise(name):
        return re.sub(r'[-_.]+', '-', name).lower()

    source_base = 'https://pypi.python.org'
    xmlrpc_client = aioxmlrpc.client.ServerProxy(source_base + '/pypi')

    pypi_prefix = 'pypi/'

    # We may have overlap, but that's fine
    sync_changes_after_key = '__sync_changes_after'
    # Paranoia: the reference implementation at https://bitbucket.org/loewis/pep381client has -1
    started = int(time()) - 1

    # Determine after when to fetch changes. There is an eventual consistency issue storing this
    # on S3, but at worst we'll be unnecessarily re-fetching updates, rather than missing them.
    # Plus, given the time to run a sync and frequency, this is unlikely anyway
    response, data = await s3_request_full(
        logger, s3_context, 'GET', '/' + pypi_prefix + sync_changes_after_key, {}, {}, b'', s3_hash(b''))
    sync_changes_after = \
        int(data) if response.status == 200 else \
        0

    # changelog doesn't seem to have changes older than two years, so for all projects on initial
    # import, we need to call list_packages
    project_names_with_duplicates = \
        (await xmlrpc_client.list_packages()) if sync_changes_after == 0 else \
        [change[0] for change in await xmlrpc_client.changelog(sync_changes_after)]
    project_names = sorted(list(set(project_names_with_duplicates)))

    queue = asyncio.Queue()

    for project_name in project_names:
        normalised_project_name = normalise(project_name)
        await queue.put((normalised_project_name, source_base + f'/simple/{normalised_project_name}/'))

    async def transfer_task():
        while True:
            project_name, project_url = await queue.get()
            logger.debug('Transferring project %s %s', project_name, project_url)

            try:
                async with session.get(project_url) as response:
                    response.raise_for_status()
                    data = await response.read()

                soup = BeautifulSoup(data, 'html.parser')
                links = soup.find_all('a')
                link_data = []

                for link in links:
                    absolute = link.get('href')
                    absolute_no_frag, frag = absolute.split('#')
                    filename = str(link.string)
                    python_version = link.get('data-requires-python')
                    has_python_version = python_version is not None
                    python_version_attr = \
                        ' data-requires-python="' + html.escape(python_version) + '"' if has_python_version else \
                        ''

                    async with session.get(absolute_no_frag) as response:
                        response.raise_for_status()
                        file_data = await response.read()

                    s3_path = f'/{pypi_prefix}{project_name}/{filename}'
                    response, _ = await s3_request_full(
                        logger, s3_context, 'PUT', s3_path, {}, {}, file_data, s3_hash(file_data))
                    response.raise_for_status()

                    link_data.append((s3_path, filename, frag, python_version_attr))

                html_str = \
                    '<!DOCTYPE html>' + \
                    '<html>' + \
                    '<body>' + \
                    ''.join([
                        f'<a href="https://{s3_context.bucket.host}/{s3_context.bucket.name}{s3_path}'
                        f'#{frag}"{python_version_attr}>{filename}</a>'
                        for s3_path, filename, frag, python_version_attr in link_data
                    ]) + \
                    '</body>' + \
                    '</html>'
                html_bytes = html_str.encode('ascii')
                s3_path = f'/{pypi_prefix}{project_name}/'
                headers = {'Content-Type': 'text/html'}
                response, _ = await s3_request_full(
                    logger, s3_context, 'PUT', s3_path, {}, headers, html_bytes, s3_hash(html_bytes))
                response.raise_for_status()

            except Exception:
                logger.exception('Exception crawling %s', project_url)
            finally:
                queue.task_done()

    tasks = [
        asyncio.ensure_future(transfer_task()) for _ in range(0, 10)
    ]
    try:
        await queue.join()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.sleep(0)

    await xmlrpc_client.close()

    started_bytes = str(started).encode('ascii')
    response, _ = await s3_request_full(
        logger, s3_context, 'PUT', '/' + pypi_prefix + sync_changes_after_key, {}, {},
        started_bytes, s3_hash(started_bytes))
    response.raise_for_status()


async def cran_mirror(logger, session, s3_context):
    source_base = 'https://cran.ma.imperial.ac.uk/'
    source_base_url = source_base + 'web/packages/available_packages_by_name.html'
    source_base_parsed = urllib.parse.urlparse(source_base_url)
    cran_prefix = 'cran/'

    done = set()
    queue = asyncio.Queue()
    await queue.put(source_base_url)

    # Main package file. Maybe better parsing this than crawling HTML?
    package_index = 'src/contrib/PACKAGES'
    async with session.get(source_base + package_index) as response:
        response.raise_for_status()
        data = await response.read()
    response, _ = await s3_request_full(
        logger, s3_context, 'PUT', '/' + cran_prefix + package_index, {}, {}, data, s3_hash(data))
    response.raise_for_status()

    async def crawl(url):
        async with session.get(url) as response:
            response.raise_for_status()
            content_type = response.headers.get('Content-Type', None)
            data = await response.read()

        key_suffix = urllib.parse.urlparse(url).path[1:]  # Without leading /
        target_key = cran_prefix + key_suffix
        response, _ = await s3_request_full(
            logger, s3_context, 'PUT', '/' + target_key, {}, {}, data, s3_hash(data))
        response.raise_for_status()

        if content_type == 'text/html':
            soup = BeautifulSoup(data, 'html.parser')
            links = soup.find_all('a')
            for link in links:
                absolute = urllib.parse.urljoin(url, link.get('href'))
                absolute_no_frag = absolute.split('#')[0]
                is_done = (
                    urllib.parse.urlparse(absolute_no_frag).netloc == source_base_parsed.netloc and
                    absolute_no_frag not in done
                )
                if is_done:
                    await queue.put(absolute_no_frag)
                    done.add(absolute_no_frag)

    async def transfer_task():
        while True:
            url = await queue.get()
            try:
                crawl(url)
            except Exception:
                logger.exception('Exception crawling %s', url)
            finally:
                queue.task_done()

    tasks = [
        asyncio.ensure_future(transfer_task()) for _ in range(0, 10)
    ]
    try:
        await queue.join()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.sleep(0)


async def conda_mirror(logger, session, s3_context, source_base_url, s3_prefix):
    arch_dirs = ['noarch/', 'linux-64/']
    repodatas = []
    queue = asyncio.Queue()

    for arch_dir in arch_dirs:
        async with session.get(source_base_url + arch_dir + 'repodata.json') as response:
            response.raise_for_status()
            source_repodata_raw = await response.read()
            source_repodata = json.loads(source_repodata_raw)

            for package_suffix, _ in source_repodata['packages'].items():
                await queue.put(arch_dir + package_suffix)

            repodatas.append((arch_dir + 'repodata.json', source_repodata_raw))

        async with session.get(source_base_url + arch_dir + 'repodata.json.bz2') as response:
            response.raise_for_status()
            repodatas.append((arch_dir + 'repodata.json.bz2', await response.read()))

    async def transfer_task():
        while True:
            package_suffix = await queue.get()

            try:
                source_package_url = source_base_url + package_suffix
                target_package_key = s3_prefix + package_suffix

                async with session.get(source_package_url) as response:
                    response.raise_for_status()
                    data = await response.read()

                response, _ = await s3_request_full(
                    logger, s3_context, 'PUT', '/' + target_package_key, {}, {}, data, s3_hash(data))
                response.raise_for_status()
            except Exception:
                logger.exception('Exception transferring %s', package_suffix)
            finally:
                queue.task_done()

    tasks = [
        asyncio.ensure_future(transfer_task()) for _ in range(0, 10)
    ]
    try:
        await queue.join()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.sleep(0)

    for path, data in repodatas:
        target_repodata_key = s3_prefix + path
        response, _ = await s3_request_full(
            logger, s3_context, 'PUT', '/' + target_repodata_key, {}, {},
            data, s3_hash(data))
        response.raise_for_status()


def main():
    loop = asyncio.get_event_loop()

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    main_task = loop.create_task(async_main(loop, logger))
    loop.add_signal_handler(signal.SIGINT, main_task.cancel)
    loop.add_signal_handler(signal.SIGTERM, main_task.cancel)

    loop.run_until_complete(main_task)

    logger.debug('Exiting.')


if __name__ == '__main__':
    main()
