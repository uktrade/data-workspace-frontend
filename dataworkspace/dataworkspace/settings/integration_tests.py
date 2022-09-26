# pylint: disable-all

from .base import *  # noqa

from helpdesk_client.interfaces import (
    HelpDeskBase,
    HelpDeskComment,
    HelpDeskUser,
    HelpDeskTicket,
)

import requests

DEBUG = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "ecs": {"format": "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"},
        "verbose": {"format": "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"},
    },
    "handlers": {"dev": {"class": "logging.StreamHandler", "formatter": "verbose"}},
    "loggers": {
        "app": {"handlers": ["dev"], "level": "DEBUG", "propagate": True},
        "test": {"handlers": ["dev"], "level": "DEBUG", "propagate": True},
        "dataworkspace": {"handlers": ["dev"], "level": "DEBUG", "propagate": True},
        "celery": {"handlers": ["dev"], "level": "INFO", "propagate": False},
    },
}


class HelpDeskTest(HelpDeskBase):
    def __init__(self, *args, **kwargs) -> None:
        self._ticket_id = 1234567890987654321

    def get_or_create_user(self, user: HelpDeskUser) -> HelpDeskUser:
        raise NotImplementedError

    def create_ticket(self, ticket: HelpDeskTicket) -> HelpDeskTicket:
        # Call help desk test server with ticket details
        ticket.id = self._ticket_id

        requests.post(
            "http://dataworkspace.test:8006/api/v2/tickets.json",
            json={
                "ticket": {
                    "id": ticket.id,
                    "subject": ticket.subject,
                    "description": ticket.description,
                    "status": "new",
                    "requester_id": 1,
                    "submitter_id": 1,
                },
            },
        )

        return ticket

    def get_ticket(self, ticket_id: int) -> HelpDeskTicket:
        raise NotImplementedError

    def close_ticket(self, ticket_id: int) -> HelpDeskTicket:
        raise NotImplementedError

    def add_comment(self, ticket_id: int, comment: HelpDeskComment) -> HelpDeskTicket:
        raise NotImplementedError

    def update_ticket(self, ticket: HelpDeskTicket) -> HelpDeskTicket:
        raise NotImplementedError


HELP_DESK_INTERFACE = "dataworkspace.settings.integration_tests.HelpDeskTest"
