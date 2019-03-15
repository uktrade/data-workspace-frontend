FROM alpine:3.8

ENV \
	LC_ALL=en_US.UTF-8 \
	LANG=en_US.UTF-8 \
	LANGUAGE=en_US.UTF-8 \
	PYTHONPATH=/ \
	DJANGO_SETTINGS_MODULE=app.settings

RUN \
	apk add --no-cache --virtual .build-deps \
		build-base=0.5-r1 \
		git=2.18.1-r0 \
		python3-dev=3.6.6-r0 && \
	apk add --no-cache \
		nginx=1.14.2-r0 \
		openssl=1.0.2r-r0 \
		py3-psycopg2=2.7.5-r0 \
		python3=3.6.6-r0 && \
	python3 -m ensurepip && \
	pip3 install \
		pip==18.00 && \
	pip3 install \
		gunicorn[gevent]==19.9.0 \
		psycogreen==1.0.1 \
		django==2.1.2 \
		-e git+https://github.com/uktrade/django-staff-sso-client.git@bb18f6838682973b542c8521d5801832227d5d95#egg=authbroker_client \
		django-govuk-template==0.8 && \
	rm /etc/nginx/conf.d/default.conf && \
	rm /etc/nginx/nginx.conf && \
	apk del .build-deps

ADD app .

CMD ["/start.sh"]

RUN adduser -S django
USER django
