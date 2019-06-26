import logging

from django.conf import settings

from zenpy import Zenpy
from zenpy.lib.api_objects import Ticket, User

logger = logging.getLogger('app')


def create_zendesk_ticket(email, username, justification_text, approval_url, dataset_name, dataset_url):
    client = Zenpy(
        subdomain=settings.ZENDESK_SUBDOMAIN,
        email=settings.ZENDESK_EMAIL,
        token=settings.ZENDESK_TOKEN,
    )

    formatted_text = f"""
{username} <{email}> has requested access to {dataset_name} {dataset_url}

Justification Text
------------------
{justification_text}

You can approve this request here
{approval_url}
"""

    ticket_audit = client.tickets.create(
        Ticket(
            subject=f'Data Catalogue Access Request for {dataset_name}',
            description=formatted_text,
            tags=['datacatalogue'],
            requester=User(
                email=email,
                name=username)
        )
    )

    return ticket_audit.ticket.id
