FROM alpine:3.10

ENV \
	LC_ALL=en_US.UTF-8 \
	LANG=en_US.UTF-8 \
	LANGUAGE=en_US.UTF-8 \
	PYTHONPATH=/dataworkspace \
	DJANGO_SETTINGS_MODULE=dataworkspace.settings.prod

RUN \
	apk add --no-cache --virtual .build-deps \
		build-base=0.5-r1 \
		git=2.22.0-r0 \
		python3-dev=3.7.4-r0 && \
	apk add --no-cache \
		nginx=1.16.1-r0 \
		openssl=1.1.1d-r0 \
		parallel=20190522-r0 \
		py3-gevent==1.3.4-r2 \
		py3-psycopg2=2.7.7-r1 \
		python3=3.7.4-r0 && \
	python3 -m ensurepip && \
	pip3 install \
		# Not the latest due to https://github.com/aio-libs/aiohttp/issues/3700
		aiohttp==3.4.4 \
		aioredis==1.2.0 \
		boto3==1.9.123 \
		celery==4.3.0 \
		celery-redbeat==0.13.0 \
		gunicorn[gevent]==19.9.0 \
		psycogreen==1.0.1 \
		django==2.2.4 \
		django-db-geventpool==3.1.0 \
		django-redis==4.10.0 \
		zenpy==2.0.12 \
		requests==2.21.0 \
		django-admin-sortable2==0.7.3 \
		sentry-sdk==0.11.2 && \
	rm /etc/nginx/conf.d/default.conf && \
	rm /etc/nginx/nginx.conf && \
	apk del .build-deps

COPY dataworkspace /dataworkspace
COPY etc /etc

CMD ["/dataworkspace/start.sh"]

RUN adduser -S django
USER django
