from django import forms
from django.contrib import admin

from django.contrib.auth.admin import (
    UserAdmin,
)
from django.contrib.auth.models import (
    User,
)

from app.models import (
    ApplicationTemplate,
    ApplicationInstance,
    Database,
    Privilage,
    Profile,
)

admin.site.register(Database)
admin.site.register(Privilage)
admin.site.register(ApplicationTemplate)
admin.site.register(ApplicationInstance)


class AppUserCreationForm(forms.ModelForm):

    class Meta:
        model = User
        fields = ('email', )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = user.email
        user.set_unusable_password()
        if commit:
            user.save()
        return user


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'
    fk_name = 'user'


class AppUserAdmin(UserAdmin):
    add_form_template = 'admin/change_form.html'
    add_form = AppUserCreationForm
    add_fieldsets = (
        (None, {
            'classes': ('wide', ),
            'fields': ('email', ),
        }),
    )
    inlines = (ProfileInline, )

    def get_inline_instances(self, request, obj=None):
        if not obj:
            return list()
        return super().get_inline_instances(request, obj)

admin.site.unregister(User)
admin.site.register(User, AppUserAdmin)
