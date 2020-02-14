from django.contrib import admin


class TimeStampedUserAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


class DeletableTimeStampedUserAdmin(TimeStampedUserAdmin):
    exclude = ['created_date', 'updated_date', 'created_by', 'updated_by', 'deleted']

    def get_queryset(self, request):
        # Only show non-deleted models in admin
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
