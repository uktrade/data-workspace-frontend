from datetime import datetime

from django.contrib import admin

from dataworkspace.apps.applications.models import ApplicationInstance
from dataworkspace.apps.applications.utils import application_instance_max_cpu


@admin.register(ApplicationInstance)
class ApplicationInstanceAdmin(admin.ModelAdmin):

    list_display = ('owner', 'public_host', 'created_date', )
    fieldsets = [
        (None, {
            'fields': [
                'owner',
                'public_host',
                'created_date',
                'spawner_application_instance_id',
                'max_cpu',
            ]
        }),
    ]
    readonly_fields = (
        'owner', 'public_host', 'created_date', 'spawner_application_instance_id', 'max_cpu',
    )

    def has_add_permission(self, request):
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(state='RUNNING')

    def max_cpu(self, obj):
        try:
            max_cpu, ts_at_max = application_instance_max_cpu(obj)
        except ValueError as exception:
            return exception.args[0] if exception.args else 'Error'

        return '{0:.2f}% at {1}'.format(
            max_cpu,
            datetime.datetime.fromtimestamp(ts_at_max).strftime('%-I:%M %p').replace('AM', 'a.m.').replace('PM', 'p.m'),
        )

    max_cpu.short_description = 'Max recent CPU'

    def get_form(self, request, obj=None, change=False, **kwargs):
        kwargs.update({
            'help_texts': {
                'max_cpu': ('The highest CPU usage in the past two hours.'
                            'The application will be stopped automatically '
                            'if the usage is less than 1% for two hours.'),
            },
        })
        return super().get_form(request, obj, change, **kwargs)
