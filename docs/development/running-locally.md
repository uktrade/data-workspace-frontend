## Cloning the Data Workspace repository

To run Data Workspace locally, you must have the Data Workspace source code, which is stored in the [Data Workspace GitHub repository](https://github.com/uktrade/data-workspace). The process of copying this code so it is available locally is known as cloning.

1. [Setup an SSH key and associate it with your GitHub account](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account)

2. Clone the repository

    ```bash
    git clone git@github.com:uktrade/data-workspace.git
    ```

3. Change to the Data Workspace directory

    ```bash
    cd data-workspace
    ```


## Creating dataworkspace.test domains

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

Some parts of the database are managed and populated by [data-flow](https://github.com/uktrade/data-flow/). To ensure there are no issues with some tables being missing, initial setup should include checking out that repo and running the `docker-compose-dw.yml` file, which will perform migrations on the shared Data Workspace/Data Flow DB.


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


## Issues running on Apple Silicon/M1 chipset?

If you have issues building the containers try the following

```
DOCKER_DEFAULT_PLATFORM=linux/amd64 docker compose up --build
```
