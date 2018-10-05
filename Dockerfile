FROM alpine:3.8

ENV \
	LC_ALL=en_US.UTF-8 \
	LANG=en_US.UTF-8 \
	LANGUAGE=en_US.UTF-8 \
	PYTHONPATH=/ \
	DJANGO_SETTINGS_MODULE=app.settings

RUN \
	apk add --no-cache \
		openssl=1.0.2p-r0 \
		python3=3.6.6-r0 && \
	python3 -m ensurepip && \
	pip3 install \
		pip==18.00 && \
	pip3 install \
		gunicorn==19.9.0 \
		django==2.1.2

ADD app .

CMD ["/start.sh"]

RUN adduser -S django
USER django
