FROM debian:bullseye

RUN \
	# Try to disable ipv6 AAAA lookups, which our DNS rewrite proxy doesn't support
	# Not 100% sure that this really does have an effect
	echo "precedence ::ffff:0:0/96  100" >> /etc/gai.conf

RUN \
	apt update && \
	apt install -y sudo python3-pip && \
	apt autoremove -y && \
	apt autoclean -y && \
	rm -rf /tmp/* && \
	rm -rf /var/lib/apt/lists/*

RUN \
	addgroup --system --gid 4356 s3sync && \
	adduser --disabled-password --gecos '' --ingroup s3sync --uid 4357 s3sync

COPY requirements.txt /app/

RUN \
	pip3 install \
		-r /app/requirements.txt

COPY start.sh /

CMD ["/start.sh"]
