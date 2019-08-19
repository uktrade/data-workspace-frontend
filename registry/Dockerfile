FROM alpine:3.9

ENV \
	LC_ALL=en_US.UTF-8 \
	LANG=en_US.UTF-8 \
	LANGUAGE=en_US.UTF-8 \
	REGISTRY_HTTP_TLS_CERTIFICATE=/home/registry/ssl.crt \
	REGISTRY_HTTP_TLS_KEY=/home/registry/ssl.key \
	REGISTRY_HTTP_ADDR=0.0.0.0:5000

RUN \
	apk add --no-cache \
		ca-certificates=20190108-r0 \
		docker-registry=2.6.2-r0 \
		openssl=1.1.1b-r1 \
		tini=0.18.0-r0

RUN \
	adduser -S registry && \
	mkdir -p /var/lib/docker-registry && \
	chown registry /var/lib/docker-registry && \
	mkdir /etc/registry && \
	chown registry /etc/registry

COPY registry-entrypoint.sh /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["docker-registry", "serve", "/etc/docker-registry/config.yml"]

USER registry
