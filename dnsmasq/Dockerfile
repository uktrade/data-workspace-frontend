FROM alpine:3.10

RUN apk --no-cache add \
	dnsmasq==2.80-r3 \
	python3=3.7.3-r0

COPY dnsmasq-set-dhcp.py /dnsmasq-set-dhcp.py
COPY dnsmasq-entrypoint.sh /entrypoint.sh

ENTRYPOINT ["sh"]
CMD ["entrypoint.sh"]
