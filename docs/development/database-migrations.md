# Database migrations

Data Workspace is written in Python, and uses [Django](https://www.djangoproject.com/) as the framework for its user-facing metadata catalogue and permissions system. When developing Data Workspace, if a change is made to Django's models, then to reflect this change in the metadata database, migrations must be created and run.

To create any required migrations locally

```bash
docker compose build && \
docker compose run \
    --user root \
    --volume=$PWD/dataworkspace:/dataworkspace/ \
    data-workspace django-admin makemigrations
```

The migrations must be committed to the codebase, and will run when Data Workspace is next started.

This pattern can be used to run other Django management commands by replacing `makemigrations` with the name of the command.
