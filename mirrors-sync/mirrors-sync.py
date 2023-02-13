import asyncio
import contextlib
from collections import namedtuple
from datetime import datetime
import hashlib
import hmac
import html
import json
import logging
import os
import re
import sys
import signal
from time import time
import urllib
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
from lowhaio import HttpDataError, HttpConnectionError, Pool, buffered, streamed
from lowhaio_redirect import redirectable

AwsCredentials = namedtuple(
    "AwsCredentials", ["access_key_id", "secret_access_key", "pre_auth_headers"]
)

S3Bucket = namedtuple("AwsS3Bucket", ["region", "host", "name"])

S3Context = namedtuple("Context", ["request", "credentials", "bucket"])


async def aws_request(
    logger,
    request,
    service,
    region,
    host,
    credentials,
    method,
    full_path,
    query,
    api_pre_auth_headers,
    payload,
    payload_hash,
):
    creds = await credentials(logger, request)
    pre_auth_headers = api_pre_auth_headers + creds.pre_auth_headers

    headers = _aws_sig_v4_headers(
        creds.access_key_id,
        creds.secret_access_key,
        pre_auth_headers,
        service,
        region,
        host,
        method.decode("ascii"),
        full_path,
        query,
        payload_hash,
    )

    url = f"https://{host}{full_path}"

    return await request(method, url, headers=headers, params=query, body=payload)


async def empty_async_iterator():
    while False:
        yield


async def blackhole(body):
    # For some requests we just want to receive the bytes without allocating
    # to a contiguous buffer, so the connection gets replaced back to the
    # connection pool
    async for _ in body:  # noqa
        pass


def _aws_sig_v4_headers(
    access_key_id,
    secret_access_key,
    pre_auth_headers,
    service,
    region,
    host,
    method,
    path,
    query,
    payload_hash,
):
    algorithm = "AWS4-HMAC-SHA256"

    now = datetime.utcnow()
    amzdate = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = now.strftime("%Y%m%d")
    credential_scope = f"{datestamp}/{region}/{service}/aws4_request"

    pre_auth_headers_lower = tuple(
        (header_key.decode().lower(), " ".join(header_value.decode().split()))
        for header_key, header_value in pre_auth_headers
    )
    required_headers = (
        ("host", host),
        ("x-amz-content-sha256", payload_hash),
        ("x-amz-date", amzdate),
    )
    headers = sorted(pre_auth_headers_lower + required_headers)
    signed_headers = ";".join(key for key, _ in headers)

    def signature():
        def canonical_request():
            canonical_uri = urllib.parse.quote(path, safe="/~")
            quoted_query = sorted(
                (urllib.parse.quote(key, safe="~"), urllib.parse.quote(value, safe="~"))
                for key, value in query
            )
            canonical_querystring = "&".join(f"{key}={value}" for key, value in quoted_query)
            canonical_headers = "".join(f"{key}:{value}\n" for key, value in headers)

            return (
                f"{method}\n{canonical_uri}\n{canonical_querystring}\n"
                + f"{canonical_headers}\n{signed_headers}\n{payload_hash}"
            )

        def sign(key, msg):
            return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

        string_to_sign = (
            f"{algorithm}\n{amzdate}\n{credential_scope}\n"
            + hashlib.sha256(canonical_request().encode("utf-8")).hexdigest()
        )

        date_key = sign(("AWS4" + secret_access_key).encode("utf-8"), datestamp)
        region_key = sign(date_key, region)
        service_key = sign(region_key, service)
        request_key = sign(service_key, "aws4_request")
        return sign(request_key, string_to_sign).hex()

    return (
        (
            b"authorization",
            (
                f"{algorithm} Credential={access_key_id}/{credential_scope}, "
                f"SignedHeaders={signed_headers}, Signature=" + signature()
            ).encode("utf-8"),
        ),
        (b"x-amz-date", amzdate.encode("utf-8")),
        (b"x-amz-content-sha256", payload_hash.encode("utf-8")),
    ) + pre_auth_headers


async def s3_request_full(
    logger, context, method, path, query, api_pre_auth_headers, payload, payload_hash
):
    with logged(
        logger,
        "Request: %s %s %s %s %s",
        [method, context.bucket.host, path, query, api_pre_auth_headers],
    ):
        code, _, body = await _s3_request(
            logger,
            context,
            method,
            path,
            query,
            api_pre_auth_headers,
            payload,
            payload_hash,
        )
        return code, await buffered(body)


async def s3_list_keys_relative_to_prefix(logger, context, prefix):
    async def _list(extra_query_items=()):
        query = (
            ("max-keys", "1000"),
            ("list-type", "2"),
            ("prefix", prefix),
        ) + extra_query_items
        code, body_bytes = await s3_request_full(
            logger,
            context,
            b"GET",
            "/",
            query,
            (),
            empty_async_iterator,
            "UNSIGNED-PAYLOAD",
        )
        if code != b"200":
            raise Exception(code, body_bytes)

        namespace = "{http://s3.amazonaws.com/doc/2006-03-01/}"
        root = ET.fromstring(body_bytes)
        next_token = ""
        keys_relative = []
        for element in root:
            if element.tag == f"{namespace}Contents":
                key = first_child_text(element, f"{namespace}Key")
                key_relative = key[len(prefix) :]
                keys_relative.append(key_relative)
            if element.tag == f"{namespace}NextContinuationToken":
                next_token = element.text

        return (next_token, keys_relative)

    async def list_first_page():
        return await _list()

    async def list_later_page(token):
        return await _list((("continuation-token", token),))

    def first_child_text(element, tag):
        for child in element:
            if child.tag == tag:
                return child.text
        return None

    token, keys_page = await list_first_page()
    for key in keys_page:
        yield key

    while token:
        token, keys_page = await list_later_page(token)
        for key in keys_page:
            yield key


async def _s3_request(
    logger, context, method, path, query, api_pre_auth_headers, payload, payload_hash
):
    bucket = context.bucket
    return await aws_request(
        logger,
        context.request,
        "s3",
        bucket.region,
        bucket.host,
        context.credentials,
        method,
        f"/{bucket.name}{path}",
        query,
        api_pre_auth_headers,
        payload,
        payload_hash,
    )


def s3_hash(payload):
    return hashlib.sha256(payload).hexdigest()


@contextlib.contextmanager
def logged(logger, message, logger_args):
    try:
        logger.info(message + "...", *logger_args)
        status = "done"
        logger_func = logger.info
        yield
    except asyncio.CancelledError:
        status = "cancelled"
        logger_func = logger.info
        raise
    except BaseException:
        status = "failed"
        logger_func = logger.exception
        raise
    finally:
        logger_func(message + "... (%s)", *(logger_args + [status]))


def get_ecs_role_credentials(url):
    aws_access_key_id = None
    aws_secret_access_key = None
    token = None
    expiration = datetime(1900, 1, 1)

    async def get(logger, request):
        nonlocal aws_access_key_id
        nonlocal aws_secret_access_key
        nonlocal token
        nonlocal expiration

        now = datetime.now()

        if now > expiration:
            with logged(logger, "Requesting temporary credentials from %s", [url]):
                code, _, body = await request(b"GET", url)
                if code != b"200":
                    raise Exception("Unable to fetch credentials")
                creds = json.loads(await buffered(body))

            aws_access_key_id = creds["AccessKeyId"]
            aws_secret_access_key = creds["SecretAccessKey"]
            token = creds["Token"]
            expiration = datetime.strptime(creds["Expiration"], "%Y-%m-%dT%H:%M:%SZ")

        return AwsCredentials(
            access_key_id=aws_access_key_id,
            secret_access_key=aws_secret_access_key,
            pre_auth_headers=((b"x-amz-security-token", token.encode("ascii")),),
        )

    return get


async def async_main(logger):
    # Suspect that S3 has a very small keep-alive value
    request_non_redirectable, close_pool = Pool(keep_alive_timeout=4, socket_timeout=30)
    request = redirectable(request_non_redirectable)

    credentials = get_ecs_role_credentials(
        "http://169.254.170.2" + os.environ["AWS_CONTAINER_CREDENTIALS_RELATIVE_URI"]
    )
    bucket = S3Bucket(
        region=os.environ["MIRRORS_BUCKET_REGION"],
        host=os.environ["MIRRORS_BUCKET_HOST"],
        name=os.environ["MIRRORS_BUCKET_NAME"],
    )
    s3_context = S3Context(request=request, credentials=credentials, bucket=bucket)

    if os.environ["MIRROR_ANACONDA_R"] == "True":
        await conda_mirror(logger, request, s3_context, "https://conda.anaconda.org/r/", "r/")

    if os.environ["MIRROR_ANACONDA_CONDA_FORGE"] == "True":
        await conda_mirror(
            logger,
            request,
            s3_context,
            "https://conda.anaconda.org/conda-forge/",
            "conda-forge/",
        )

    if os.environ["MIRROR_ANACONDA_CONDA_ANACONDA"] == "True":
        await conda_mirror(
            logger,
            request,
            s3_context,
            "https://conda.anaconda.org/anaconda/",
            "anaconda/",
        )

    if os.environ["MIRROR_CRAN"] == "True":
        await cran_mirror(logger, request, s3_context)

    if os.environ["MIRROR_PYPI"] == "True":
        await pypi_mirror(logger, request, s3_context)

    if os.environ["MIRROR_DEBIAN"] == "True":
        await debian_mirror(
            logger,
            request,
            s3_context,
            "https://cloudfront.debian.net/debian-security/",
            "debian-security/",
        )
        await debian_mirror(
            logger,
            request,
            s3_context,
            "https://cloudfront.debian.net/debian/",
            "debian/",
        )

    if os.environ["MIRROR_NLTK"] == "True":
        await nltk_mirror(logger, request, s3_context, "nltk/")

    await close_pool()
    await asyncio.sleep(0)


async def pypi_mirror(logger, request, s3_context):
    def normalise(name):
        return re.sub(r"[-_.]+", "-", name).lower()

    async def list_packages():
        request_body = (
            b'<?xml version="1.0"?>'
            b"<methodCall><methodName>list_packages</methodName></methodCall>"
        )
        _, _, body = await request(
            b"POST",
            source_base + "/pypi",
            body=streamed(request_body),
            headers=(
                (b"content-type", b"text/xml"),
                (b"content-length", str(len(request_body)).encode()),
            ),
        )
        return [
            package.text
            for package in ET.fromstring(await buffered(body)).findall(
                "./params/param/value/array/data/value/string"
            )
        ]

    async def changelog(sync_changes_after):
        request_body = (
            b'<?xml version="1.0"?>'
            b"<methodCall><methodName>changelog</methodName><params>"
            b"<param><value>"
            b"<int>" + str(sync_changes_after).encode() + b"</int>"
            b"</value></param>"
            b"</params></methodCall>"
        )
        _, _, body = await request(
            b"POST",
            source_base + "/pypi",
            body=streamed(request_body),
            headers=(
                (b"content-type", b"text/xml"),
                (b"content-length", str(len(request_body)).encode()),
            ),
        )
        return [
            package.text
            for package in ET.fromstring((await buffered(body)).replace(b"\x1b", b"")).findall(
                "./params/param/value/array/data/value/array/data/value[1]/string"
            )
        ]

    source_base = "https://pypi.python.org"

    pypi_prefix = "pypi/"

    # We may have overlap, but that's fine
    sync_changes_after_key = "__sync_changes_after"
    # Paranoia: the reference implementation at https://bitbucket.org/loewis/pep381client has -1
    started = int(time()) - 1

    # Determine after when to fetch changes. There is an eventual consistency issue storing this
    # on S3, but at worst we'll be unnecessarily re-fetching updates, rather than missing them.
    # Plus, given the time to run a sync and frequency, this is unlikely anyway
    code, data = await s3_request_full(
        logger,
        s3_context,
        b"GET",
        "/" + pypi_prefix + sync_changes_after_key,
        (),
        (),
        empty_async_iterator,
        s3_hash(b""),
    )
    if code not in [b"200", b"404"]:
        raise Exception("Failed GET of __sync_changes_after {} {}".format(code, data))
    sync_changes_after = int(data) if code == b"200" else 0

    # changelog doesn't seem to have changes older than two years, so for all projects on initial
    # import, we need to call list_packages
    project_names_with_duplicates = (
        (await list_packages())
        if sync_changes_after == 0
        else (await changelog(sync_changes_after))
    )

    project_names = sorted(list(set(project_names_with_duplicates)))

    queue = asyncio.Queue()

    for project_name in project_names:
        normalised_project_name = normalise(project_name)
        await queue.put(
            (
                normalised_project_name,
                source_base + f"/simple/{normalised_project_name}/",
            )
        )

    async def transfer_project(project_name, project_url):
        code, _, body = await request(b"GET", project_url)
        data = await buffered(body)
        if code != b"200":
            raise Exception("Failed GET {}".format(code))

        soup = BeautifulSoup(data, "html.parser")
        links = soup.find_all("a")
        link_data = []

        logger.info("Finding existing files")
        existing_project_filenames = {
            key
            async for key in s3_list_keys_relative_to_prefix(
                logger, s3_context, f"{pypi_prefix}{project_name}/"
            )
        }

        for link in links:
            absolute = link.get("href")
            absolute_no_frag, frag = absolute.split("#")
            filename = str(link.string)
            python_version = link.get("data-requires-python")
            has_python_version = python_version is not None
            python_version_attr = (
                ' data-requires-python="' + html.escape(python_version) + '"'
                if has_python_version
                else ""
            )

            s3_path = f"/{pypi_prefix}{project_name}/{filename}"
            link_data.append((s3_path, filename, frag, python_version_attr))

            exists = filename in existing_project_filenames
            if exists:
                logger.debug("Skipping transfer of %s", s3_path)
                continue

            for _ in range(0, 10):
                try:
                    code, headers, body = await request(b"GET", absolute_no_frag)
                    if code != b"200":
                        await blackhole(body)
                        raise Exception("Failed GET {}".format(code))

                    content_length = dict((key.lower(), value) for key, value in headers)[
                        b"content-length"
                    ]
                    headers = ((b"content-length", content_length),)
                    code, _ = await s3_request_full(
                        logger,
                        s3_context,
                        b"PUT",
                        s3_path,
                        (),
                        headers,
                        lambda: body,
                        "UNSIGNED-PAYLOAD",
                    )
                except (HttpConnectionError, HttpDataError):
                    await asyncio.sleep(10)
                else:
                    break
            if code != b"200":
                raise Exception("Failed PUT {}".format(code))

        html_str = (
            "<!DOCTYPE html>"
            + "<html>"
            + "<body>"
            + "".join(
                [
                    f'<a href="https://{s3_context.bucket.host}/{s3_context.bucket.name}{s3_path}'
                    f'#{frag}"{python_version_attr}>{filename}</a>'
                    for s3_path, filename, frag, python_version_attr in link_data
                ]
            )
            + "</body>"
            + "</html>"
        )
        html_bytes = html_str.encode("ascii")
        s3_path = f"/{pypi_prefix}{project_name}/"
        headers = (
            (b"content-type", b"text/html"),
            (b"content-length", str(len(html_bytes)).encode("ascii")),
        )
        for _ in range(0, 5):
            try:
                code, _ = await s3_request_full(
                    logger,
                    s3_context,
                    b"PUT",
                    s3_path,
                    (),
                    headers,
                    streamed(html_bytes),
                    s3_hash(html_bytes),
                )
            except (HttpConnectionError, HttpDataError):
                await asyncio.sleep(10)
            else:
                break
        if code != b"200":
            raise Exception("Failed PUT {}".format(code))

    async def transfer_task():
        while True:
            project_name, project_url = await queue.get()
            logger.info("Transferring project %s %s", project_name, project_url)

            try:
                await transfer_project(project_name, project_url)
            except Exception:  # pylint: disable=broad-except
                logger.exception("Exception crawling %s", project_url)
            finally:
                queue.task_done()

    tasks = [asyncio.ensure_future(transfer_task()) for _ in range(0, 10)]
    try:
        await queue.join()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.sleep(0)

    started_bytes = str(started).encode("ascii")

    headers = ((b"content-length", str(len(started_bytes)).encode("ascii")),)
    for _ in range(0, 10):
        try:
            code, _ = await s3_request_full(
                logger,
                s3_context,
                b"PUT",
                "/" + pypi_prefix + sync_changes_after_key,
                (),
                headers,
                streamed(started_bytes),
                s3_hash(started_bytes),
            )
        except (HttpConnectionError, HttpDataError):
            pass
        else:
            break
    if code != b"200":
        raise Exception()


async def cran_mirror(logger, request, s3_context):
    source_base = "https://cran.ma.imperial.ac.uk/"
    source_base_url = source_base + "web/packages/available_packages_by_name.html"
    source_base_parsed = urllib.parse.urlparse(source_base_url)
    cran_prefix = "cran/"

    done = set()
    queue = asyncio.Queue()
    await queue.put(source_base_url)

    # Main package file. Maybe better parsing this than crawling HTML?
    package_index = "src/contrib/PACKAGES"
    code, _, body = await request(b"GET", source_base + package_index)
    package_index_body = await buffered(body)
    if code != b"200":
        raise Exception()

    logger.info("Finding existing files")
    existing_files = {
        key async for key in s3_list_keys_relative_to_prefix(logger, s3_context, cran_prefix)
    }

    async def crawl(url):
        key_suffix = urllib.parse.urlparse(url).path[1:]  # Without leading /

        if key_suffix in existing_files and (
            key_suffix.endswith(".tar.gz")
            or key_suffix.endswith(".tgz")
            or key_suffix.endswith(".zip")
            or key_suffix.endswith(".pdf")
        ):
            # The package files have a version in the file name. Other files like html and pdf
            # don't, but don't think they are actually used in when installing packages from R
            return

        code, headers, body = await request(b"GET", url)
        if code != b"200":
            await blackhole(body)
            raise Exception()
        headers_lower = dict((key.lower(), value) for key, value in headers)
        content_type = headers_lower.get(b"content-type", None)
        content_length = headers_lower[b"content-length"]
        target_key = cran_prefix + key_suffix

        if content_type == b"text/html":
            data = await buffered(body)
            soup = BeautifulSoup(data, "html.parser")
            links = soup.find_all("a")
            for link in links:
                absolute = urllib.parse.urljoin(url, link.get("href"))
                absolute_no_frag = absolute.split("#")[0]
                is_done = (
                    urllib.parse.urlparse(absolute_no_frag).netloc == source_base_parsed.netloc
                    and absolute_no_frag not in done
                )
                if is_done:
                    done.add(absolute_no_frag)
                    await queue.put(absolute_no_frag)
            return

        if key_suffix in existing_files:
            await blackhole(body)
            return

        headers = ((b"content-length", content_length),)
        code, _ = await s3_request_full(
            logger,
            s3_context,
            b"PUT",
            "/" + target_key,
            (),
            headers,
            lambda: body,
            "UNSIGNED-PAYLOAD",
        )
        if code != b"200":
            raise Exception()

    async def transfer_task():
        while True:
            url = await queue.get()
            try:
                for _ in range(0, 10):
                    try:
                        await crawl(url)
                    except (HttpConnectionError, HttpDataError):
                        await asyncio.sleep(10)
                    else:
                        break
            except Exception:  # pylint: disable=broad-except
                logger.exception("Exception crawling %s", url)
            finally:
                queue.task_done()

    tasks = [asyncio.ensure_future(transfer_task()) for _ in range(0, 10)]
    try:
        await queue.join()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.sleep(0)

    headers = ((b"content-length", str(len(package_index_body)).encode("ascii")),)
    code, _ = await s3_request_full(
        logger,
        s3_context,
        b"PUT",
        "/" + cran_prefix + package_index,
        (),
        headers,
        streamed(package_index_body),
        s3_hash(package_index_body),
    )

    if code != b"200":
        raise Exception()


async def conda_mirror(logger, request, s3_context, source_base_url, s3_prefix):
    arch_dirs = ["noarch/", "linux-64/"]
    repodatas = []
    queue = asyncio.Queue()

    logger.info("Finding existing files")
    existing_files = {
        key async for key in s3_list_keys_relative_to_prefix(logger, s3_context, s3_prefix)
    }

    for arch_dir in arch_dirs:
        code, _, body = await request(b"GET", source_base_url + arch_dir + "repodata.json")
        if code != b"200":
            raise Exception()

        source_repodata_raw = await buffered(body)
        source_repodata = json.loads(source_repodata_raw)

        for package_suffix, _ in source_repodata["packages"].items():
            await queue.put(arch_dir + package_suffix)

        repodatas.append((arch_dir + "repodata.json", source_repodata_raw))

        code, _, body = await request(b"GET", source_base_url + arch_dir + "repodata.json.bz2")
        if code != b"200":
            raise Exception()
        repodatas.append((arch_dir + "repodata.json.bz2", await buffered(body)))

    async def transfer_package(package_suffix):
        source_package_url = source_base_url + package_suffix
        target_package_key = s3_prefix + package_suffix

        exists = package_suffix in existing_files
        if exists:
            logger.debug("Skipping transfer of {}".format("/" + target_package_key))
            return

        code, headers, body = await request(b"GET", source_package_url)
        if code != b"200":
            response = await buffered(body)
            raise Exception("Exception GET {} {} {}".format(source_package_url, code, response))
        headers_lower = dict((key.lower(), value) for key, value in headers)
        headers = ((b"content-length", headers_lower[b"content-length"]),)
        code, body = await s3_request_full(
            logger,
            s3_context,
            b"PUT",
            "/" + target_package_key,
            (),
            headers,
            lambda: body,
            "UNSIGNED-PAYLOAD",
        )
        if code != b"200":
            raise Exception(  # pylint: disable=broad-except
                "Exception PUT {} {} {}".format("/" + target_package_key, code, body)
            )

    async def transfer_task():
        while True:
            package_suffix = await queue.get()

            try:
                for _ in range(0, 10):
                    try:
                        await transfer_package(package_suffix)
                    except (HttpConnectionError, HttpDataError):
                        await asyncio.sleep(10)
                    else:
                        break
            except Exception:  # pylint: disable=broad-except
                logger.exception("Exception transferring %s", package_suffix)
            finally:
                queue.task_done()

    tasks = [asyncio.ensure_future(transfer_task()) for _ in range(0, 10)]
    try:
        await queue.join()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.sleep(0)

    for path, data in repodatas:
        target_repodata_key = s3_prefix + path
        headers = ((b"content-length", str(len(data)).encode("ascii")),)
        code, _ = await s3_request_full(
            logger,
            s3_context,
            b"PUT",
            "/" + target_repodata_key,
            (),
            headers,
            streamed(data),
            s3_hash(data),
        )
        if code != b"200":
            raise Exception()


async def debian_mirror(logger, request, s3_context, source_base_url, s3_prefix):
    source_base_parsed = urllib.parse.urlparse(source_base_url)
    source_base_path = source_base_parsed.path

    done = set()
    queue = asyncio.Queue()
    await queue.put(source_base_url)

    logger.info("Finding existing files")
    existing_relative_keys = {
        key async for key in s3_list_keys_relative_to_prefix(logger, s3_context, s3_prefix)
    }

    def get_relative_key(url):
        return urllib.parse.urlparse(url).path[len(source_base_path) :]

    async def crawl(url):
        code, headers, body = await request(b"GET", url)
        if code != b"200":
            await blackhole(body)
            raise Exception(f"{code} {url}")

        headers_lower = dict((key.lower(), value) for key, value in headers)
        content_type = headers_lower.get(b"content-type", b"")
        target_key = s3_prefix + get_relative_key(url)

        if content_type.startswith(b"text/html"):
            data = await buffered(body)
            soup = BeautifulSoup(data, "html.parser")
            links = soup.find_all("a")
            for link in links:
                # The web pages contain URL-encoded URLs, but lowhaio expects non-encoded
                absolute_str = urllib.parse.urljoin(url, link.get("href"))
                absolute = urllib.parse.urlparse(absolute_str)
                absolute = absolute._replace(path=urllib.parse.unquote(absolute.path))
                absolute_str = absolute.geturl()
                next_relative_key = get_relative_key(absolute_str)
                to_do = (
                    absolute.netloc == source_base_parsed.netloc
                    and absolute.path[: len(source_base_path)] == source_base_path
                    and absolute_str not in done
                    and (
                        next_relative_key not in existing_relative_keys
                        or (
                            # Immutable
                            not next_relative_key.endswith(".deb")
                            and not next_relative_key.endswith(".change")
                        )
                    )
                )
                if to_do:
                    logger.info("On %s adding %s", url, absolute_str)
                    done.add(absolute_str)
                    await queue.put(absolute_str)
            return

        content_length = headers_lower[b"content-length"]
        headers = ((b"content-length", content_length),)
        code, _ = await s3_request_full(
            logger,
            s3_context,
            b"PUT",
            "/" + target_key,
            (),
            headers,
            lambda: body,
            "UNSIGNED-PAYLOAD",
        )
        if code != b"200":
            raise Exception()

    async def transfer_task():
        while True:
            url = await queue.get()
            try:
                for _ in range(0, 10):
                    try:
                        await crawl(url)
                    except (HttpConnectionError, HttpDataError):
                        await asyncio.sleep(10)
                    else:
                        break
            except Exception:  # pylint: disable=broad-except
                logger.exception("Exception crawling %s", url)
            finally:
                queue.task_done()

    tasks = [asyncio.ensure_future(transfer_task()) for _ in range(0, 10)]
    try:
        await queue.join()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.sleep(0)


async def nltk_mirror(logger, request, s3_context, s3_prefix):
    base = "https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/"
    input_index_url = f"{base}/index.xml"

    # Fetch index file
    code, headers, body = await request(b"GET", input_index_url)
    if code != b"200":
        raise Exception("Unable to fetch index")
    headers_xml_lower = dict((key.lower(), value) for key, value in headers)
    index_xml_content_type = headers_xml_lower[b"content-type"]
    index_xml = ET.fromstring(await buffered(body))

    # Transfer package contents to S£ if they haven't already
    for package in index_xml.findall("./packages/package"):
        package_original_url = package.attrib["url"]
        package_checksum = package.attrib["checksum"]
        package_id = package.attrib["id"]

        # The NTLK downloader is sensitive to the extension of the file
        _, ext = os.path.splitext(package_original_url)
        new_path = f"/{s3_prefix}{package_id}-{package_checksum}{ext}"

        package.attrib[
            "url"
        ] = f"https://{s3_context.bucket.host}/{s3_context.bucket.name}{new_path}"

        # If the file already exists, don't re-upload. Named including the
        # checksum deliberately so we can do this
        code, _ = await s3_request_full(
            logger,
            s3_context,
            b"HEAD",
            new_path,
            (),
            headers,
            empty_async_iterator,
            "UNSIGNED-PAYLOAD",
        )
        logger.info("%s %s", f"{s3_context.bucket.name}{new_path}", code)
        if code == b"200":
            continue

        # Stream the file to S3
        code, headers, body = await request(b"GET", package_original_url)
        if code != b"200":
            await blackhole(body)
            raise Exception(f"{code} {package_original_url}")

        headers_lower = dict((key.lower(), value) for key, value in headers)
        headers = (
            (b"content-length", headers_lower[b"content-length"]),
            (b"content-type", headers_lower[b"content-type"]),
        )
        code, _ = await s3_request_full(
            logger,
            s3_context,
            b"PUT",
            new_path,
            (),
            headers,
            lambda: body,
            "UNSIGNED-PAYLOAD",
        )
        if code != b"200":
            raise Exception()

    # The ascii encoding is important: the nltk downloader seems to assume
    # attributes are ascii
    output_xml_str = ET.tostring(index_xml, encoding="ascii", method="xml")
    index_xml_content_length = str(len(output_xml_str)).encode("ascii")
    headers = (
        (b"content-length", index_xml_content_length),
        (b"content-type", index_xml_content_type),
    )
    code, _ = await s3_request_full(
        logger,
        s3_context,
        b"PUT",
        f"/{s3_prefix}index.xml",
        (),
        headers,
        streamed(output_xml_str),
        "UNSIGNED-PAYLOAD",
    )
    if code != b"200":
        raise Exception()


def main():
    loop = asyncio.get_event_loop()

    logger = logging.getLogger("app")
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    logger.addHandler(handler)

    main_task = loop.create_task(async_main(logger))
    loop.add_signal_handler(signal.SIGINT, main_task.cancel)
    loop.add_signal_handler(signal.SIGTERM, main_task.cancel)

    loop.run_until_complete(main_task)

    logger.info("Exiting.")


if __name__ == "__main__":
    main()
