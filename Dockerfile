FROM debian:buster-slim AS base

ENV \
	LC_ALL=en_US.UTF-8 \
	LANG=en_US.UTF-8 \
	LANGUAGE=en_US.UTF-8 \
	PYTHONPATH=/dataworkspace \
	DJANGO_SETTINGS_MODULE=dataworkspace.settings.base

RUN apt-get update && \
    apt-get update && \
    apt-get install -y --no-install-recommends curl bzip2 make ca-certificates && \
    curl https://ftp.gnu.org/gnu/parallel/parallel-20190522.tar.bz2 > parallel-20190522.tar.bz2 && \
    tar xjf parallel-20190522.tar.bz2 && \
    cd parallel-20190522 && \
    ./configure && make && make install && \
    cd / && \
    rm -rf parallel-20190522 parallel-20190522.tar.bz2 && \
    apt-get install -y --no-install-recommends \
        locales=2.28-10 \
        git=1:2.20.1-2+deb10u3 \
        nginx=1.14.2-2+deb10u4 \
        nginx-extras=1.14.2-2+deb10u4\
        openssl=1.1.1d-0+deb10u7 \
        build-essential=12.6 \
        procps=2:3.3.15-2 \
        python3=3.7.3-1 \
        python3-dev=3.7.3-1 \
        python3-pip=18.1-5 \
        python3-setuptools=40.8.0-1 && \
    echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen && \
    locale-gen en_US.utf8 && \
    rm /etc/nginx/nginx.conf && \
    rm -rf /tmp/* && \
    rm -rf /var/lib/apt/lists/* && \
    useradd -m django && \
    chown -R django /var/log/nginx

COPY requirements.txt requirements.txt
RUN python3 -m pip install --upgrade pip wheel && \
	python3 -m pip install -r requirements.txt

FROM base AS test

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc=4:8.3.0-1 \
        musl-dev=1.1.21-2 \
        chromium \
        chromium-driver \
        libxml2-dev=2.9.4+dfsg1-7+deb10u2 \
        libxslt1-dev=1.1.32-2.2~deb10u1 && \
    echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen && \
    locale-gen en_US.utf8 && \
    rm -rf /tmp/* && \
    rm -rf /var/lib/apt/lists/*

COPY requirements-dev.txt requirements-dev.txt
RUN pip3 install -r requirements-dev.txt

COPY dataworkspace /dataworkspace
RUN cd dataworkspace

COPY etc /etc

USER django

COPY test /test

FROM test as dev

USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends nodejs npm && \
    rm -rf /tmp/* && \
    rm -rf /var/lib/apt/lists/*

RUN npm install --global --unsafe-perm nodemon

USER django

CMD ["/dataworkspace/start-dev.sh"]

FROM base AS live

COPY dataworkspace /dataworkspace

RUN cd dataworkspace

COPY etc /etc

CMD ["/dataworkspace/start.sh"]

USER django
