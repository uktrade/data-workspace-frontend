# How to Contribute

In most cases to contribute you will need a [GitHub account](https://github.com/join).

## Contributing an Issue

Suspected issues with Data Workspace can be submitted at the [Data Workspace page](https://github.com/uktrade/data-workspace/issues).
An issue that contains a [minimal, reproducible example](https://stackoverflow.com/help/minimal-reproducible-example) stands the best chance of being resolved. However, it is understood that this is not possible in all circumstances.


## Contributing a Feature Request

A feature request can be submitted using the [Ideas category in Data Workspace discussions](https://github.com/uktrade/data-workspace/discussions/categories/ideas). (This page currently doesn't exist)

## Contributing documentation or code

To contribute changes to documentation or code, you will need the source of data-workspace locally. The instructions for this depend on if you are a member of the [uktrade GitHub organisation](https://github.com/uktrade). In both cases, experience of working with source code, working on the command line, and working with git is helpful.

### If you’re a member of uktrade

1. [Setup an SSH key and associate it with your GitHub account] (https://docs.github.com/en/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account)

2. Clone the repository

    ```bash
    git clone git@github.com:uktrade/data-workspace.git
    cd data-workspace
    ```

You should not fork the repository if you're a member of uktrade.


### If you’re not a member of uktrade

1.[Setup an SSH key and associate it with your GitHub account](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account).

2. Clone the repository.

    ```bash
    git clone git@github.com:/data-workspace.git
    cd data-workspace
    ```

3.[Fork the repository](https://github.com/uktrade/data-workspacefork). Make a note of the "Owner" that you fork to. This is usually your username.
  
  There is more documentation on forking in [GitHub's guide on contributing to projects](https://docs.github.com/en/get-started/quickstart/contributing-to-projects).
  
4. Clone the forked repository. In the following, replace my-username with the owner that you forked to in step 2.

    ```bash
    git clone git@github.com:my-username/data-workspace.git
    cd data-workspace
    ```

## Contributing documentation

The source of the documentation is in the [docs/](https://github.com/uktrade/data-workspace/tree/main/docs) directory of the source code, and is written using [Material for mkdocs](https://squidfunk.github.io/mkdocs-material/).

Changes are then submitted via a Pull Request (PR). To do this:

1. Decide on a short hyphen-separated descriptive name for your change, prefixed with docs/ for example docs/add-example.

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
    gir push origin docs/add-example
    ```
    
6. Raise a PR at [https://github.com/uktrade/data-workspace/pulls](https://github.com/uktrade/data-workspace/pulls) against the main branch in data-workspace.

7. Wait for the PR to be approved and merged, and respond to any questions or suggested changes.

When the PR is merged, the documentation is deployed automatically to [https://uktrade.github.io/data-workspace/](https://uktrade.github.io/data-workspace/).


## Contributing code

To contribute most code changes:

- Knowledge of Python is required. Python iterables, and specifically generators, are used heavily.

Changes are then submitted via a Pull Request (PR). To do this:

1. Decide on a short hyphen-separated descriptive name for your change, prefixed with the type of change. For example fix/the-bug-description.

2. Make a branch using this descriptive name.

    ```bash
    git checkout -b fix-a-bug-description
    ```
    
3. Make sure you can run existing tests locally

    ```bash
    pip install -e ".[dev]"  # Only needed once
    pytest
    ```
    
4. Make your changes in a text editor. In the cases of changing behaviour, this would usually include changing or adding at least one test likely within [dataworkspace/dataworkspace/tests](https://github.com/uktrade/data-workspace/tree/master/dataworkspace/dataworkspace/tests), and running them.

    ```bash
    pytest
    ```
    
5. Commit your changes and push to your fork. Ideally the commit message will follow the [Conventional Commit specification](https://www.conventionalcommits.org/).

    ```bash
    git add stream_zip.py  # Repeat for each file changed
    git commit -m "feat: the bug description"
    git push origin fix/the-bug-description
    ```
    
6. Raise a PR at https://github.com/uktrade/data-workspace/pulls(https://github.com/uktrade/data-workspace/pulls) against the main branch in data-workspace.

7. Wait for the PR to be approved and merged, and respond to any questions or suggested changes.