FROM alpine:3.8

ENV \
	LC_ALL=en_US.UTF-8 \
	LANG=en_US.UTF-8 \
	LANGUAGE=en_US.UTF-8

RUN \
	apk add --no-cache \
	    build-base=0.5-r1 \
	    python3-dev=3.6.9-r1 \
		python3=3.6.9-r1 && \
	python3 -m ensurepip && \
	pip3 install \
		aiohttp==3.6.2

COPY metrics.py /

CMD ["python3", "/metrics.py"]

RUN adduser -S metrics
USER metrics
