FROM alpine:3.8

ENV \
	LC_ALL=en_US.UTF-8 \
	LANG=en_US.UTF-8 \
	LANGUAGE=en_US.UTF-8

RUN \
	apk add --no-cache \
		python3=3.6.9-r1 && \
	python3 -m ensurepip && \
	pip3 install pip==18.01 && \
	pip3 install \
		beautifulsoup4==4.7.1 \
		lowhaio==0.0.87 \
		lowhaio_redirect==0.0.1

COPY mirrors-sync.py /
CMD ["python3", "mirrors-sync.py"]

RUN adduser -S mirrors-sync
USER mirrors-sync
