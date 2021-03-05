FROM alpine:3.10

RUN apk --no-cache add \
	python3=3.7.7-r2

RUN pip3 install \
	aiodnsresolver==0.0.151 \
	dnsrewriteproxy==0.0.13

COPY set-dhcp.py nameserver.py entrypoint.sh /

ENTRYPOINT ["sh"]
CMD ["entrypoint.sh"]
