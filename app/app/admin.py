from django import forms
from django.contrib import admin

from django.contrib.auth.admin import (
    UserAdmin,
)
from django.contrib.auth.models import (
    User,
)

from app.models import (
    Database,
    Privilage,
)

admin.site.register(Database)
admin.site.register(Privilage)


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


class AppUserAdmin(UserAdmin):
    add_form_template = 'admin/change_form.html'
    add_form = AppUserCreationForm
    add_fieldsets = (
        (None, {
            'classes': ('wide', ),
            'fields': ('email', ),
        }),
    )

admin.site.unregister(User)
admin.site.register(User, AppUserAdmin)
