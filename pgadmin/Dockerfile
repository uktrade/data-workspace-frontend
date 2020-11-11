FROM dpage/pgadmin4:4.27

ENV \
	PGADMIN_LISTEN_ADDRESS=0.0.0.0 \
	PGADMIN_LISTEN_PORT=8888 \
	PGADMIN_DEFAULT_EMAIL=pgadmin4@pgadmin.org \
	PGADMIN_DEFAULT_PASSWORD=test

COPY pgadmin-config.py /pgadmin4/config_local.py

USER root
RUN \
	touch /pgadmin4/.pgpass /pgadmin4/servers.json && \
	chown pgadmin:pgadmin /pgadmin4/.pgpass /pgadmin4/servers.json && \
	chown -R pgadmin:pgadmin /home/jovyan
USER pgadmin
