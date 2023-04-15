# Database migrations

Data Workspace's user-facing metadata catalogue uses [Django](https://www.djangoproject.com/). When developing Data Workspace, if a change is made to Django's models, to reflect this change in the metadata database, migrations must be created and run.


## Prerequisites and source code

To create migrations you must have the Data Workspace prerequisites and cloned its source code. See [Running locally](running-locally.md) for details.


## Creating migrations

After making changes to Django models, to create any required migrations:

```bash
docker compose build && \
docker compose run \
    --user root \
    --volume=$PWD/dataworkspace:/dataworkspace/ \
    data-workspace django-admin makemigrations
```

The migrations must be committed to the codebase, and will run when Data Workspace is next started.

This pattern can be used to run other Django management commands by replacing `makemigrations` with the name of the command.
