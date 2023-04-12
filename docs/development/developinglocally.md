## Running locally

### Cloning the Data Workspace Repository

1. [Setup an SSH key and associate it with your GitHub account](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account)

2. Clone the repository

    ```bash
    git clone git@github.com:uktrade/data-workspace.git
    ```

### Starting the Application

Set data infrastructure shared network

```bash
docker network create data-infrastructure-shared-network
```

Set the required variables by

```bash
cp .envs/sample.env .envs/dev.env
```

Start the application by

```bash
docker compose up --build
```

Some parts of the database are managed and populated by [data-flow](https://github.com/uktrade/data-flow/). To ensure there are no issues with some tables being missing, initial setup should include checking out that repo and running the `docker-compose-dw.yml` file, which will perform migrations on the shared Data Workspace/Data Flow DB.

### Domains

With the default environment, in order to be able to properly test cookies that are shared with subdomains, and for the application to be visible at http://dataworkspace.test:8000, you will need the below in your `/etc/hosts` file.

```
127.0.0.1       dataworkspace.test
127.0.0.1       data-workspace-localstack
127.0.0.1       data-workspace-sso.test
```

To run tool and visualisation-related code, you will need subdomains in your `/etc/hosts` file, such as 

```
127.0.0.1       visualisation-a.dataworkspace.test
```

If intending to run superset locally, the following subdomains will also be required

```
127.0.0.1       superset-admin.dataworkspace.test
127.0.0.1       superset-edit.dataworkspace.test
```

### Issues running on Apple Silicon/M1 Chipset?

If you have issues building the containers try the following

```
DOCKER_DEFAULT_PLATFORM=linux/amd64 docker compose up --build
```

## Running superset locally

To get started you will need to create an env file

```bash
cp .envs/superset-sample.env .envs/superset.dev.env
```

Update the new file with your DIT email address (must match your SSO email, or mock SSO credentials).

Then run `docker compose` using the superset profile.

```bash
docker compose --profile superset up
```

Initially you will then need to set up the Editor role by running the following script, replacing container-id with the id of the data-workspace-postgres docker container:

```bash
docker exec -i <container-id> psql -U postgres -d superset < superset/create-editor-role.sql
```

You can then visit http://superset-edit.dataworkspace.test:8000/ or http://superset-admin.dataworkspace.test:8000/

## Creating migrations / running management commands

```bash
docker compose build && \
docker compose run \
    --user root \
    --volume=$PWD/dataworkspace:/dataworkspace/ \
    data-workspace django-admin makemigrations
```

For other commands, replace `makemigrations` with the name of the command.

## Debugging in docker

See the [remote debugging docs](remotedebugging.md)

## Running tests

```bash
make docker-test
```

Django tests
```bash
make docker-test-unit
```

### Running unit and integration tests locally

To run the tests locally without having to rebuild the containers every time append `-local` to the test make commands

```bash
make docker-test-unit-local
```

```bash
make docker-test-integration-local
```

```bash
make docker-test-local
```

To run specific tests pass `-e TARGET=<test>` into make

```bash
make docker-test-unit-local -e TARGET=dataworkspace/dataworkspace/tests/test_admin.py::TestCustomAdminSite::test_non_admin_access
```

```bash
make docker-test-integration-local -e TARGET=test/test_application.py
```

### Running selenium tests locally

We have some selenium integration tests that launch a (headless) browser in order to interact with a running instance of Data Workspace to assure some core flows (only Data Explorer at the time of writing). It is sometimes desirable to watch these tests run, e.g. in order to debug where it is failing. To run the selenium tests through docker compose using a local browser, do the following:

1) Download the latest [Selenium Server](https://www.selenium.dev/downloads/) and run it in the background, e.g. `java -jar ~/Downloads/selenium-server-standalone-3.141.59 &`
2) Run the selenium tests via docker-compose, exposing the Data Workspace port and the mock-SSO port and setting the `REMOTE_SELENIUM_URL` environment variable, e.g. `docker compose --profile test -p data-workspace-test run -e REMOTE_SELENIUM_URL=http://host.docker.internal:4444/wd/hub -p 8000:8000 -p 8005:8005 --rm data-workspace-test pytest -vvvs test/test_selenium.py`

## Updating a dependency

We use [pip-tools](https://github.com/jazzband/pip-tools) to manage dependencies across two files - `requirements.txt` and `requirements-dev.txt`. These have corresponding `.in` files where we specify our top-level dependencies.

Add the new dependencies to those `.in` files, or update an existing dependency, then (with `pip-tools` already installed), run `make save-requirements`.

## Front end static assets

We use [node-sass](https://github.com/sass/node-sass#command-line-interface) to build the front end css and include the GOVUK Front End styles.

To build this locally requires NodeJS. Ideally installed via `nvm` https://github.com/nvm-sh/nvm


```
  # this will configure node from .nvmrc or prompt you to install
  nvm use
  npm install
  npm run build:css
```

## Running the React apps locally

We're set up to use django-webpack-loader for hotloading the react app while developing. 

You can get it running by starting the dev server:

```shell
docker compose up
```

and in a separate terminal changing to the js app directory and running the webpack hotloader:

```shell
cd dataworkspace/dataworkspace/static/js/react_apps/
npm run dev
```

For production usage we use pre-built javascript bundles to reduce the pain of having to build npm modules at deployment.

If you make any changes to the react apps you will need to rebuild and commit the bundles. 
This will create the relevant js files in `/static/js/bundles/` directory.

```shell
cd dataworkspace/dataworkspace/static/js/react_apps/
npm run build
git add ../bundles/*.js ../stats/react_apps-stats.json
```