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
