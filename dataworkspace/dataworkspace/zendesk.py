import logging
import urllib.parse

from django.conf import settings
from django.urls import reverse
from zenpy import Zenpy
from zenpy.lib.api_objects import Comment, CustomField, Ticket, User

from dataworkspace.notify import generate_token, send_email

logger = logging.getLogger("app")

zendesk_service_field_id = settings.ZENDESK_SERVICE_FIELD_ID
zendesk_service_field_value = settings.ZENDESK_SERVICE_FIELD_VALUE


def get_username(user):
    return f"{user.first_name} {user.last_name}"


def get_people_url(name):
    return "https://people.trade.gov.uk/people-and-teams/search/?query={}&filters=teams&filters=people".format(
        urllib.parse.quote(name)
    )


def build_ticket_description_text(
    access_request, access_request_url, catalogue_item=None, stata_description="N/A"
):
    username = get_username(access_request.requester)
    people_url = get_people_url(username)
    ticket_description = f"""Access request for

Username:   {username}
Journey:    {access_request.human_readable_journey}
Dataset:    {catalogue_item}
SSO Login:  {access_request.requester.email}
People search: {people_url}
Stata Request Description: {stata_description}


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


def create_zendesk_ticket(request, access_request, catalogue_item=None, stata_description="N/A"):
    client = Zenpy(
        subdomain=settings.ZENDESK_SUBDOMAIN,
        email=settings.ZENDESK_EMAIL,
        token=settings.ZENDESK_TOKEN,
    )

    access_request_url = request.build_absolute_uri(
        reverse("admin:request_access_accessrequest_change", args=(access_request.id,))
    )

    authorize_url = request.build_absolute_uri(
        reverse("admin:auth_user_change", args=[access_request.requester.id])
    )

    ticket_description = build_ticket_description_text(
        access_request, access_request_url, catalogue_item, stata_description
    )

    private_comment = (
        build_private_comment_text(catalogue_item, authorize_url) if catalogue_item else None
    )

    username = get_username(access_request.requester)

    subject = f"Access Request for {catalogue_item if catalogue_item else username}"

    ticket_audit = client.tickets.create(
        Ticket(
            subject=subject,
            description=ticket_description,
            requester=User(email=access_request.requester.email, name=username),
            custom_fields=[
                CustomField(id=zendesk_service_field_id, value=zendesk_service_field_value)
            ],
        )
    )

    ticket_audit.ticket.comment = Comment(body=private_comment, public=False)
    client.tickets.update(ticket_audit.ticket)

    return ticket_audit.ticket.id


def update_zendesk_ticket(ticket_id, comment=None, status=None):
    client = Zenpy(
        subdomain=settings.ZENDESK_SUBDOMAIN,
        email=settings.ZENDESK_EMAIL,
        token=settings.ZENDESK_TOKEN,
    )

    ticket = client.tickets(id=ticket_id)

    if comment:
        ticket.comment = Comment(body=comment, public=False)

    if status:
        ticket.status = status

    client.tickets.update(ticket)

    return ticket


def notify_dataset_access_request(request, access_request, dataset):
    dataset_url = request.build_absolute_uri(dataset.get_absolute_url())
    request_approvers_emails = dataset.request_approvers or [
        dataset.information_asset_manager.email
    ]
    message = f"""
An access request has been sent to the relevent person or team to assess you request.

There is no need to action this ticket until a further notification is received.

Data Set: {dataset.name} ({dataset_url})

Requestor {request.user.email}
People finder link: {get_people_url(request.user.get_full_name())}

Requestor’s response to why access is needed:
{access_request.reason_for_access}

Information Asset Manager: {dataset.information_asset_manager.email if dataset.information_asset_manager else 'Not set'}

Request Approver: {", ".join(request_approvers_emails)}

If access has not been granted to the requestor within 5 working days, this will trigger an update to this Zendesk ticket to resolve the request.
"""

    ticket_reference = create_support_request(
        request.user,
        request.user.email,
        message,
        subject=f"Data set access request received - {dataset.name}",
        tag="dataset-access-request",
    )

    authorize_url = request.build_absolute_uri(
        reverse(
            "datasets:review_access",
            kwargs={"pk": dataset.id, "user_id": request.user.id},
        )
    )

    contacts = set()
    contacts.add(dataset.information_asset_manager.email)
    if request_approvers_emails:
        contacts.update(request_approvers_emails)

    people_url = get_people_url(request.user.get_full_name())

    for contact in contacts:
        send_email(
            (settings.NOTIFY_DATASET_ACCESS_REQUEST_TEMPLATE_ID),
            contact,
            personalisation={
                "dataset_name": dataset.name,
                "dataset_url": dataset_url,
                "user_email": access_request.contact_email,
                "goal": access_request.reason_for_access,
                "people_url": people_url,
                "give_access_url": f"{authorize_url}",
            },
        )

    return ticket_reference


def notify_unpublish_catalogue_page(request, dataset):
    message = """
A catalogue page has been unpublished and needs action from the support team.

Contact the user and find out why they have unpublished this page.

"""

    create_support_request(
        request.user,
        request.user.email,
        message,
        subject=f"{dataset.name} has been unpublished by {request.user}",
        tag="dataset-unpublish-request",
    )


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
    client = Zenpy(
        subdomain=settings.ZENDESK_SUBDOMAIN,
        email=settings.ZENDESK_EMAIL,
        token=settings.ZENDESK_TOKEN,
    )
    ticket_audit = client.tickets.create(
        Ticket(
            subject=subject or "Data Workspace Support Request",
            description=message,
            requester=User(email=email, name=user.get_full_name()),
            tags=[tag] if tag else None,
            custom_fields=[
                CustomField(id=zendesk_service_field_id, value=zendesk_service_field_value)
            ],
        )
    )
    return ticket_audit.ticket.id
