FROM alpine:3.10
ENV PGWEB_VERSION 0.11.4

RUN \
	apk update && \
	apk add --no-cache \
		ca-certificates \
		openssl \
		postgresql \
		python3 \
		wget && \
	update-ca-certificates && \
	rm -rf /var/cache/apk/* && \
	cd /tmp && \
	wget -q https://github.com/sosedoff/pgweb/releases/download/v$PGWEB_VERSION/pgweb_linux_amd64.zip && \
	unzip pgweb_linux_amd64.zip -d /usr/bin && \
	mv /usr/bin/pgweb_linux_amd64 /usr/bin/pgweb && \
	rm -f pgweb_linux_amd64.zip

COPY pgweb-config.py start.sh /

CMD ["/start.sh"]
