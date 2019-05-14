# Analysis Workspace

Allows users to launch applications in order to analyse data


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

and redis

```bash
docker run --rm --name analysis-workspace-redis -d -p 6379:6379 redis:4.0.10
```

and then to start the application run

```bash
docker build . -t jupyterhub-data-auth-admin && \
docker run --rm -it -p 8000:8000 \
    --link jupyteradminpostgres:jupyteradminpostgres \
    --link analysis-workspace-redis:analysis-workspace-redis \
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
    -e REDIS_URL='redis://analysis-workspace-redis:6379' \
    -e APPSTREAM_URL='https://url.to.appstream/' \
    -e SUPPORT_URL='https://url.to.support/' \
    -e NOTEBOOKS_URL='https://url.to.notebooks/' \
    -e APPSTREAM_AWS_SECRET_KEY='secret-key' \
    -e APPSTREAM_AWS_ACCESS_KEY='access-key' \
    -e APPSTREAM_AWS_REGION='region' \
    -e APPSTREAM_FLEET_NAME='fleet-name' \
    -e APPSTREAM_STACK_NAME='stack-name' \
    jupyterhub-data-auth-admin
```

## Creating migrations

Amend the end of the above command to create migrations.

```bash
    ...
    --user root \
    --volume=$PWD/app/app/migrations:/app/app/migrations \
    jupyterhub-data-auth-admin django-admin makemigrations
```

## Running management commands

Append `django-admin [command]` to the command above to run a management command locally. For more complex operations, append `ash` to enter into a shell and run `django-admin` from there.


## Running tests

Redis must be running in a docker container.

```bash
docker run --rm --name analysis-workspace-redis -d -p 6379:6379 redis:4.0.10
```

The tests themselves are also run in a docker container that builds on the production container, to fairly closely simulate the production environment.


```bash
docker build . -t jupyterhub-data-auth-admin && \
docker build . -f Dockerfile-test -t analysis-workspace-test &&  \
docker run --rm \
    --link jupyteradminpostgres:jupyteradminpostgres \
    --link analysis-workspace-redis:analysis-workspace-redis \
    analysis-workspace-test  \
    python3 -m unittest test.test
```


# Building & pushing docker image to Quay

```bash
docker build -t jupyterhub-data-auth-admin . && \
docker tag jupyterhub-data-auth-admin:latest  quay.io/uktrade/jupyterhub-data-auth-admin:latest && \
docker push quay.io/uktrade/jupyterhub-data-auth-admin:latest
```
