from django.contrib.auth import get_user_model
from django.db import migrations


def migrate_username_to_sso_id(apps, schema_editor):
    dw_users = get_user_model()
    for user in dw_users.objects.all():
        if hasattr(user, 'profile') and user.profile.sso_id:
            user.username = user.profile.sso_id
            user.save()


class Migration(migrations.Migration):
    dependencies = [
        ("applications", "0020_alter_applicationtemplate_group_name"),
    ]

    operations = [
        migrations.RunPython(migrate_username_to_sso_id),
    ]
