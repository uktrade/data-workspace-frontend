SHELL := /bin/bash
APPLICATION_NAME="uktrade / data-workspace / Superset"
APPLICATION_VERSION=1.0

# Colour coding for output
COLOUR_NONE=\033[0m
COLOUR_GREEN=\033[1;36m
COLOUR_YELLOW=\033[33;01m

.PHONY: help test
help:
	@echo -e "$(COLOUR_GREEN)|--- $(APPLICATION_NAME) [$(APPLICATION_VERSION)] ---|$(COLOUR_NONE)"
	@echo -e "$(COLOUR_YELLOW)make requirements$(COLOUR_NONE): update requirements using pip-compile"

.PHONY: requirements
requirements:
	docker run --rm -it -v "$(PWD):/app"  python:3.9.10 bash

