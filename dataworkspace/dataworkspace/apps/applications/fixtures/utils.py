import json
import pathlib


def get_fixture(path):
    return json.loads((pathlib.Path(__file__).parent / path).read_text())
