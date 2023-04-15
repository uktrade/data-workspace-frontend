## Updating a dependendencies

We use [pip-tools](https://github.com/jazzband/pip-tools) to manage dependencies across two files - `requirements.txt` and `requirements-dev.txt`. These have corresponding `.in` files where we specify our top-level dependencies.

Add the new dependencies to those `.in` files, or update an existing dependency, then (with `pip-tools` already installed), run `make save-requirements`.
