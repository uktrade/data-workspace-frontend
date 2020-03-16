import requests

from django.conf import settings


def gitlab_api_v4(method, path, params=()):
    return requests.request(
        method,
        f'{settings.GITLAB_URL}api/v4/{path}',
        params=params,
        headers={'PRIVATE-TOKEN': settings.GITLAB_TOKEN},
    ).json()
