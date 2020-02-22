FROM debian:buster-slim

RUN \
	apt-get update && \
	DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
		bzip2 \
		ca-certificates \
		nginx \
		procps \
		task-lxde-desktop \
		vnc4server \
		websockify \
		wget && \
	wget https://github.com/novnc/noVNC/archive/v1.1.0.tar.gz && \
	tar -zxvf v1.1.0.tar.gz && \
	rm -r -f v1.1.0.tar.gz && \
	apt-get clean && \
	rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY index.html /noVNC-1.1.0/index.html

RUN \
	addgroup --system --gid 4356 dw && \
	adduser --disabled-password --gecos '' --ingroup dw --uid 4357 dw && \
	touch /var/run/nginx.pid && \
	chown dw:dw /var/run/nginx.pid

COPY passwd xstartup start.sh nginx.conf /

ENV \
	USER=dw
USER dw

CMD ["/start.sh"]
