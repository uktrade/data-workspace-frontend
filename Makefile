SHELL := /bin/bash
APPLICATION_NAME="uktrade / data-workspace"
APPLICATION_VERSION=1.0

# Colour coding for output
COLOUR_NONE=\033[0m
COLOUR_GREEN=\033[1;36m
COLOUR_YELLOW=\033[33;01m

.PHONY: help test
help:
	@echo -e "$(COLOUR_GREEN)|--- $(APPLICATION_NAME) [$(APPLICATION_VERSION)] ---|$(COLOUR_NONE)"
	@echo -e "$(COLOUR_YELLOW)make up$(COLOUR_NONE) : launches containers for local development"
	@echo -e "$(COLOUR_YELLOW)make docker-test-shell-local$(COLOUR_NONE) : bash shell for the unit tests in a container with your local volume mounted"
	@echo -e "$(COLOUR_YELLOW)make docker-test-unit-local$(COLOUR_NONE) : runs the unit tests in a container with your local volume mounted"
	@echo -e "$(COLOUR_YELLOW)make docker-test-integration$(COLOUR_NONE) : runs the integration tests in a container (10 minutes min)"
	@echo -e "$(COLOUR_YELLOW)make logout$(COLOUR_NONE): logs out the current user"

.PHONY: first-use
first-use:
	docker network create data-infrastructure-shared-network || true

.PHONY: up
up: first-use
	docker compose up

.PHONY: docker-build
docker-build:
	docker compose --profile test build

.PHONY: docker-test-unit
docker-test-unit: TESTS ?= /dataworkspace/dataworkspace
docker-test-unit: docker-build
	docker compose --profile test -p data-workspace-test run data-workspace-test pytest -vv --junitxml=/test-results/junit.xml $(TESTS)

.PHONY: docker-test-integration
docker-test-integration: TESTS ?= test/
docker-test-integration: docker-build
	docker compose --profile test -p data-workspace-test run data-workspace-test pytest --junitxml=/test-results/junit.xml $(TESTS)

.PHONY: docker-test
docker-test: docker-test-integration docker-test-unit

.PHONY: docker-e2e-build
docker-e2e-build:
	docker compose -f docker-compose.yml -f docker-compose.e2e.yml -p e2e --profile e2e build --parallel

.PHONY: docker-e2e-run
docker-e2e-run:
	docker compose -f docker-compose.yml -f docker-compose.e2e.yml -p e2e --profile e2e up --renew-anon-volumes --exit-code-from data-workspace-e2e-test

.PHONY: docker-e2e-build-run
docker-e2e-build-run:
	docker compose -f docker-compose.yml -f docker-compose.e2e.yml -p e2e --profile e2e up --build --force-recreate --renew-anon-volumes --exit-code-from data-workspace-e2e-test

.PHONY: docker-e2e-start
docker-e2e-start:
	docker compose -f docker-compose.yml -f docker-compose.e2e.yml -p e2e --profile e2e up --build --force-recreate --renew-anon-volumes -d

.PHONY: docker-a11y-build
docker-a11y-build:
	docker compose -f docker-compose.yml -f docker-compose.a11y.yml -p a11y --profile a11y build

.PHONY: docker-a11y-run
docker-a11y-run:
	docker compose -f docker-compose.yml -f docker-compose.a11y.yml -p a11y --profile a11y up --exit-code-from data-workspace-e2e-test

.PHONY: docker-a11y-build-run
docker-a11y-build-run:
	docker compose -f docker-compose.yml -f docker-compose.a11y.yml -p a11y --profile a11y up --build --force-recreate --exit-code-from data-workspace-e2e-test

.PHONY: docker-a11y-start
docker-a11y-start:
	docker compose -f docker-compose.yml -f docker-compose.a11y.yml -p a11y --profile a11y up --build --force-recreate -d

.PHONY: docker-clean
docker-clean:
	docker compose --profile test -p data-workspace-test down -v

.PHONY: check-flake8
check-flake8:
	flake8 .

.PHONY: docker-check-migrations
docker-check-migrations:
	docker compose --profile test -p data-workspace-test run data-workspace-test sh -c "sleep 5 && django-admin makemigrations --check --dry-run --verbosity 3"

.PHONY: check-black
check-black:
	@black --version
	black --check .

.PHONY: check-pylint
check-pylint:
	 env PYTHONPATH=app python3 -m pylint.__main__ --rcfile .pylintrc --output-format=colorized dataworkspace/dataworkspace test

.PHONY: check
check: check-flake8 check-black check-pylint

.PHONY: docker-check
docker-check:
	docker compose run --rm data-workspace bash -c "cd /app && make check"

.PHONY: docker-format
docker-format: first-use
	docker compose run --rm data-workspace bash -c "cd /app && black ."

.PHONY: format
format:
	black .

.PHONY: dev-shell
dev-shell:
	docker compose run --rm data-workspace bash

.PHONY: save-requirements
save-requirements:
	docker compose run --rm data-workspace bash -c "cd /app && pip-compile requirements.in"
	docker compose run --rm data-workspace bash -c "cd /app && pip-compile requirements-dev.in"

.PHONY: docker-test-unit-local
docker-test-unit-local:
	TEST_DIR="$(TARGET)" ; \
	if [ -z "$$TEST_DIR" ]; \
		then TEST_DIR="/dataworkspace/dataworkspace"; \
 	fi; \
	docker compose --profile test -p data-workspace-test run data-workspace-test pytest $$TEST_DIR -x -v --disable-warnings --reuse-db

.PHONY: docker-test-shell-local
docker-test-shell-local:
	docker compose --profile test -p data-workspace-test run --rm data-workspace-test bash

.PHONY: docker-test-integration-local
docker-test-integration-local:
	TEST_DIR="$(TARGET)" ; \
	if [ -z "$$TEST_DIR" ]; \
		then TEST_DIR="/test"; \
 	fi; \
	docker compose --profile test -p data-workspace-test run --rm data-workspace-test bash -c "DJANGO_SETTINGS_MODULE=dataworkspace.settings.integration_tests pytest -x -v $$TEST_DIR --disable-warnings"

.PHONY: docker-test-local
docker-test-local: docker-test-unit-local docker-test-integration-local

.PHONY: logout
logout:
	docker compose exec data-workspace-redis bash -c "redis-cli --scan --pattern data_workspace* | xargs redis-cli unlink"

.PHONY: docker-test-sequential
docker-test-sequential:
	docker compose --profile test -p data-workspace-test stop
	docker compose --profile test -p data-workspace-test rm -f

	docker compose --profile test -p data-workspace-test up -d
	docker compose --profile test -p data-workspace-test run --rm data-workspace-test pytest /test/test_application.py -x -v
	docker compose --profile test -p data-workspace-test stop

	docker compose --profile test -p data-workspace-test up -d
	docker compose --profile test -p data-workspace-test run --rm data-workspace-test pytest /test/test_application_1.py -x -v
	docker compose --profile test -p data-workspace-test stop

	docker compose --profile test -p data-workspace-test up -d
	docker compose --profile test -p data-workspace-test run --rm data-workspace-test pytest /test/test_application_2.py -x -v
	docker compose --profile test -p data-workspace-test stop

	docker compose --profile test -p data-workspace-test up -d
	docker compose --profile test -p data-workspace-test run --rm data-workspace-test pytest /test/test_utils.py -x -v
	docker compose --profile test -p data-workspace-test stop

	docker compose --profile test -p data-workspace-test up -d
	docker compose --profile test -p data-workspace-test run --rm data-workspace-test pytest /test/selenium/test_explorer.py -x -v
	docker compose --profile test -p data-workspace-test stop

	docker compose --profile test -p data-workspace-test up -d
	docker compose --profile test -p data-workspace-test run --rm data-workspace-test pytest /test/selenium/test_request_data.py -x -v
	docker compose --profile test -p data-workspace-test stop
