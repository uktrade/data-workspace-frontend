FROM python:3.7-slim-buster AS base

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        locales=2.28-10 \
        git=1:2.20.1-2+deb10u1 \
        nginx=1.14.2-2+deb10u1 \
        openssl=1.1.1d-0+deb10u2 \
        parallel=20161222-1.1 && \
    echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen && \
    locale-gen en_US.utf8 && \
    rm /etc/nginx/nginx.conf && \
    rm -rf /tmp/* && \
    rm -rf /var/lib/apt/lists/* && \
    useradd -m django

ENV LC_ALL=en_US.UTF-8 \
    LANG=en_US.UTF-8 \
    LANGUAGE=en_US.UTF-8 \
    PYTHONPATH=/dataworkspace \
    DJANGO_SETTINGS_MODULE=dataworkspace.settings.base

COPY requirements.txt requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt


# ===============
FROM base AS test

COPY requirements-dev.txt requirements-dev.txt
RUN pip3 install --no-cache-dir -r requirements-dev.txt

COPY dataworkspace /dataworkspace
COPY etc /etc

USER django

COPY test /test


# ===============
FROM base AS live

COPY dataworkspace /dataworkspace
COPY etc /etc

CMD ["/dataworkspace/start.sh"]

USER django
