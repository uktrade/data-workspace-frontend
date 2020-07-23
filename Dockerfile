FROM alpine:3.10 AS base

ENV \
	LC_ALL=en_US.UTF-8 \
	LANG=en_US.UTF-8 \
	LANGUAGE=en_US.UTF-8 \
	PYTHONPATH=/dataworkspace \
	DJANGO_SETTINGS_MODULE=dataworkspace.settings.base

COPY requirements.txt requirements.txt

RUN \
	apk add --no-cache --virtual .build-deps \
		build-base=0.5-r1 \
		git=2.22.4-r0 \
		python3-dev=3.7.7-r1 \
		libffi-dev=3.2.1-r6 \
		openssl-dev=1.1.1g-r0 \
		linux-headers=4.19.36-r0 && \
	apk add --no-cache \
		nginx=1.16.1-r2 \
		nginx-mod-http-headers-more=1.16.1-r2 \
		openssl=1.1.1g-r0 \
		parallel=20190522-r0 \
		py3-psycopg2=2.7.7-r1 \
		python3=3.7.7-r1 && \
	rm /etc/nginx/conf.d/default.conf && \
	rm /etc/nginx/nginx.conf && \
	python3 -m ensurepip && \
	pip3 install -r requirements.txt && \
	apk del .build-deps && \
	adduser -S django

FROM base AS test

RUN apk add --no-cache \
        gcc \
        musl-dev \
        postgresql-dev \
        python3-dev

COPY requirements-dev.txt requirements-dev.txt
RUN pip3 install -r requirements-dev.txt

COPY dataworkspace /dataworkspace
COPY etc /etc

USER django

COPY test /test


FROM base AS live

COPY dataworkspace /dataworkspace
COPY etc /etc

CMD ["/dataworkspace/start.sh"]

USER django
