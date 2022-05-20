FROM debian:bullseye-20220509-slim AS base

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
        locales \
        git \
        nginx \
        nginx-extras \
        openssl \
        build-essential \
        procps \
        python3 \
        python3-dev \
        python3-pip \
        python3-setuptools && \
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
        gcc \
        musl-dev \
        chromium \
        chromium-driver \
        libxml2-dev \
        libxslt1-dev && \
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
