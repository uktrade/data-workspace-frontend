## Prerequisites and source code

To run tests you must have the Data Workspace prerequisites and cloned its source code. See [Running locally](running-locally.md) for details.


## Unit and integration tests

To run all tests

```bash
make docker-test
```

To only run Django unit tests

```bash
make docker-test-unit
```

To only run higher level integration tests

```bash
make docker-test-integration
```


## Unit and integration tests without rebuilding containers

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


## Watching selenium tests run

We have some selenium integration tests that launch a (headless) browser in order to interact with a running instance of Data Workspace to assure some core flows (only Data Explorer at the time of writing). It is sometimes desirable to watch these tests run, e.g. in order to debug where it is failing. To run the selenium tests through docker compose using a local browser, do the following:

1) Download the latest [Selenium Server](https://www.selenium.dev/downloads/) and run it in the background, e.g. `java -jar ~/Downloads/selenium-server-standalone-3.141.59 &`
2) Run the selenium tests via docker-compose, exposing the Data Workspace port and the mock-SSO port and setting the `REMOTE_SELENIUM_URL` environment variable, e.g. `docker compose --profile test -p data-workspace-test run -e REMOTE_SELENIUM_URL=http://host.docker.internal:4444/wd/hub -p 8000:8000 -p 8005:8005 --rm data-workspace-test pytest -vvvs test/test_selenium.py`
