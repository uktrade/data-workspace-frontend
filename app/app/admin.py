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
    ResponsiblePerson,
)

logger = logging.getLogger('app')

admin.site.site_header = 'Data Workspace'

admin.site.unregister(Group)
admin.site.unregister(User)

admin.site.register(Privilage)
admin.site.register(DataGrouping)
admin.site.register(DataSet)
admin.site.register(SourceLink)
admin.site.register(ResponsiblePerson)


class AppUserCreationForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('email',)

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
            'fields': ('email',),
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

    readonly_fields = ['sso_id', 'first_name', 'last_name']

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


admin.site.register(User, AppUserAdmin)
