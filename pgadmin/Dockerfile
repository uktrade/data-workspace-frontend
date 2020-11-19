FROM dpage/pgadmin4:4.27

ENV \
	PGADMIN_LISTEN_ADDRESS=0.0.0.0 \
	PGADMIN_LISTEN_PORT=8888 \
	PGADMIN_DEFAULT_EMAIL=pgadmin4@pgadmin.org \
	PGADMIN_DEFAULT_PASSWORD=test

COPY pgadmin-config.py /pgadmin4/config_local.py
COPY start.sh /

USER root
RUN \
	usermod -u 4356 pgadmin && \
	groupmod -g 4357 pgadmin && \
	chmod +x /start.sh

ENTRYPOINT ["/start.sh"]
