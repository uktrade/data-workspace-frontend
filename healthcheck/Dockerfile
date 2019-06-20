FROM alpine:3.8

ENV \
	LC_ALL=en_US.UTF-8 \
	LANG=en_US.UTF-8 \
	LANGUAGE=en_US.UTF-8

RUN \
	apk add --no-cache \
		python3=3.6.8-r0 && \
	python3 -m ensurepip && \
	pip3 install \
		aiohttp==3.5.4

COPY healthcheck.py /

CMD ["python3", "/healthcheck.py"]

RUN adduser -S healthcheck
USER healthcheck
