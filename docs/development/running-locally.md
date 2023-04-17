---
title: Running locally
---

To develop features on Data Workspace, or to evaluate if it's suitable for your use case, it can be helpful to run Data Workspace on your local computer.


## Prerequisites

To run Data Workspace locally, you must have these tools installed:

- [Docker](https://docs.docker.com/get-docker/)
- [Git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)

You should also have familiarity with the command line, and editing text files. If you plan to make changes to the Data Workspace source code, you should also have familiarity with [Python](https://www.python.org/).


## Cloning source code

To run Data Workspace locally, you must also have the Data Workspace source code, which is stored in the [Data Workspace GitHub repository](https://github.com/uktrade/data-workspace). The process of copying this code so it is available locally is known as cloning.

1. If you don't already have a GitHub account, [create a GitHub account](https://github.com/signup)

2. [Setup an SSH key and associate it with your GitHub account](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account)

3. [Create a new fork of the Data Workspace repository](https://github.com/uktrade/data-workspace/fork). Make a note of the owner you choose to fork to. This is usually your GitHub username. There is more documentation on forking at [GitHub's guide on contributing to projects](https://docs.github.com/en/get-started/quickstart/contributing-to-projects).

    If you're a member if the [uktrade GitHub organsation](https://github.com/uktrade) you should skip this step and not fork. If you're not planning on contributing changes, you can also skip forking.


4. Clone the repository by running the following command, replacing `owner` with the owner that you forked to in step 3. If you skipped forking, `owner` should be `uktrade`.

    ```bash
    git clone git@github.com:owner/data-workspace.git
    ```

    This will create a new directory containing a copy of the Data Workspace source code, `data-workspace`.

5. Change to the `data-workspace` directory

    ```bash
    cd data-workspace
    ```

## Creating domains

In order to be able to properly test cookies that are shared with subdomains, localhost is not used for local development. Instead, by default the dataworkspace.test domain is used. For this to work, you will need the below in your `/etc/hosts` file.

```
127.0.0.1       dataworkspace.test
127.0.0.1       data-workspace-localstack
127.0.0.1       data-workspace-sso.test
127.0.0.1       superset-admin.dataworkspace.test
127.0.0.1       superset-edit.dataworkspace.test
```

To run tool and visualisation-related code, you will need subdomains in your `/etc/hosts` file, such as 

```
127.0.0.1       visualisation-a.dataworkspace.test
```


## Starting the application

Set the required variables by

```bash
cp .envs/sample.env .envs/dev.env
```

Start the application by

```bash
docker compose up --build
```

The application should then visible at [http://dataworkspace.test:8000](http://dataworkspace.test:8000).

## Running Superset locally

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


## Front end static assets

We use [node-sass](https://github.com/sass/node-sass#command-line-interface) to build the front end css and include the GOVUK Front End styles.

To build this locally requires NodeJS. Ideally installed via `nvm` [https://github.com/nvm-sh/nvm)](https://github.com/nvm-sh/nvm)


```
  # this will configure node from .nvmrc or prompt you to install
  nvm use
  npm install
  npm run build:css
```


## React apps

We're set up to use django-webpack-loader for hotloading the React app while developing. 

You can get it running by starting the dev server:

```shell
docker compose up
```

and in a separate terminal changing to the js app directory and running the webpack hotloader:

```shell
cd dataworkspace/dataworkspace/static/js/react_apps/
npm run dev
```

For production usage we use pre-built JavaScript bundles to reduce the pain of having to build npm modules at deployment.

If you make any changes to the React apps you will need to rebuild and commit the bundles. 
This will create the relevant js files in `/static/js/bundles/` directory.

```shell
cd dataworkspace/dataworkspace/static/js/react_apps/
# this may about 10 minutes to install all dependencies
npm install
npm run build
git add ../bundles/*.js ../stats/react_apps-stats.json
```


## Issues on Apple Silicon

If you have issues building the containers try the following

```
DOCKER_DEFAULT_PLATFORM=linux/amd64 docker compose up --build
```
