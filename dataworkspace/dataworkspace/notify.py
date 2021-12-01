import json

from cryptography.fernet import Fernet
from django.conf import settings
from notifications_python_client.notifications import NotificationsAPIClient


def generate_token(data):
    fernet = Fernet(settings.FERNET_EMAIL_TOKEN_KEY)

    return fernet.encrypt(json.dumps(data).encode("utf-8"))


def decrypt_token(token):
    fernet = Fernet(settings.FERNET_EMAIL_TOKEN_KEY)

    return json.loads(fernet.decrypt(token).decode("utf-8"))


class EmailSendFailureException(Exception):
    pass


def send_email(template_id, email_address, personalisation=None, reference=None):
    client = NotificationsAPIClient(settings.NOTIFY_API_KEY)

    response = client.send_email_notification(
        template_id=template_id,
        email_address=email_address,
        personalisation=personalisation,
        reference=reference,
    )
    # pylint: disable=unsupported-membership-test
    if "id" in response:
        # pylint: disable=unsubscriptable-object
        return response["id"]
    else:
        raise EmailSendFailureException(response)
