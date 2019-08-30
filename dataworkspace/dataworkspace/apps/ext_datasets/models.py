from django.db import models

from dataworkspace.apps.core.models import TimeStampedModel


class OMISDataset(TimeStampedModel):
    DRAFT = 'draft'
    QUOTE_AWAITING_ACCEPTANCE = 'quote_awaiting_acceptance'
    QUOTE_ACCEPTED = 'quote_accepted'
    PAID = 'paid'
    COMPLETE = 'complete'
    CANCELLED = 'cancelled'

    OrderStatus = (
        (DRAFT, 'Draft'),
        (QUOTE_AWAITING_ACCEPTANCE, 'Quote awaiting acceptance'),
        (QUOTE_ACCEPTED, 'Quote accepted'),
        (PAID, 'Paid'),
        (COMPLETE, 'Complete'),
        (CANCELLED, 'Cancelled'),
    )

    omis_order_reference = models.CharField(primary_key=True, max_length=100)
    company_name = models.CharField(max_length=255)
    order_status = models.CharField(
        max_length=100,
        choices=OrderStatus,
        default=DRAFT
    )
    contact_first_name = models.CharField(max_length=255)
    contact_last_name = models.CharField(max_length=255)
    contact_email_address = models.EmailField()
    contact_phone_number = models.CharField(max_length=255, null=True, blank=True)
    subtotal = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Net cost - any discount in pence from invoice.',
    )
    net_price = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Net cost - discount value in pence from order.',
    )
    sector_name = models.CharField(max_length=255, null=True, blank=True)
    market = models.TextField(null=True, blank=True)

    DIT_team = models.TextField(null=True, blank=True)
    UK_region = models.TextField(null=True, blank=True)

    created_date = models.DateTimeField(db_index=True, null=True, blank=True)
    cancelled_date = models.DateTimeField(null=True, blank=True)
    cancellation_reason_text = models.TextField(null=True, blank=True)
    completion_date = models.DateTimeField(null=True, blank=True)
    delivery_date = models.DateField(null=True, blank=True)
    payment_received_date = models.DateTimeField(null=True, blank=True)

    company_trading_address_line_1 = models.CharField(max_length=255, null=True, blank=True)
    company_trading_address_line_2 = models.CharField(max_length=255, null=True, blank=True)
    company_trading_address_town = models.CharField(max_length=255, null=True, blank=True)
    company_trading_address_county = models.CharField(max_length=255, null=True, blank=True)
    company_trading_address_country = models.CharField(max_length=255, null=True, blank=True)
    company_trading_address_postcode = models.CharField(max_length=255, null=True, blank=True)

    company_registered_address_line_1 = models.CharField(max_length=255, null=True, blank=True)
    company_registered_address_line_2 = models.CharField(max_length=255, null=True, blank=True)
    company_registered_address_town = models.CharField(max_length=255, null=True, blank=True)
    company_registered_address_county = models.CharField(max_length=255, null=True, blank=True)
    company_registered_address_country = models.CharField(max_length=255, null=True, blank=True)
    company_registered_address_postcode = models.CharField(max_length=255, null=True, blank=True)

    services = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'app_omisdataset'
