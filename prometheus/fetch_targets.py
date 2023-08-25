import asyncio
import base64
import json
import logging
import os
import sys
import urllib.parse

import httpx


async def async_main(logger, target_file, url, username, password):
    while True:
        await asyncio.sleep(10)
        try:
            logger.debug("Fetching from %s", url)
            headers = {
                b"Authorization": b"Basic "
                + base64.b64encode(f"{username}:{password}".encode("ascii"))
            }
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers)
            response.raise_for_status()
            logger.debug("Code %s", response.status_code)
            raw_json = response.json()
            logger.debug("Received %s", raw_json)
            applications = json.loads(raw_json)["applications"]
            logger.debug("Found %s", applications)
            file_sd_config = [
                {
                    "labels": {
                        "job": "tools",
                        "tool_name": application["name"],
                        "user": application["user"],
                    },
                    "targets": [
                        urllib.parse.urlsplit(application["proxy_url"]).hostname + ":8889"
                    ],
                }
                for application in applications
                if application["proxy_url"] is not None
            ]
            logger.debug("Saving %s to %s", file_sd_config, target_file)
            with open(target_file, "w") as file:
                file.write(json.dumps(file_sd_config))
        except Exception:  # pylint: disable=broad-except
            logger.exception("Exception fetching targets")


def main():
    target_file = os.environ["TARGET_FILE"]
    url = os.environ["URL"]
    username = os.environ["METRICS_SERVICE_DISCOVERY_BASIC_AUTH_USER"]
    password = os.environ["METRICS_SERVICE_DISCOVERY_BASIC_AUTH_PASSWORD"]

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(async_main(logger, target_file, url, username, password))


if __name__ == "__main__":
    main()
