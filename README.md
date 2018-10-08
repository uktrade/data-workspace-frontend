# jupyterhub-data-auth-admin

Application that controls authorisation for data sources accessed from JupyterHub

## Running locally

You must initially start the database

```bash
docker run --name jupyteradminpostgres -d --rm -p 5432:5432 \
    -e POSTGRES_USER=postgres \
    -e POSTGRES_PASSWORD=postgres \
    -e POSTGRES_DB=postgres \
    postgres:10.4
```

and then to start the application run

```bash
docker build . -t jupyterhub-data-auth-admin && \
docker run --rm -it -p 8000:8000 \
    --link jupyteradminpostgres:jupyteradminpostgres \
    -e SECRET_KEY=something-secret \
    -e ALLOWED_HOST=localhost \
    -e AUTHBROKER_URL='https://url.to.staff.sso/' \
    -e AUTHBROKER_CLIENT_ID='some-id' \
    -e AUTHBROKER_CLIENT_SECRET='some-secret' \
    -e DB_NAME=postgres \
    -e DB_USER=postgres \
    -e DB_PASSWORD=postgres \
    -e DB_HOST=jupyteradminpostgres \
    -e DB_PORT=5432 \
    jupyterhub-data-auth-admin
```

## Running management commands

Append `django-admin [command]` to the command above to run a management command locally. For more complex operations, append `ash` to enter into a shell and run `django-admin` from there.
