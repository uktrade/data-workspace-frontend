# jupyterhub-data-auth-admin

Application that controls authorisation for data sources accessed from JupyterHub

## Running locally

You must initially start the database

```bash
openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 -subj /CN=jupyteradminpostgres \
    -keyout ssl.key \
    -out ssl.crt && \
chmod 0600 ssl.key ssl.crt && \
docker run --name jupyteradminpostgres -d --rm -p 5432:5432 \
    -e POSTGRES_USER=postgres \
    -e POSTGRES_PASSWORD=postgres \
    -e POSTGRES_DB=postgres \
    -v $PWD/ssl.crt:/ssl.crt \
    -v $PWD/ssl.key:/ssl.key \
    postgres:10.4 \
    -c ssl=on -c ssl_cert_file=/ssl.crt -c ssl_key_file=/ssl.key
```

and then to start the application run

```bash
docker build . -t jupyterhub-data-auth-admin && \
docker run --rm -it -p 8000:8000 \
    --link jupyteradminpostgres:jupyteradminpostgres \
    -e SECRET_KEY=something-secret \
    -e ALLOWED_HOSTS__1=localhost \
    -e AUTHBROKER_URL='https://url.to.staff.sso/' \
    -e AUTHBROKER_CLIENT_ID='some-id' \
    -e AUTHBROKER_CLIENT_SECRET='some-secret' \
    -e ADMIN_DB__NAME=postgres \
    -e ADMIN_DB__USER=postgres \
    -e ADMIN_DB__PASSWORD=postgres \
    -e ADMIN_DB__HOST=jupyteradminpostgres \
    -e ADMIN_DB__PORT=5432 \
    -e DATA_DB__my_database__NAME=postgres \
    -e DATA_DB__my_database__USER=postgres \
    -e DATA_DB__my_database__PASSWORD=postgres \
    -e DATA_DB__my_database__HOST=jupyteradminpostgres \
    -e DATA_DB__my_database__PORT=5432 \
    jupyterhub-data-auth-admin
```

## Creating migrations

Amend the end of the above command to create migrations.

```bash
    ...
    --user root \
    --volume=$PWD/app/app/migrations:/app/migrations \
    jupyterhub-data-auth-admin django-admin makemigrations
```

## Running management commands

Append `django-admin [command]` to the command above to run a management command locally. For more complex operations, append `ash` to enter into a shell and run `django-admin` from there.
