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


.PHONY: format
format:
	black --exclude=venv --skip-string-normalization .

.PHONY: save-requirements
save-requirements:
	pip-compile requirements.in
	pip-compile requirements-dev.in

.PHONY: docker-test-unit-local
docker-test-unit-local:
	docker-compose -f docker-compose-test-local.yml -p data-workspace-test run data-workspace-test pytest /dataworkspace/dataworkspace

.PHONY: docker-test-integration-local
docker-test-integration-local:
	docker-compose -f docker-compose-test-local.yml -p data-workspace-test run data-workspace-test pytest /test

.PHONY: docker-test-local
docker-test-local: docker-test-unit-local docker-test-integration-local
