FROM debian:buster-slim AS base

RUN \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        locales && \
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
        build-essential \
        ca-certificates \
        libffi-dev \
        libldap2-dev \
        libsasl2-dev \
        libssl-dev \
        python3 \
        python3-dev \
        python3-pip

RUN adduser --disabled-password --gecos '' superset

COPY requirements.txt /

RUN \
    pip3 install --upgrade setuptools==57.5.0 pip && \
    pip3 install -r requirements.txt

ENV \
    PYTHONPATH=/etc/superset:$PYTHONPATH \
    FLASK_APP=superset

COPY superset_config.py /etc/superset/

COPY data-workspace-patches.js /usr/local/lib/python3.7/dist-packages/superset/static/assets/

RUN sed -i 's/<\/title>/<\/title><script src="\/static\/assets\/data-workspace-patches.js"><\/script>/g' \
    /usr/local/lib/python3.7/dist-packages/superset/templates/superset/basic.html

FROM base AS dev

COPY start-dev.sh /start.sh

USER superset

CMD ["/start.sh"]

FROM base as live

COPY start.sh /

USER superset

CMD ["/start.sh"]
