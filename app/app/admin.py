import logging

from django import forms
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

from .models import (
    ApplicationInstance,
    Privilage,
    DataGrouping,
    DataSet,
    SourceLink,
    SourceSchema,
    SourceTables,
    ResponsiblePerson,
)

logger = logging.getLogger('app')

admin.site.site_header = 'Data Workspace'

admin.site.unregister(Group)
admin.site.unregister(User)

admin.site.register(Privilage)
admin.site.register(DataGrouping)
admin.site.register(ResponsiblePerson)


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


class AppUserAdmin(UserAdmin):
    add_form_template = 'admin/change_form.html'
    add_form = AppUserCreationForm
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', ),
        }),
    )

    form = AppUserEditForm

    fieldsets = [
        (None, {
            'fields': ['email', 'sso_id', 'first_name', 'last_name']
        }),
        ('Permissions', {
            'fields': ['can_start_all_applications', 'is_staff', 'is_superuser']}),
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

        super().save_model(request, obj, form, change)

    def sso_id(self, instance):
        return instance.profile.sso_id


class SourceLinkInline(admin.StackedInline):
    model = SourceLink
    extra = 1


class SourceSchemaInline(admin.StackedInline):
    model = SourceSchema
    max_num = 1


class SourceTablesInline(admin.StackedInline):
    model = SourceTables
    extra = 1


class DataSetForm(forms.ModelForm):
    requires_security_clearance = forms.BooleanField(
        label='Requires security clearance',
        required=False,
    )

    class Meta:
        model = DataSet
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        is_instance = 'instance' in kwargs and kwargs['instance']
        self.fields['requires_security_clearance'].initial = \
            kwargs['instance'].required_permissions.filter(
                codename='security_clearance',
                content_type=ContentType.objects.get_for_model(DataSet)).exists() if is_instance else \
            False


class DataSetAdmin(admin.ModelAdmin):
    form = DataSetForm

    inlines = [
        SourceLinkInline,
        SourceSchemaInline,
        SourceTablesInline,
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
                'requires_security_clearance',
            ]
        })
    ]

    def save_model(self, request, obj, form, change):
        permission = Permission.objects.get(
            codename='security_clearance',
            content_type=ContentType.objects.get_for_model(DataSet),
        )

        super().save_model(request, obj, form, change)

        if form.cleaned_data['requires_security_clearance']:
            obj.required_permissions.add(permission)
        else:
            obj.required_permissions.remove(permission)


admin.site.register(User, AppUserAdmin)
admin.site.register(DataSet, DataSetAdmin)
