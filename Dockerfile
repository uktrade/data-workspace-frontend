FROM alpine:3.10

ENV \
	LC_ALL=en_US.UTF-8 \
	LANG=en_US.UTF-8 \
	LANGUAGE=en_US.UTF-8 \
	PYTHONPATH=/dataworkspace \
	DJANGO_SETTINGS_MODULE=dataworkspace.settings.prod

COPY requirements.txt requirements.txt

RUN \
	apk add --no-cache --virtual .build-deps \
		git=2.22.0-r0 && \
	apk add --no-cache \
		build-base=0.5-r1 \
		python3-dev=3.7.5-r1 \
		nginx=1.16.1-r1 \
		openssl=1.1.1d-r0 \
		parallel=20190522-r0 \
		py3-gevent==1.3.4-r2 \
		py3-psycopg2=2.7.7-r1 \
		python3=3.7.5-r1 && \
	python3 -m ensurepip && \
	pip3 install -r requirements.txt && \
	rm /etc/nginx/conf.d/default.conf && \
	rm /etc/nginx/nginx.conf && \
	apk del .build-deps

COPY dataworkspace /dataworkspace
COPY etc /etc

CMD ["/dataworkspace/start.sh"]

RUN adduser -S django
USER django
