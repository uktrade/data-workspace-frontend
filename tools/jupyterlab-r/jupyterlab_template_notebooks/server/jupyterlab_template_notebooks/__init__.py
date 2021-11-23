from glob import glob
import json
import os
import os.path
from pathlib import PurePosixPath

from notebook.base.handlers import IPythonHandler  # pylint: disable=import-error
from notebook.utils import url_path_join  # pylint: disable=import-error


def _jupyter_server_extension_paths():
    return [{"module": "jupyterlab_template_notebooks"}]


def load_jupyter_server_extension(nb_server_app):
    web_app = nb_server_app.web_app
    base_url = web_app.settings["base_url"]

    host_pattern = ".*$"
    web_app.add_handlers(
        host_pattern,
        [
            (url_path_join(base_url, "templates/"), TemplateListHandler),
            (url_path_join(base_url, "templates/(.+)"), TemplateContentsHandler),
        ],
    )


class TemplateListHandler(IPythonHandler):
    def get(self):
        template_list = json.dumps(
            {
                "templates": [
                    {
                        "path": "/templates/" + PurePosixPath(path).name,
                        "name": PurePosixPath(path).name,
                    }
                    for path in glob(
                        str(PurePosixPath(os.path.realpath(__file__)).parent) + "/*.ipynb"
                    )
                ]
            }
        ).encode("utf-8")
        self.set_header("content-type", "application/json")
        self.set_header("content-length", str(len(template_list)))
        self.write(template_list)
        self.flush()


class TemplateContentsHandler(IPythonHandler):
    def get(self, path):
        current_dir = PurePosixPath(os.path.realpath(__file__)).parent
        file_location = current_dir / path

        # The whole server is readable by the user, but it is typical to
        # forbid escaping the folder
        if current_dir not in file_location.parents:
            self.set_status(404)
            return

        with open(file_location, "rb") as file:
            file_contents_raw = file.read()

        content_types = {".png": "image/png", ".ipynb": "application/json"}
        self.set_header("content-type", content_types[file_location.suffix])

        # Hack to rewrite the SRCs of image. Suspect this will not be needed
        # in latest notebook / JupyterLab, but not bumping for now to not
        # change too much at once
        file_contents_to_send = (
            file_contents_raw
            if file_location.suffix != ".ipynb"
            else file_contents_raw.replace(
                b'<img src=\\"',
                b'<img src=\\"https://' + self.request.headers["host"].encode("utf-8"),
            )
        )

        self.set_header("content-length", str(len(file_contents_to_send)))
        self.write(file_contents_to_send)
        self.flush()
