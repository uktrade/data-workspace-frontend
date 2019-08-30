from rest_framework import serializers

from dataworkspace.apps.ext_datasets.models import OMISDataset


class OMISDatasetSerializer(serializers.ModelSerializer):
    reference = serializers.CharField(max_length=100, source='omis_order_reference')
    company__name = serializers.CharField(max_length=100, source='company_name')
    status = serializers.CharField(max_length=100, source='order_status')
    contact__first_name = serializers.CharField(max_length=255, source='contact_first_name')
    contact__last_name = serializers.CharField(max_length=255, source='contact_last_name')
    contact__email = serializers.CharField(max_length=255, source='contact_email_address')
    contact__telephone_number = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=255, source='contact_phone_number'
    )
    invoice__subtotal_cost = serializers.IntegerField(required=False, allow_null=True, source='subtotal')
    subtotal_cost = serializers.IntegerField(required=False, allow_null=True, source='net_price')
    sector__segment = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=255, source='sector_name'
    )
    primary_market__name = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=255, source='market'
    )
    created_by__dit_team__name = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, source='DIT_team'
    )
    uk_region__name = serializers.CharField(required=False, allow_null=True, allow_blank=True, source='UK_region')
    created_on = serializers.DateTimeField(required=False, allow_null=True, source='created_date')
    cancelled_on = serializers.DateTimeField(required=False, allow_null=True, source='cancelled_date')
    cancellation_reason__name = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, source='cancellation_reason_text'
    )
    completed_on = serializers.DateTimeField(required=False, allow_null=True, source='completion_date')
    paid_on = serializers.DateTimeField(required=False, allow_null=True, source='payment_received_date')
    company__address_1 = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=255, source='company_trading_address_line_1'
    )
    company__address_2 = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=255, source='company_trading_address_line_2'
    )
    company__address_town = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=255, source='company_trading_address_town'
    )
    company__address_county = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=255, source='company_trading_address_county'
    )
    company__address_country__name = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=255, source='company_trading_address_country'
    )
    company__address_postcode = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=255, source='company_trading_address_postcode'
    )
    company__registered_address_1 = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=255, source='company_registered_address_line_1'
    )
    company__registered_address_2 = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=255, source='company_registered_address_line_2'
    )
    company__registered_address_town = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=255, source='company_registered_address_town'
    )
    company__registered_address_county = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=255, source='company_registered_address_county'
    )
    company__registered_address_country__name = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=255, source='company_registered_address_country'
    )
    company__registered_address_postcode = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=255, source='company_registered_address_postcode'
    )

    class Meta:
        model = OMISDataset
        fields = ('reference', 'company__name', 'status', 'contact__first_name', 'contact__last_name', 'contact__email',
                  'contact__telephone_number', 'invoice__subtotal_cost', 'subtotal_cost', 'sector__segment',
                  'primary_market__name', 'created_by__dit_team__name', 'uk_region__name', 'created_on', 'cancelled_on',
                  'cancellation_reason__name', 'completed_on', 'delivery_date', 'paid_on', 'company__address_1',
                  'company__address_2', 'company__address_town', 'company__address_county',
                  'company__address_country__name', 'company__address_postcode', 'company__registered_address_1',
                  'company__registered_address_2', 'company__registered_address_town',
                  'company__registered_address_county', 'company__registered_address_country__name',
                  'company__registered_address_postcode', 'services')
