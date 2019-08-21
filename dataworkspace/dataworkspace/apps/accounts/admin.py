from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import (
    UserAdmin,
)
from django.contrib.auth.models import (
    Permission,
)
from django.contrib.contenttypes.models import (
    ContentType,
)
from django.db import (
    transaction,
)
from django.forms.widgets import (
    CheckboxSelectMultiple,
)

from dataworkspace.apps.datasets.models import DataSet, DataSetUserPermission
from dataworkspace.apps.applications.models import ApplicationInstance


class AppUserCreationForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
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
        label='Can start local tools',
        help_text='For JupyterLab, rStudio and pgAdmin',
        required=False,
    )
    can_access_appstream = forms.BooleanField(
        label='Can access AppStream',
        help_text='For SPSS and STATA',
        required=False,
    )
    authorized_datasets = forms.ModelMultipleChoiceField(
        label='Authorized datasets',
        required=False,
        widget=CheckboxSelectMultiple,
        queryset=None,
    )

    class Meta:
        model = get_user_model()
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs['instance']

        self.fields['can_start_all_applications'].initial = instance.user_permissions.filter(
            codename='start_all_applications',
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        ).exists()

        self.fields['can_access_appstream'].initial = instance.user_permissions.filter(
            codename='access_appstream',
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        ).exists()

        self.fields['authorized_datasets'].queryset = DataSet.objects.all().order_by('grouping__name', 'name', 'id')
        self.fields['authorized_datasets'].initial = DataSet.objects.filter(
            datasetuserpermission__user=instance,
        )


admin.site.unregister(get_user_model())


@admin.register(get_user_model())
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
                'can_access_appstream',
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

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        start_all_applications_permission = Permission.objects.get(
            codename='start_all_applications',
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        access_appstream_permission = Permission.objects.get(
            codename='access_appstream',
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )

        if 'can_start_all_applications' in form.cleaned_data:
            if (
                    form.cleaned_data['can_start_all_applications'] and
                    start_all_applications_permission not in obj.user_permissions.all()
            ):
                obj.user_permissions.add(start_all_applications_permission)
            elif start_all_applications_permission in obj.user_permissions.all():
                obj.user_permissions.remove(start_all_applications_permission)

        if 'can_access_appstream' in form.cleaned_data:
            if (
                    form.cleaned_data['can_access_appstream'] and
                    access_appstream_permission not in obj.user_permissions.all()
            ):
                obj.user_permissions.add(access_appstream_permission)
            elif access_appstream_permission in obj.user_permissions.all():
                obj.user_permissions.remove(access_appstream_permission)

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
