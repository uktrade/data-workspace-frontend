FROM debian:buster-slim

RUN \
	apt-get update && \
	apt-get install -y --no-install-recommends \
		locales=2.28-10 && \
	echo "en_GB.UTF-8 UTF-8" >> /etc/locale.gen && \
	locale-gen en_GB.utf8 && \
	rm -rf /var/lib/apt/lists/*

ENV \
	LC_ALL=en_GB.UTF-8 \
	LANG=en_GB.UTF-8 \
	LANGUAGE=en_GB.UTF-8

RUN \
	apt-get update && \
	apt-get install -y --no-install-recommends \
		ca-certificates \
		dirmngr \
		gnupg2 && \
	rm -rf /var/lib/apt/lists/* && \
	echo "deb https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/debian/ buster main" > /etc/apt/sources.list && \
	echo "deb https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/debian/ buster-updates main" >> /etc/apt/sources.list && \
	echo "Acquire{Check-Valid-Until false; Retries 10;}" >> /etc/apt/apt.conf
