# Generated by Django 4.2.16 on 2024-12-05 08:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0022_team_platform"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="usersatisfactionsurvey",
            name="describe_experience",
        ),
        migrations.AlterField(
            model_name="usersatisfactionsurvey",
            name="how_satisfied",
            field=models.CharField(
                choices=[
                    ("very-satisfied", "Very satisfied"),
                    ("satisfied", "Satisfied"),
                    ("neither", "Neither satisfied nor dissatisfied"),
                    ("dissatisfied", "Dissatisfied"),
                    ("very-dissatisfied", "Very dissatisfied"),
                ],
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="usersatisfactionsurvey",
            name="trying_to_do",
            field=models.TextField(
                blank=True,
                choices=[
                    ("find-data", "Find data"),
                    ("access-data", "Access data"),
                    ("analyse-data", "Analyse data"),
                    ("use-tool", "Use tools"),
                    ("use-visualisation", "Use a data visualisation"),
                    ("other", "Other"),
                ],
                null=True,
            ),
        ),
    ]