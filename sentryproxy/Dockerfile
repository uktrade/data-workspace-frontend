FROM alpine:3.10

RUN apk --no-cache add \
	nginx==1.16.1-r2 \
	openssl=1.1.1i-r0 \
	tini=0.18.0-r0

COPY sentryproxy-entrypoint.sh /entrypoint.sh
COPY sentryproxy.conf /etc/nginx/nginx.conf

RUN \
	mkdir /run/nginx

CMD ["nginx"]
ENTRYPOINT ["/entrypoint.sh"]
