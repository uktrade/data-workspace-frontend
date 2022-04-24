from django.core.management.base import BaseCommand
from django.core.management import call_command

class Command(BaseCommand):
    help = "Creates a django superuser for admin.user@example.com"

    def handle(self, *args, **options):
        self.stdout.write("call django management command to create_superuser")
        call_command("createsuperuser", email="admin.user@example.com", username="admin.user@example.com",interactive=False)

