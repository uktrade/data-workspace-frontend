FROM alpine:3.10

COPY requirements.txt /app/
RUN \
	apk add --no-cache \
		python3 && \
	pip3 install \
		-r /app/requirements.txt

RUN \
	apk add sudo && \
	addgroup -S -g 4356 s3sync && \
	adduser -S -u 4357 s3sync -G s3sync

COPY start.sh /

CMD ["/start.sh"]
