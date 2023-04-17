# How to contribute

Contributions to Data Workspace are welcome, such as reporting issues, requesting features, making documentation changes, or submitting code changes.


## Prerequisites

- In all cases a [GitHub account](https://github.com/join) is needed to contribute.
- To contribute code or documentation, you must have a copy of the Data Workspace source code locally, and have certain tools installed. See [Running locally](https://data-workspace.docs.trade.gov.uk/development/running-locally/) for details of these.
- To contribute code, knowledge of [Python](https://www.python.org/) is required.


## Issues

Suspected issues with Data Workspace can be submitted at [Data Workspace issues](https://github.com/uktrade/data-workspace/issues).
An issue that contains a [minimal, reproducible example](https://stackoverflow.com/help/minimal-reproducible-example) stands the best chance of being resolved. However, it is understood that this is not possible in all circumstances.


## Feature requests

A feature request can be submitted using the [Ideas category in Data Workspace discussions](https://github.com/uktrade/data-workspace/discussions/categories/ideas).


## Documentation

The source of the documentation is in the [`docs/`](https://github.com/uktrade/data-workspace/tree/master/docs) directory of the source code, and is written using [Material for mkdocs](https://squidfunk.github.io/mkdocs-material/).

Changes are then submitted via a Pull Request (PR). To do this:

1. Decide on a short hyphen-separated descriptive name for your change, prefixed with `docs/`, for example `docs/add-example`.

2. Make a branch using this descriptive name.

    ```bash
    git checkout -b docs/add-example
    cd data-workspace
    ```

3. Make your changes in a text editor.

4. Preview your changes locally.

    ```bash
    pip install -r requirements-docs.txt  # Only needed once
    mkdocs serve
    ```

5. Commit your change and push to your fork. Ideally the commit message will follow the [Conventional Commit specification](https://www.conventionalcommits.org/).

    ```bash
    git add docs/getting-started.md  # Repeat for each file changed
    git commit -m "docs: add an example"
    git push origin docs/add-example
    ```

6. Raise a PR at [https://github.com/uktrade/data-workspace/pulls](https://github.com/uktrade/data-workspace/pulls) against the main branch in data-workspace.

7. Wait for the PR to be approved and merged, and respond to any questions or suggested changes.

When the PR is merged, the documentation is deployed automatically to [https://data-workspace.docs.trade.gov.uk/](https://data-workspace.docs.trade.gov.uk/).


## Code

Changes are submitted via a Pull Request (PR). To do this:

1. Decide on a short hyphen-separated descriptive name for your change, prefixed with the type of change. For example `fix/the-bug-description`.

2. Make a branch using this descriptive name.

    ```bash
    git checkout -b fix/a-bug-description
    ```

3. Make sure you can run existing tests locally, for example by running:

    ```bash
    make docker-test
    ```

    See [Running tests](https://data-workspace.docs.trade.gov.uk/development/running-tests/) for more details on running tests.

4. Make your changes in a text editor. In the cases of changing behaviour, this would usually include changing or adding tests within [dataworkspace/dataworkspace/tests](https://github.com/uktrade/data-workspace/tree/master/dataworkspace/dataworkspace/tests), and running them.


5. Commit your changes and push to your fork. Ideally the commit message will follow the [Conventional Commit specification](https://www.conventionalcommits.org/).

    ```bash
    git add my_file.py  # Repeat for each file changed
    git commit -m "fix: the bug description"
    git push origin fix/the-bug-description
    ```

6. Raise a PR at [https://github.com/uktrade/data-workspace/pulls](https://github.com/uktrade/data-workspace/pulls) against the master branch of data-workspace.

7. Wait for the PR to be approved and merged, and respond to any questions or suggested changes.
