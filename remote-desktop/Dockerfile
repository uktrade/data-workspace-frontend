FROM debian:buster

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
		vim \
		gnupg \
		software-properties-common \
		wget && \
	wget -qO - https://qgis.org/downloads/qgis-2020.gpg.key | gpg --no-default-keyring --keyring gnupg-ring:/etc/apt/trusted.gpg.d/qgis-archive.gpg --import && \
	chmod a+r /etc/apt/trusted.gpg.d/qgis-archive.gpg && \
	add-apt-repository "deb https://qgis.org/ubuntu $(lsb_release -c -s) main" && \
	apt update && \
	apt install qgis qgis-plugin-grass -y && \
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

COPY passwd xstartup start.sh nginx.conf org.qgis.qgis.desktop /

ENV \
	USER=dw
USER dw

CMD ["/start.sh"]
