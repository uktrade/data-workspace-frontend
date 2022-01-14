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
		vim \
		gnupg \
		software-properties-common \
		gzip \
		gretl \
		wget && \
	wget -qO - https://qgis.org/downloads/qgis-2021.gpg.key | gpg --no-default-keyring --keyring gnupg-ring:/etc/apt/trusted.gpg.d/qgis-archive.gpg --import && \
	chmod a+r /etc/apt/trusted.gpg.d/qgis-archive.gpg && \
	add-apt-repository "deb https://qgis.org/ubuntu $(lsb_release -c -s) main" && \
	apt update && \
	apt install qgis qgis-plugin-grass -y && \
	apt-get clean && \
	rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN \
	wget https://github.com/novnc/websockify/archive/refs/tags/v0.9.0.tar.gz && \
	tar -zxvf v0.9.0.tar.gz && \
	cd websockify-0.9.0 && \
	python3 setup.py install && \
	cd .. && \
	rm -r -f v0.9.0.tar.gz

COPY index.html /webroot/index.html

RUN gzip -c /webroot/index.html > /webroot/index.html.gz

RUN \
	addgroup --system --gid 4356 dw && \
	adduser --disabled-password --gecos '' --ingroup dw --uid 4357 dw && \
	touch /var/run/nginx.pid && \
	chown dw:dw /var/run/nginx.pid

COPY start.sh nginx.conf org.qgis.qgis.desktop gretl.desktop /

ENV \
	USER=dw
USER dw

CMD ["/start.sh"]
