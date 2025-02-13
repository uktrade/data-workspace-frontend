from django.contrib.auth import get_user_model
from rest_framework import serializers


class UserSerializer(serializers.ModelSerializer):
    user_permissions_subset = serializers.SerializerMethodField()
    user_sso = serializers.SerializerMethodField("get_user_sso")
    first_login = serializers.SerializerMethodField()
    private_schema = serializers.SerializerMethodField()
    sso_status = serializers.SerializerMethodField()

    class Meta:
        model = get_user_model()
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "is_superuser",
            "is_staff",
            "user_permissions_subset",
            "user_sso",
            "first_login",
            "private_schema",
            "sso_status",
        )

    def get_user_permissions_subset(self, user):
        perms_to_check = [
            "develop_visualisations",
            "access_appstream",
            "access_quicksight",
            "start_all_applications",
        ]
        user_permissions_subset = user.user_permissions.filter(codename__in=perms_to_check)
        output = {perm: False for perm in perms_to_check}
        for permission in user_permissions_subset:
            codename = permission.codename
            if codename in perms_to_check:
                output[codename] = True
        return output

    def get_user_sso(self, user):
        try:
            return user.profile.sso_id
        except get_user_model().profile.RelatedObjectDoesNotExist:
            return None

    def get_first_login(self, user):
        try:
            return user.profile.first_login
        except get_user_model().profile.RelatedObjectDoesNotExist:
            return None

    def get_private_schema(self, user):
        try:
            return user.profile.get_private_schema()
        except get_user_model().profile.RelatedObjectDoesNotExist:
            return None

    def get_sso_status(self, user):
        try:
            return user.profile.sso_status
        except get_user_model().profile.RelatedObjectDoesNotExist:
            return None
