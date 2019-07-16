import datetime
import logging

from django import forms
from django.forms.widgets import (
    CheckboxSelectMultiple,
)
from django.contrib import admin

from django.contrib.auth.admin import (
    UserAdmin,
)
from django.contrib.auth.models import (
    Permission,
)

from django.contrib.auth.models import (
    Group,
    User,
)
from django.contrib.contenttypes.models import (
    ContentType,
)

from app.models import (
    ApplicationInstance,
    DataGrouping,
    DataSet,
    DataSetUserPermission,
    SourceLink,
    SourceTable,
    ReferenceDataset,
    ReferenceDatasetField
)
from app.shared import (
    application_instance_max_cpu,
)
from app.common.admin import TimeStampedUserAdmin
from app.dw_admin.forms import ReferenceDataFieldInlineForm

logger = logging.getLogger('app')

admin.site.site_header = 'Data Workspace'

admin.site.unregister(Group)
admin.site.unregister(User)


class DataGroupingAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}
    list_display = ('name', 'slug', 'short_description')


class DataLinkAdmin(admin.ModelAdmin):
    list_display = ('name', 'format', 'url', 'dataset')


admin.site.register(DataGrouping, DataGroupingAdmin)


class AppUserCreationForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = user.email
        user.set_unusable_password()
        if commit:
            user.save()
        return user


class AppUserEditForm(forms.ModelForm):
    can_start_all_applications = forms.BooleanField(
        label='Can access tools',
        help_text='Designates that the user can access tools',
        required=False,
    )
    authorized_datasets = forms.ModelMultipleChoiceField(
        label='Authorized datasets',
        required=False,
        widget=CheckboxSelectMultiple,
        queryset=None,
    )

    class Meta:
        model = User
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs['instance']

        self.fields['can_start_all_applications'].initial = instance.user_permissions.filter(
            codename='start_all_applications',
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        ).exists()

        self.fields['authorized_datasets'].queryset = DataSet.objects.all().order_by('grouping__name', 'name', 'id')
        self.fields['authorized_datasets'].initial = DataSet.objects.filter(
            datasetuserpermission__user=instance,
        )


class AppUserAdmin(UserAdmin):
    add_form_template = 'admin/change_form.html'
    add_form = AppUserCreationForm
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name',),
        }),
    )

    form = AppUserEditForm

    fieldsets = [
        (None, {
            'fields': ['email', 'sso_id', 'first_name', 'last_name']
        }),
        ('Permissions', {
            'fields': [
                'can_start_all_applications',
                'is_staff',
                'is_superuser',
                'authorized_datasets',
            ]}),
    ]

    readonly_fields = ['sso_id']

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ['email']
        return self.readonly_fields

    def save_model(self, request, obj, form, change):
        permission = Permission.objects.get(
            codename='start_all_applications',
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )

        if 'can_start_all_applications' in form.cleaned_data:
            if form.cleaned_data['can_start_all_applications']:
                obj.user_permissions.add(permission)
            else:
                obj.user_permissions.remove(permission)

        if 'authorized_datasets' in form.cleaned_data:
            current_datasets = DataSet.objects.filter(
                datasetuserpermission__user=obj,
            )
            for dataset in form.cleaned_data['authorized_datasets']:
                if dataset not in current_datasets.all():
                    DataSetUserPermission.objects.create(
                        dataset=dataset,
                        user=obj,
                    )
            for dataset in current_datasets:
                if dataset not in form.cleaned_data['authorized_datasets']:
                    DataSetUserPermission.objects.filter(
                        dataset=dataset,
                        user=obj,
                    ).delete()

        super().save_model(request, obj, form, change)

    def sso_id(self, instance):
        return instance.profile.sso_id


class SourceLinkInline(admin.StackedInline):
    model = SourceLink
    extra = 1


class SourceTableInline(admin.StackedInline):
    model = SourceTable
    extra = 1


class DataSetForm(forms.ModelForm):
    requires_authorization = forms.BooleanField(
        label='Each user must be individually authorized to access the data',
        required=False,
    )

    class Meta:
        model = DataSet
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        is_instance = 'instance' in kwargs and kwargs['instance']
        self.fields['requires_authorization'].initial = \
            kwargs['instance'].user_access_type == 'REQUIRES_AUTHORIZATION' if is_instance else \
            True


class DataSetAdmin(admin.ModelAdmin):
    form = DataSetForm

    prepopulated_fields = {'slug': ('name',)}
    list_display = ('name', 'slug', 'short_description', 'grouping')
    inlines = [
        SourceLinkInline,
        SourceTableInline,
    ]
    fieldsets = [
        (None, {
            'fields': [
                'name',
                'slug',
                'short_description',
                'grouping',
                'description',
                'enquiries_contact',
                'redactions',
                'licence',
                'volume',
                'retention_policy',
                'personal_data',
                'restrictions_on_usage',
            ]
        }),
        ('Permissions', {
            'fields': [
                'requires_authorization',
            ]
        })
    ]

    def save_model(self, request, obj, form, change):
        obj.user_access_type = \
            'REQUIRES_AUTHORIZATION' if form.cleaned_data['requires_authorization'] else \
            'REQUIRES_AUTHENTICATION'

        super().save_model(request, obj, form, change)


class ApplicationInstanceAdmin(admin.ModelAdmin):

    list_display = ('owner', 'public_host', 'created_date', )
    fieldsets = [
        (None, {
            'fields': [
                'owner',
                'public_host',
                'created_date',
                'max_cpu',
            ]
        }),
    ]
    readonly_fields = ('owner', 'public_host', 'created_date', 'max_cpu')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
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
                'max_cpu': 'The highest CPU usage in the past two hours. The application will be stopped automatically if the usage is less than 1% for two hours.',
            },
        })
        return super().get_form(request, obj, change, **kwargs)


admin.site.register(User, AppUserAdmin)
admin.site.register(DataSet, DataSetAdmin)
admin.site.register(ApplicationInstance, ApplicationInstanceAdmin)


class ReferenceDataInlineFormset(forms.BaseInlineFormSet):
    model = ReferenceDatasetField

    def clean(self):
        # Ensure one and only one field is set as identifier
        identifiers = [
            x for x in self.forms
            if x.cleaned_data.get('is_identifier') and not x.cleaned_data['DELETE']
        ]
        if len(identifiers) == 0:
            raise forms.ValidationError(
                'Please ensure one field is set as the unique identifier'
            )
        if len(identifiers) > 1:
            raise forms.ValidationError(
                'Please select only one unique identifier field'
            )


class ReferenceDataFieldInline(admin.TabularInline):
    form = ReferenceDataFieldInlineForm
    formset = ReferenceDataInlineFormset
    model = ReferenceDatasetField
    min_num = 1
    extra = 1
    exclude = ['created_date', 'updated_date', 'created_by', 'updated_by', 'deleted']
    fieldsets = [
        (None, {
            'fields': [
                'name',
                'data_type',
                'description',
                'is_identifier'
            ]
        })
    ]


@admin.register(ReferenceDataset)
class ReferenceDatasetAdmin(TimeStampedUserAdmin):
    change_form_template = 'admin/reference_dataset_changeform.html'
    prepopulated_fields = {'slug': ('name',)}
    exclude = ['created_date', 'updated_date', 'created_by', 'updated_by', 'deleted']
    list_display = ('name', 'slug', 'short_description', 'group')
    inlines = [ReferenceDataFieldInline]
    fieldsets = [
        (None, {
            'fields': [
                'name',
                'slug',
                'group',
                'short_description',
                'description',
                'valid_from',
                'valid_to',
                'enquiries_contact',
                'licence',
                'restrictions_on_usage',
            ]
        })
    ]

    def get_queryset(self, request):
        # Only show non-deleted reference datasets in admin
        return self.model.objects.live()

    def get_actions(self, request):
        """
        Disable bulk delete so tables can be managed.
        :param request:
        :return:
        """
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def save_formset(self, request, form, formset, change):
        for f in formset.forms:
            if not change:
                f.instance.created_by = request.user
            f.instance.updated_by = request.user
        super().save_formset(request, form, formset, change)
