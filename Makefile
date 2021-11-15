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
	@echo -e "$(COLOUR_YELLOW)make docker-test-unit$(COLOUR_NONE) : runs the unit tests in a container"
	@echo -e "$(COLOUR_YELLOW)make docker-test-integration$(COLOUR_NONE) : runs the integration tests in a container (10 minutes min)"


.PHONY: first-use
first-use:
	docker network create data-infrastructure-shared-network || true

.PHONY: up
up: first-use
	docker-compose -f docker-compose-dev.yml up


.PHONY: docker-build
docker-build:
	docker-compose -f docker-compose-test.yml build


.PHONY: docker-test-unit
docker-test-unit: docker-build
	docker-compose -f docker-compose-test.yml -p data-workspace-test run data-workspace-test pytest /dataworkspace/dataworkspace


.PHONY: docker-test-integration
docker-test-integration: docker-build
	docker-compose -f docker-compose-test.yml -p data-workspace-test run data-workspace-test pytest test/


.PHONY: docker-test
docker-test: docker-test-integration docker-test-unit


.PHONY: docker-clean
docker-clean:
	docker-compose -f docker-compose-test.yml -p data-workspace-test down -v

.PHONY: check-flake8
check-flake8:
	flake8 .

.PHONY: docker-check-migrations
docker-check-migrations:
	docker-compose -f docker-compose-test.yml -p data-workspace-test run data-workspace-test sh -c "sleep 5 && django-admin makemigrations --check --dry-run --verbosity 3"

.PHONY: check-black
check-black:
	black --exclude=venv --skip-string-normalization --check .

.PHONY: check-pylint
check-pylint:
	 env PYTHONPATH=app python3 -m pylint.__main__ --rcfile .pylintrc dataworkspace/dataworkspace test

.PHONY: check
check: check-flake8 check-black check-pylint

.PHONY: docker-format
docker-format:
	docker-compose -f docker-compose-dev.yml run --rm data-workspace bash -c "cd /app && black --exclude=venv --skip-string-normalization ."


.PHONY: format
format:
	black --exclude=venv --skip-string-normalization .

.PHONY: save-requirements
save-requirements:
	docker-compose -f docker-compose-dev.yml run --rm data-workspace bash -c "cd /app && pip-compile requirements.in"
	docker-compose -f docker-compose-dev.yml run --rm data-workspace bash -c "cd /app && pip-compile requirements-dev.in"

.PHONY: docker-test-unit-local
docker-test-unit-local:
	TEST_DIR="$(TARGET)" ; \
	if [ -z "$$TEST_DIR" ]; \
		then TEST_DIR="/dataworkspace/dataworkspace"; \
 	fi; \
	docker-compose -f docker-compose-test-local.yml -p data-workspace-test run data-workspace-test pytest $$TEST_DIR -x -v

.PHONY: docker-test-shell-local
docker-test-shell-local:
	docker-compose -f docker-compose-test-local.yml -p data-workspace-test run --rm data-workspace-test bash

.PHONY: docker-test-integration-local
docker-test-integration-local:
	TEST_DIR="$(TARGET)" ; \
	if [ -z "$$TEST_DIR" ]; \
		then TEST_DIR="/test"; \
 	fi; \
	docker-compose -f docker-compose-test-local.yml -p data-workspace-test run data-workspace-test pytest $$TEST_DIR

.PHONY: docker-test-local
docker-test-local: docker-test-unit-local docker-test-integration-local

.PHONY: docker-test-sequential
docker-test-sequential:
	docker-compose -f docker-compose-test-local.yml -p data-workspace-test stop
	docker-compose -f docker-compose-test-local.yml -p data-workspace-test rm -f

	docker-compose -f docker-compose-test-local.yml -p data-workspace-test up -d
	docker-compose -f docker-compose-test-local.yml -p data-workspace-test run --rm data-workspace-test pytest /test/test_application.py -x -v
	docker-compose -f docker-compose-test-local.yml -p data-workspace-test stop

	docker-compose -f docker-compose-test-local.yml -p data-workspace-test up -d
	docker-compose -f docker-compose-test-local.yml -p data-workspace-test run --rm data-workspace-test pytest /test/test_utils.py -x -v
	docker-compose -f docker-compose-test-local.yml -p data-workspace-test stop


	docker-compose -f docker-compose-test-local.yml -p data-workspace-test up -d
	docker-compose -f docker-compose-test-local.yml -p data-workspace-test run --rm data-workspace-test pytest /test/selenium/test_explorer.py -x -v
	docker-compose -f docker-compose-test-local.yml -p data-workspace-test stop

	docker-compose -f docker-compose-test-local.yml -p data-workspace-test up -d
	docker-compose -f docker-compose-test-local.yml -p data-workspace-test run --rm data-workspace-test pytest /test/selenium/test_request_data.py -x -v
	docker-compose -f docker-compose-test-local.yml -p data-workspace-test stop

