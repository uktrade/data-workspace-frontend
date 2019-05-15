# Analysis Workspace

Allows users to launch applications in order to analyse data


## Running locally

You must initially start the database

```bash
docker build . -f Dockerfile-postgres -t analysis-workspace-postgres && \
docker run --name analysis-workspace-postgres -d --rm -p 5432:5432 \
    analysis-workspace-postgres
```

and redis

```bash
docker build . -f Dockerfile-redis -t analysis-workspace-redis && \
docker run --name analysis-workspace-redis -d --rm -p 6379:6379  \
    analysis-workspace-redis
```

and then to start the application run

```bash
docker build . -t analysis-workspace && \
docker run --rm -it -p 8000:8000 \
    --link analysis-workspace-postgres:analysis-workspace-postgres \
    --link analysis-workspace-redis:analysis-workspace-redis \
    --env-file=analysis-workspace.env \
    -e AUTHBROKER_URL='https://url.to.staff.sso/' \
    -e AUTHBROKER_CLIENT_ID='some-id' \
    -e AUTHBROKER_CLIENT_SECRET='some-secret' \
    analysis-workspace
```

## Creating migrations

Amend the end of the above command to create migrations.

```bash
    ...
    --user root \
    --volume=$PWD/app/app/migrations:/app/app/migrations \
    analysis-workspace django-admin makemigrations
```

## Running management commands

Append `django-admin [command]` to the command above to run a management command locally. For more complex operations, append `ash` to enter into a shell and run `django-admin` from there.


## Running tests

The tests themselves are also run in a docker container that builds on the production container, to fairly closely simulate the production environment.


```bash
docker build . -t analysis-workspace && \
docker build . -f Dockerfile-test -t analysis-workspace-test &&  \
docker run --rm \
    --link analysis-workspace-postgres:analysis-workspace-postgres \
    --link analysis-workspace-redis:analysis-workspace-redis \
    analysis-workspace-test  \
    python3 -m unittest test.test
```


# Building & pushing docker image to Quay

```bash
docker build -t analysis-workspace . && \
docker tag analysis-workspace:latest quay.io/uktrade/jupyterhub-data-auth-admin:latest && \
docker push quay.io/uktrade/jupyterhub-data-auth-admin:latest
```
