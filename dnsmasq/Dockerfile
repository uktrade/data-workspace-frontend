FROM alpine:3.8

RUN apk --no-cache add \
	dnsmasq==2.79-r3 \
	python3=3.6.6-r0

COPY dnsmasq-set-dhcp.py /dnsmasq-set-dhcp.py
COPY dnsmasq-entrypoint.sh /entrypoint.sh

ENTRYPOINT ["sh"]
CMD ["entrypoint.sh"]
