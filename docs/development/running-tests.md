---
title: Running tests
---

Running tests locally is useful when developing features on Data Workspace to make sure existing functionality isn't broken, and to ensure any new functionality works as intended.


## Prerequisites

To create migrations you must have the Data Workspace prerequisites and cloned its source code. See [Running locally](running-locally.md) for details.


## Unit and integration tests

To run all tests:

```bash
make docker-test
```

To only run Django unit tests:

```bash
make docker-test-unit
```

To only run higher level integration tests:

```bash
make docker-test-integration
```


## Without rebuilding

To run the tests locally without having to rebuild the containers every time append `-local` to the test make commands:

```bash
make docker-test-unit-local
```

```bash
make docker-test-integration-local
```

```bash
make docker-test-local
```

To run specific tests pass `-e TARGET=<test>` into make:

```bash
make docker-test-unit-local -e TARGET=dataworkspace/dataworkspace/tests/test_admin.py::TestCustomAdminSite::test_non_admin_access
```

```bash
make docker-test-integration-local -e TARGET=test/test_application.py
```


## Watching Selenium tests

We have some Selenium integration tests that launch a (headless) browser in order to interact with a running instance of Data Workspace to assure some core flows (only Data Explorer at the time of writing). It is sometimes desirable to watch these tests run, e.g. in order to debug where it is failing. To run the selenium tests through docker compose using a local browser, do the following:

1. Download the latest [Selenium Server](https://www.selenium.dev/downloads/) and run it in the background, e.g. `java -jar ~/Downloads/selenium-server-standalone-3.141.59 &`.

2. Run the selenium tests via docker-compose, exposing the Data Workspace port and the mock-SSO port and setting the `REMOTE_SELENIUM_URL` environment variable, e.g. `docker compose --profile test -p data-workspace-test run -e REMOTE_SELENIUM_URL=http://host.docker.internal:4444/wd/hub -p 8000:8000 -p 8005:8005 --rm data-workspace-test pytest -vvvs test/test_selenium.py`.

## E2E tests

There are 2 ways to run the E2E tests locally. The easiest way is to use [docker](#running-the-e2e-tests-locally-using-cypress-docker-image), however this option should only be used to run and view the test results. Due to docker caching images, if any tests need to be updated or new ones added it is better to use [npm](#running-the-e2e-tests-locally-using-npm) as any test changes are immidiately accessible

### Running the E2E tests locally using cypress docker image

The E2E tests can be run locally using the make command `make docker-e2e-build-run` from the root. This will spin up the data workspace app pointing at a dedicated E2E database, that will install some E2E specific fixtures. This DB will not interfere with any local test data you have.

The cypress tests are run using the `data-workspace-e2e-test` docker container. This container will start as soon as it detects the data workspace app is available on port 8000, and as soon as the test complete the docker containers will be closed. To view any tests that failed, browse the `e2e-data-workspace-cypress-1` docker container, where the logs will show a summary of all tests. Any failed tests will also have their screenshots saved in the `cypress/screenshots` folder in your local environment.

### Running the E2E tests locally using npm

Before running the tests, to get the E2E data workspace app run the make command `make docker-e2e-start` from the root, which will spin up the data workspace app pointing at a dedicated E2E database.

Once the containers have started, you can use either `npm run cypress:run` to run the tests in headless mode, or `npm run cypress:open` to use the Cypress test runner app.

### Exporting data for fixtures
If you have manually added some test data and would like to include that data inside an E2E test, this command will write that to a json file for you:
`python3 dataworkspace/manage.py dumpdata --indent=4 MODEL_NAME > dataworkspace/dataworkspace/apps/OUTPUT_FILE.json`

For example:
`python3 dataworkspace/manage.py dumpdata --indent=4 datasets.DataSetUserPermission > dataworkspace/dataworkspace/apps/datasets/fixtures/datasets_datasetuserpermissions.json`