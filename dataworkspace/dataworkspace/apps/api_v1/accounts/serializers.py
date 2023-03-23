from django.contrib.auth import get_user_model
from rest_framework import serializers


class UserSerializer(serializers.ModelSerializer):
    user_permissions_subset = serializers.SerializerMethodField()
    user_sso = serializers.SerializerMethodField("get_user_sso")
    first_login = serializers.SerializerMethodField()
    private_schema = serializers.SerializerMethodField()

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
        return user.profile.sso_id

    def get_first_login(self, user):
        return user.profile.first_login

    def get_private_schema(self, user):

        return user.profile.get_private_schema()
