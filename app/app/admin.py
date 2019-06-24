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
    DataSetUserPermission,
    SourceLink,
    SourceSchema,
    SourceTables,
)

logger = logging.getLogger('app')

admin.site.site_header = 'Data Workspace'

admin.site.unregister(Group)
admin.site.unregister(User)

admin.site.register(Privilage)


class DataGroupingAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}
    list_display = ('name', 'slug', 'short_description')


class DataLinkAdmin(admin.ModelAdmin):
    list_display = ('name', 'format', 'url', 'dataset')


admin.site.register(DataGrouping, DataGroupingAdmin)

admin.site.register(SourceLink, DataLinkAdmin)


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
            False


class DataSetAdmin(admin.ModelAdmin):
    form = DataSetForm

    prepopulated_fields = {'slug': ('name',)}
    list_display = ('name', 'slug', 'short_description', 'grouping')
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
                'requires_authorization',
            ]
        })
    ]

    def save_model(self, request, obj, form, change):
        obj.user_access_type = \
            'REQUIRES_AUTHORIZATION' if form.cleaned_data['requires_authorization'] else \
            'REQUIRES_AUTHENTICATION'

        super().save_model(request, obj, form, change)


admin.site.register(User, AppUserAdmin)
admin.site.register(DataSet, DataSetAdmin)
admin.site.register(DataSetUserPermission)
