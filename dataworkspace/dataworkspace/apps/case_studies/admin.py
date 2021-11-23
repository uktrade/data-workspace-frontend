from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from dataworkspace.apps.case_studies.models import CaseStudy
from dataworkspace.apps.core.admin import CSPRichTextEditorMixin, TimeStampedUserAdmin


@admin.register(CaseStudy)
class CaseStudyAdmin(CSPRichTextEditorMixin, TimeStampedUserAdmin):
    list_display = (
        'name',
        'short_description',
        'published',
        'publish_date',
        'created_by_link',
        'updated_by_link',
    )
    search_fields = ('name', 'short_description')
    fieldsets = (
        (None, {'fields': ['published', 'name', 'slug', 'short_description']}),
        (
            'Overview',
            {'fields': ['department_name', 'service_name', 'outcome', 'image']},
        ),
        (
            'Details',
            {'fields': ['background', 'solution', 'impact']},
        ),
        (
            'Quote',
            {
                'fields': [
                    'quote_title',
                    'quote_text',
                    'quote_full_name',
                    'quote_department_name',
                ]
            },
        ),
    )
    readonly_fields = (
        'publish_date',
        'created_by',
        'created_date',
        'updated_by',
        'modified_date',
    )
    prepopulated_fields = {'slug': ('name',)}

    def _user_link(self, user):
        return format_html(
            f'<a href="{reverse("admin:auth_user_change", args=(user.id,))}">{user.get_full_name()}</a>'
        )

    def created_by_link(self, obj):
        return self._user_link(obj.created_by)

    created_by_link.short_description = 'Created by'

    def updated_by_link(self, obj):
        return self._user_link(obj.updated_by)

    updated_by_link.short_description = 'Updated  by'
