import os
from asyncio import CancelledError

import sentry_sdk
from aiohttp import ServerDisconnectedError


def before_send(event, hint):
    if "exc_info" not in hint:
        return event

    exception = hint["exc_info"][1]

    # Group together all asyncio/aiohttp cancellederrors
    if isinstance(exception, CancelledError):
        event["fingerprint"] = ["cancelled-error", "{{ module }}"]
    elif isinstance(exception, ConnectionResetError):
        event["fingerprint"] = ["connection-reset-error", "{{ module }}"]
    elif isinstance(exception, ServerDisconnectedError):
        event["fingerprint"] = ["server-disconnected-error", "{{ module }}"]

    # Remove references to database_data from stack traces
    if event.get("exception"):
        for value in event["exception"].get("values", []):
            for frame in value["stacktrace"]["frames"]:
                if "database_data" in frame["vars"]:
                    frame["vars"]["database_data"] = "[Database credentials scrubbed]"
                for idx, pre_context in enumerate(frame["pre_context"]):
                    if "password" in pre_context.lower():
                        frame["pre_context"][idx] = "[Password scrubbed]"
                for idx, post_context in enumerate(frame["post_context"]):
                    if "password" in post_context.lower():
                        frame["post_context"][idx] = "[Password scrubbed]"

    return event


def init_sentry(integrations):
    if os.environ.get("SENTRY_DSN") is not None:
        sentry_sdk.init(
            os.environ["SENTRY_DSN"],
            integrations=integrations,
            before_send=before_send,
        )
