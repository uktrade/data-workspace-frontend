# Generated by Django 3.2.19 on 2023-05-12 10:53

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0013_auto_20230511_1615"),
        ("applications", "0020_alter_applicationtemplate_group_name"),
    ]

    operations = [
        migrations.AlterField(
            model_name="applicationinstance",
            name="owner",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, to="core.dataworkspaceuser"
            ),
        ),
        migrations.AlterField(
            model_name="usertoolconfiguration",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, to="core.dataworkspaceuser"
            ),
        ),
        migrations.AlterField(
            model_name="visualisationapproval",
            name="approver",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, to="core.dataworkspaceuser"
            ),
        ),
    ]