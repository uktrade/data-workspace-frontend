FROM alpine:3.8

ENV \
	LC_ALL=en_US.UTF-8 \
	LANG=en_US.UTF-8 \
	LANGUAGE=en_US.UTF-8 \
	PYTHONPATH=/ \
	DJANGO_SETTINGS_MODULE=app.settings

RUN \
	apk add --no-cache \
		git=2.18.1-r0 \
		nginx=1.14.1-r0 \
		openssl=1.0.2q-r0 \
		py3-psycopg2=2.7.5-r0 \
		python3=3.6.6-r0 && \
	python3 -m ensurepip && \
	pip3 install \
		pip==18.00 && \
	pip3 install \
		gunicorn==19.9.0 \
		django==2.1.2 \
		-e git+https://github.com/uktrade/django-staff-sso-client.git@bb18f6838682973b542c8521d5801832227d5d95#egg=authbroker_client && \
	rm /etc/nginx/conf.d/default.conf && \
	rm /etc/nginx/nginx.conf && \
	apk del git

ADD app .

CMD ["/start.sh"]

RUN adduser -S django
USER django
