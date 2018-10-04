FROM alpine:3.8

ENV \
	LC_ALL=en_US.UTF-8 \
	LANG=en_US.UTF-8 \
	LANGUAGE=en_US.UTF-8

RUN \
	apk add --no-cache \
		python3=3.6.6-r0 && \
	python3 -m ensurepip && \
	pip3 install \
		pip==18.00 && \
	pip3 install \
		gunicorn==19.9.0 \
		django==2.1.2

ADD app .

CMD ["gunicorn", "app.wsgi:application", "-c", "gunicorn_config.py"]

RUN adduser -S django
USER django
