import os
from asyncio import CancelledError

import sentry_sdk
from aiohttp import ServerDisconnectedError


def before_send(event, hint):
    if 'exc_info' not in hint:
        return event

    exception = hint['exc_info'][1]

    # Group together all asyncio/aiohttp cancellederrors
    if isinstance(exception, CancelledError):
        event['fingerprint'] = ['cancelled-error', '{{ module }}']
    elif isinstance(exception, ConnectionResetError):
        event['fingerprint'] = ['connection-reset-error', '{{ module }}']
    elif isinstance(exception, ServerDisconnectedError):
        event['fingerprint'] = ['server-disconnected-error', '{{ module }}']

    return event


def init_sentry(integration):
    if os.environ.get('SENTRY_DSN') is not None:
        sentry_sdk.init(
            os.environ['SENTRY_DSN'],
            integrations=[integration],
            before_send=before_send,
        )
