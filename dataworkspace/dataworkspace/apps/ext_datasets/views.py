import csv
from datetime import datetime
import gevent.queue

from django.db.models import DateField, Q
from django.db.models.functions import TruncMonth
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.http import StreamingHttpResponse
from django.views import View

from dataworkspace.apps.datasets.models import DataSet
from dataworkspace.apps.ext_datasets.models import OMISDataset


class Echo:
    """An object that implements just the write method of the file-like
    interface.
    """

    def write(self, value):
        """Write the value by returning it, instead of storing in a buffer."""
        return value


class BaseOmisReportView(View):
    """Base View to present report from OMISDataset in CSV format.
    """
    # TODO Allow users to create reports dynamically for any given dataset by creating metareports
    name = None
    """Name of the report."""
    completion_date = None
    """Date omis orders completed"""
    field_names = None
    """Desired field names of OMISDataset to be shown in the report"""

    def get_completion_date_from_request(self):
        completion_date = self.request.GET.get('completion_date')
        try:
            completion_date = datetime.strptime(completion_date, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return False

        return completion_date

    def fetch_report_from_omis_dataset(self):

        def yield_bytes_from_queue():
            while True:
                try:
                    yield bytes_queue.get(timeout=0.1)
                except gevent.queue.Empty:
                    break

        def iter_queryset(queryset):
            for record in queryset:
                yield [record[field_name] for field_name in self.field_names]

        queryset = OMISDataset.objects.annotate(
            first_day_of_month=TruncMonth('completion_date', output_field=DateField())
        ).filter(
            self.get_filter_by_q_object()
        ).values(*self.field_names)

        csv_writer = csv.writer(Echo())

        queue_size = 5
        bytes_queue = gevent.queue.Queue(maxsize=queue_size)

        field_verbose_names = []
        for field in OMISDataset._meta.get_fields():
            if field.name in self.field_names:
                field_verbose_names.append(field.verbose_name)

        bytes_queue.put(
            csv_writer.writerow(field_verbose_names), timeout=10
        )

        if queryset:
            bytes_fetched = ''.join(
                csv_writer.writerow(row) for row in iter_queryset(queryset)
            ).encode('utf-8')

            bytes_queue.put(bytes_fetched, timeout=15)

        response = StreamingHttpResponse(yield_bytes_from_queue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{self.name}-{self.completion_date}.csv"'
        return response

    def get_filter_by_q_object(self):
        # Must be defined on inherited views
        raise NotImplementedError

    def get(self, request):
        # Prevent presenting any report without having a valid meta dataset provided
        dataset_id = request.GET.get('dataset_id')
        if not dataset_id:
            raise SuspiciousOperation('Dataset id must be provided')
        try:
            dataset = DataSet.objects.get(id=dataset_id)
        except DataSet.DoesNotExist:
            raise SuspiciousOperation('Provided dataset not exist')

        if not dataset.published:
            raise SuspiciousOperation('Requested dataset is not published')

        if not dataset.user_has_access(request.user):
            raise PermissionDenied()

        self.completion_date = self.get_completion_date_from_request()
        if not self.completion_date:
            raise SuspiciousOperation('Completion date must be provided in the format (YYYY-MM-DD)')
        return self.fetch_report_from_omis_dataset()


class OMISCompletedOrderReportView(BaseOmisReportView):
    name = 'OMIS Completed Order Report'
    field_names = [
        'company_name',
        'DIT_team',
        'subtotal',
        'UK_region',
        'market',
        'sector_name',
        'services',
        'delivery_date',
        'payment_received_date',
        'completion_date',
    ]

    def get_filter_by_q_object(self):
        return (Q(first_day_of_month=self.completion_date) &
                Q(order_status=OMISDataset.COMPLETE))


class OMISCancelledOrderReportView(BaseOmisReportView):
    name = 'OMIS Cancelled Order Report'
    field_names = [
        'omis_order_reference',
        'company_name',
        'net_price',
        'DIT_team',
        'market',
        'created_date',
        'cancelled_date',
        'cancellation_reason_text',
    ]

    def get_filter_by_q_object(self):
        return (Q(first_day_of_month__gte=self.completion_date) &
                Q(order_status=OMISDataset.CANCELLED))


class OMISClientSurveyReportView(BaseOmisReportView):
    name = 'OMIS Client Survey Report'
    field_names = [
        'company_name',
        'contact_first_name',
        'contact_last_name',
        'contact_phone_number',
        'contact_email_address',
        'company_trading_address_line_1',
        'company_trading_address_line_2',
        'company_trading_address_town',
        'company_trading_address_county',
        'company_trading_address_country',
        'company_trading_address_postcode',
        'company_registered_address_line_1',
        'company_registered_address_line_2',
        'company_registered_address_town',
        'company_registered_address_county',
        'company_registered_address_country',
        'company_registered_address_postcode',
    ]

    def get_filter_by_q_object(self):
        return (Q(first_day_of_month=self.completion_date) &
                Q(order_status=OMISDataset.COMPLETE))
