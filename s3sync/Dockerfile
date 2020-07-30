FROM quay.io/uktrade/mobius3:v0.0.33

COPY start.sh /

CMD ["/start.sh"]

USER root

RUN \
	apk add sudo && \
	addgroup -S -g 4356 s3sync && \
	adduser -S -u 4357 s3sync -G s3sync

# Must be created to ensure it has the correct user permissions
RUN mkdir /home/s3sync/data

WORKDIR /home/s3sync
