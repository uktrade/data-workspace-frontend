FROM alpine:3.10

ENV \
	LC_ALL=en_US.UTF-8 \
	LANG=en_US.UTF-8 \
	LANGUAGE=en_US.UTF-8 \
	TARGET_FILE=/etc/prometheus/files.json

RUN \
	PROMETHEUS_VERSION=2.10.0 && \
	apk add --no-cache \
		ca-certificates \
		parallel \
		python3 && \
	apk add --no-cache --virtual .build-deps \
		curl && \
	curl -LO https://github.com/prometheus/prometheus/releases/download/v${PROMETHEUS_VERSION}/prometheus-${PROMETHEUS_VERSION}.linux-amd64.tar.gz && \
	tar -xvzf prometheus-${PROMETHEUS_VERSION}.linux-amd64.tar.gz && \
	mkdir -p /prometheus /etc/prometheus && \
	cp prometheus-${PROMETHEUS_VERSION}.linux-amd64/promtool /usr/local/bin/ && \
	cp prometheus-${PROMETHEUS_VERSION}.linux-amd64/prometheus /usr/local/bin/ && \
	cp -R prometheus-${PROMETHEUS_VERSION}.linux-amd64/console_libraries/ /etc/prometheus/ && \
	cp -R prometheus-${PROMETHEUS_VERSION}.linux-amd64/consoles/ /etc/prometheus/ && \
	rm -rf prometheus-${PROMETHEUS_VERSION}.linux-amd64* && \
	adduser -s /bin/false -D -H prometheus && \
	chown -R prometheus:prometheus /prometheus && \
	apk del .build-deps && \
	pip3 install \
		lowhaio==0.0.78

COPY prometheus.yml /etc/prometheus/
COPY fetch_targets.py /
COPY start.sh /start.sh
RUN \
	echo '[]' > ${TARGET_FILE} && \
	chown prometheus:prometheus ${TARGET_FILE} && \
	chmod o+w ${TARGET_FILE}

ENTRYPOINT []
CMD ["/start.sh"]

USER prometheus
