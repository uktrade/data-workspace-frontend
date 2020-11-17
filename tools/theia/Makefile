.PHONY: save-requirements
save-requirements:
	docker run -v $(shell pwd):/tmp/reqs python:3.7-slim bash -c "cd /tmp/reqs && pip install pip-tools && pip-compile requirements.in"
