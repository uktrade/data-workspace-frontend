import logging
import urllib.parse

from django.conf import settings
from django.urls import reverse

from helpdesk_client import get_helpdesk_interface
from helpdesk_client.interfaces import (
    HelpDeskComment,
    HelpDeskCustomField,
    HelpDeskTicket,
    HelpDeskUser,
)

from dataworkspace.notify import generate_token, send_email

logger = logging.getLogger("app")

zendesk_service_field_id = settings.ZENDESK_SERVICE_FIELD_ID
zendesk_service_field_value = settings.ZENDESK_SERVICE_FIELD_VALUE


def get_username(user):
    return f"{user.first_name} {user.last_name}"


def get_people_url(name):
    return "https://people.trade.gov.uk/search?search_filters[]=people&query={}".format(
        urllib.parse.quote(name)
    )


def build_ticket_description_text(access_request, access_request_url, catalogue_item=None):
    username = get_username(access_request.requester)
    people_url = get_people_url(username)
    ticket_description = f"""Access request for

Username:   {username}
Journey:    {access_request.human_readable_journey}
Dataset:    {catalogue_item}
SSO Login:  {access_request.requester.email}
People search: {people_url}


Details for the request can be found at

{access_request_url}

"""

    logger.debug(ticket_description)
    return ticket_description


def build_private_comment_text(catalogue_item, approval_url):
    asset_owner_text = "None"
    asset_manager_text = "None"

    iao = catalogue_item.information_asset_owner
    iam = catalogue_item.information_asset_manager
    if iao:
        asset_owner_text = f"{iao.first_name} {iao.last_name} " f"<{iao.email}>"

    if iam:
        asset_owner_text = f"{iam.first_name} {iam.last_name} " f"<{iam.email}>"

    private_comment = f"""

Information Asset Owner: {asset_owner_text}
Information Asset Manager: {asset_manager_text}

You can approve this request here
{approval_url}
    """

    logger.debug(private_comment)

    return private_comment


# configure and instantiate the client
helpdesk_interface = get_helpdesk_interface("helpdesk_client.interfaces.HelpDeskStubbed")
helpdesk = helpdesk_interface(credentials=settings.HELP_DESK_CREDS)


def create_zendesk_ticket(request, access_request, catalogue_item=None):
    access_request_url = request.build_absolute_uri(
        reverse("admin:request_access_accessrequest_change", args=(access_request.id,))
    )

    authorize_url = request.build_absolute_uri(
        reverse("admin:auth_user_change", args=[access_request.requester.id])
    )

    ticket_description = build_ticket_description_text(
        access_request, access_request_url, catalogue_item
    )

    private_comment = (
        build_private_comment_text(catalogue_item, authorize_url) if catalogue_item else None
    )

    username = get_username(access_request.requester)

    subject = f"Access Request for {catalogue_item if catalogue_item else username}"

    helpdesk_ticket = HelpDeskTicket(
        subject=subject,
        description=ticket_description,
        user=HelpDeskUser(full_name=username, email=access_request.requester.email),
        custom_fields=[
            HelpDeskCustomField(id=zendesk_service_field_id, value=zendesk_service_field_value)
        ],
        comment=HelpDeskComment(body=private_comment, public=False),
    )

    ticket_audit = helpdesk.create_ticket(helpdesk_ticket)

    return ticket_audit.id


def update_helpdesk_ticket(ticket_id, comment=None, status=None):
    if comment:
        helpdesk.helpdesk.add_comment(
            ticket_id=ticket_id, comment=HelpDeskComment(body=comment, public=False)
        )

    if status:
        ticket = helpdesk.get_ticket(ticket_id=ticket_id)
        ticket.status = status
        ticket = helpdesk.update_ticket(ticket=ticket)

    return ticket


def notify_visualisation_access_request(request, access_request, dataset):
    dataset_url = request.build_absolute_uri(dataset.get_absolute_url())
    message = f"""
An access request has been sent to the data visualisation owner and secondary contact to process.

There is no need to action this ticket until a further notification is received.

Data visualisation: {dataset.name} ({dataset_url})

Requestor {request.user.email}
People finder link: {get_people_url(request.user.get_full_name())}

Requestor’s response to why access is needed:
{access_request.reason_for_access}

Data visualisation owner: {dataset.enquiries_contact.email if dataset.enquiries_contact else 'Not set'}

Secondary contact: {dataset.secondary_enquiries_contact.email if dataset.secondary_enquiries_contact else 'Not set'}

If access has not been granted to the requestor within 5 working days, this will trigger an update to this Zendesk ticket to resolve the request.
    """

    ticket_reference = create_support_request(
        request.user,
        request.user.email,
        message,
        subject=f"Data visualisation access request received - {dataset.name}",
        tag="visualisation-access-request",
    )

    give_access_url = request.build_absolute_uri(
        reverse(
            "visualisations:users-give-access",
            args=[dataset.visualisation_template.gitlab_project_id],
        )
    )
    give_access_token = generate_token(
        {"email": request.user.email, "ticket": ticket_reference}
    ).decode("utf-8")

    contacts = set()
    if dataset.enquiries_contact:
        contacts.add(dataset.enquiries_contact.email)
    if dataset.secondary_enquiries_contact:
        contacts.add(dataset.secondary_enquiries_contact.email)

    for contact in contacts:
        send_email(
            settings.NOTIFY_VISUALISATION_ACCESS_REQUEST_TEMPLATE_ID,
            contact,
            personalisation={
                "visualisation_name": dataset.name,
                "visualisation_url": dataset_url,
                "user_email": access_request.contact_email,
                "goal": access_request.reason_for_access,
                "people_url": get_people_url(request.user.get_full_name()),
                "give_access_url": f"{give_access_url}?token={give_access_token}",
            },
        )

    return ticket_reference


def create_support_request(user, email, message, tag=None, subject=None):
    ticket_audit = helpdesk.create_ticket(
        HelpDeskTicket(
            subject=subject or "Data Workspace Support Request",
            description=message,
            user=HelpDeskUser(
                full_name=user.get_full_name(),
                email=email,
            ),
            custom_fields=[
                HelpDeskCustomField(id=zendesk_service_field_id, value=zendesk_service_field_value)
            ],
            tags=[tag] if tag else None,
        )
    )

    return ticket_audit.id
