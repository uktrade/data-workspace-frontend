FROM alpine:3.8

RUN apk --no-cache add \
	nginx==1.14.2-r0 \
	openssl=1.0.2r-r0 \
	tini=0.18.0-r0

COPY sentryproxy-entrypoint.sh /entrypoint.sh
COPY sentryproxy.conf /etc/nginx/nginx.conf

RUN \
	mkdir /run/nginx

CMD ["nginx"]
ENTRYPOINT ["/entrypoint.sh"]
