import logging
import threading
import time

from django.core.management import call_command
from django.core.management.base import BaseCommand

logger = logging.getLogger('multirunner')


class CommandRunner(threading.Thread):
    def __init__(self, command, args):
        threading.Thread.__init__(self)
        self.command = command
        self.args = args
        self.stop_command = threading.Event()

    def run(self):
        while not self.stop_command.is_set():
            try:
                call_command(self.command, *self.args)
            except Exception as e:  # pylint: disable=broad-except
                logging.error(e)
            time.sleep(1)

    def stop(self):
        self.stop_command.set()


class MultiTask:
    def __init__(self, tasks):
        self.threads = []
        for task, args in tasks:
            self.threads.append(CommandRunner(task, args))

    def start(self):
        for t in self.threads:
            t.start()

    def stop(self):
        for t in self.threads:
            t.stop()


class Command(BaseCommand):
    def handle(self, *args, **options):
        self.stdout.write("Continuously creates dummy datasets. Ctrl+C once you are done.")

        tasks = [
            ('create_master_dataset', []),
            ('create_datacut_dataset', []),
            ('create_reference_dataset', []),
            ('create_visualisation_dataset', []),
        ]
        mt = MultiTask(tasks)
        mt.start()
