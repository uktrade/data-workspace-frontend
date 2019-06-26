import logging

from django.conf import settings

from zenpy import Zenpy
from zenpy.lib.api_objects import Ticket, User

logger = logging.getLogger('app')


def create_zendesk_ticket(contact_email,
                          user,
                          team_name,
                          justification_text,
                          approval_url,
                          dataset_name,
                          dataset_url,
                          information_asset_owner,  # mb these can be null
                          information_asset_manager,
                          ):
    client = Zenpy(
        subdomain=settings.ZENDESK_SUBDOMAIN,
        email=settings.ZENDESK_EMAIL,
        token=settings.ZENDESK_TOKEN,
    )

    username = f'{user.first_name} {user.last_name}'
    asset_owner_text = "None"
    asset_manager_text = "None"

    if information_asset_owner:
        asset_owner_text = f'{information_asset_owner.first_name} {information_asset_owner.last_name} <{information_asset_owner.email}>'

    if information_asset_manager:
        asset_owner_text = f'{information_asset_manager.first_name} {information_asset_manager.last_name} <{information_asset_manager.email}>'

    formatted_text = f"""
Access request for 
{dataset_name} {dataset_url}

Information Asset Owner: {asset_owner_text}
Information Asset Manager: {asset_manager_text}

Username:   {username}
Contact:    {contact_email}
SSO Login:  {user.email}
Team:       {team_name}


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
                email=contact_email,
                name=username)
        )
    )

    return ticket_audit.ticket.id
