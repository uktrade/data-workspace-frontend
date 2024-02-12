FROM node:16-alpine AS builder
WORKDIR /app
# COPY dataworkspace/dataworkspace/static/js/TEST_FILE.txt bundles/TEST_FILE.txt
COPY dataworkspace/dataworkspace/static/js .
RUN npm ci --include=dev
RUN npm run build

# FROM node:16-alpine AS final
# WORKDIR /app
# COPY dataworkspace/dataworkspace/static/js .
# COPY --from=builder ./app/bundles ./bundles
# RUN npm ci --include=dev
# CMD [ "npm", "run", "dev" ]


FROM debian:bullseye-20220509-slim AS base

# # COPY --from=builder ./app/bundles ./dataworkspace/dataworkspace/static/js/bundles

# WORKDIR /dataworkspace/dataworkspace/static/js
# RUN ls
# WORKDIR /dataworkspace/dataworkspace/static/js/bundles
# RUN ls
# WORKDIR /

# ENV \
#     LC_ALL=en_US.UTF-8 \
#     LANG=en_US.UTF-8 \
#     LANGUAGE=en_US.UTF-8 \
#     PYTHONPATH=/dataworkspace \
#     DJANGO_SETTINGS_MODULE=dataworkspace.settings.base

# RUN apt-get update && \
#     apt-get update && \
#     apt-get install -y --no-install-recommends curl bzip2 make ca-certificates && \
#     curl https://ftp.gnu.org/gnu/parallel/parallel-20190522.tar.bz2 > parallel-20190522.tar.bz2 && \
#     tar xjf parallel-20190522.tar.bz2 && \
#     cd parallel-20190522 && \
#     ./configure && make && make install && \
#     cd / && \
#     rm -rf parallel-20190522 parallel-20190522.tar.bz2 && \
#     apt-get install -y --no-install-recommends \
#     locales \
#     git \
#     nginx \
#     nginx-extras \
#     openssl \
#     build-essential \
#     libpq-dev \
#     procps \
#     python3 \
#     python3-dev \
#     python3-pip \
#     python3-setuptools && \
#     echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen && \
#     locale-gen en_US.utf8 && \
#     rm /etc/nginx/nginx.conf && \
#     rm -rf /tmp/* && \
#     rm -rf /var/lib/apt/lists/* && \
#     useradd -m django && \
#     chown -R django /var/log/nginx

# COPY requirements.txt requirements.txt
# RUN python3 -m pip install --upgrade pip wheel pip-tools && \
#     python3 -m pip install -r requirements.txt

# WORKDIR /dataworkspace/dataworkspace/static/js
# RUN ls
# WORKDIR /dataworkspace/dataworkspace/static/js/bundles
# RUN ls
# WORKDIR /

# FROM base AS test

# WORKDIR /dataworkspace/dataworkspace/static/js
# RUN ls
# WORKDIR /dataworkspace/dataworkspace/static/js/bundles
# RUN ls
# WORKDIR /

# RUN apt-get update && \
#     apt-get install -y --no-install-recommends \
#     gcc \
#     musl-dev \
#     chromium \
#     chromium-driver \
#     libxml2-dev \
#     libxslt1-dev && \
#     echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen && \
#     locale-gen en_US.utf8 && \
#     rm -rf /tmp/* && \
#     rm -rf /var/lib/apt/lists/*

# COPY requirements-dev.txt requirements-dev.txt
# COPY setup.cfg setup.cfg

# RUN pip3 install -r requirements-dev.txt

# COPY dataworkspace /dataworkspace
# # # RUN rm -rf dataworkspace/dataworkspace/static/js/bundles
# # COPY --from=builder ./app/bundles/ ./dataworkspace/dataworkspace/static/js/bundles
# # COPY --from=builder ./app/bundles ./dataworkspace/dataworkspace/static/js/bundles1
# # COPY --from=builder ./app/bundles/ ./dataworkspace/dataworkspace/static/js/bundles2
# # COPY --from=builder ./app/bundles/ ./dataworkspace/dataworkspace/static/js/bundles3/
# # COPY --from=builder ./app/bundles /dataworkspace/dataworkspace/static/js/bundles4/

# # COPY --from=builder ./app/bundles dataworkspace/dataworkspace/static/js/bundles20/
# # COPY --from=builder ./app/bundles dataworkspace/dataworkspace/static/js/bundles21

# # COPY --from=builder ./app/bundles/ ./app/dataworkspace/dataworkspace/static/js/bundles1
# # COPY --from=builder ./app/bundles/ ./app/dataworkspace/dataworkspace/static/js/bundles2/
# # COPY --from=builder ./app/bundles ./app/dataworkspace/dataworkspace/static/js/bundles3
# # COPY --from=builder ./app/bundles ./app/dataworkspace/dataworkspace/static/js/bundles4/

# # COPY --from=builder ./app/bundles ./bundles1
# # COPY --from=builder ./app/bundles/ ./bundles2

# # # COPY ./bundles2 /dataworkspace/dataworkspace/static/js/bundles5/
# # # COPY bundles2 /dataworkspace/dataworkspace/static/js/bundles6/
# # # COPY ./bundles2 dataworkspace/dataworkspace/static/js/bundles7/
# # # COPY bundles2 dataworkspace/dataworkspace/static/js/bundles8/

# # # COPY ./bundles2 /dataworkspace/dataworkspace/static/js/bundles9
# # # COPY bundles2 /dataworkspace/dataworkspace/static/js/bundles10
# # # COPY ./bundles2 dataworkspace/dataworkspace/static/js/bundles11
# # # COPY bundles2 dataworkspace/dataworkspace/static/js/bundles12
# # # COPY --from=builder ./app/bundles .
# # # RUN ls
# # # WORKDIR /dataworkspace
# # # RUN ls
# # # WORKDIR /dataworkspace/dataworkspace/static/js
# # # RUN ls
# # # WORKDIR /dataworkspace/dataworkspace/static/js/bundles
# # # RUN ls
# # # WORKDIR /
# # # RUN cd dataworkspace

# COPY etc /etc
# RUN \
#     mkdir /test-results && \
#     chown -R django:django /test-results

# USER django

# COPY test /test

# WORKDIR /dataworkspace/dataworkspace/static/js
# RUN ls
# WORKDIR /dataworkspace/dataworkspace/static/js/bundles
# RUN ls
# WORKDIR /

# FROM test AS dev

# WORKDIR /dataworkspace/dataworkspace/static/js
# RUN ls
# WORKDIR /dataworkspace/dataworkspace/static/js/bundles
# RUN ls
# WORKDIR /

# # USER root

# # RUN apt-get update && \
# #     apt-get install -y --no-install-recommends nodejs npm && \
# #     rm -rf /tmp/* && \
# #     rm -rf /var/lib/apt/lists/*

# # RUN npm install --global --unsafe-perm nodemon
# # COPY --from=builder ./app/bundles/ ./dataworkspace
# # COPY --from=builder ./app/bundles/ ./dataworkspace/dataworkspace
# # COPY --from=builder ./app/bundles/ ./dataworkspace/dataworkspace/static
# # COPY --from=builder ./app/bundles/ ./dataworkspace/dataworkspace/static/js
# # COPY --from=builder ./app/bundles/ ./dataworkspace/dataworkspace/static/js/bundles

# # COPY --from=builder ./app/bundles/ ./app/dataworkspace/dataworkspace/static/js/bundles
# # USER django

# # CMD ["/dataworkspace/start-dev.sh"]

# # FROM dev AS e2e

# # CMD ["/dataworkspace/start-e2e.sh"]

# # FROM base AS live

# # COPY dataworkspace /dataworkspace

# # RUN cd dataworkspace

# # COPY etc /etc

# # CMD ["/dataworkspace/start.sh"]

# # USER django


#ORIGINAL

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
    libpq-dev \
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
RUN python3 -m pip install --upgrade pip wheel pip-tools && \
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
COPY setup.cfg setup.cfg
RUN pip3 install -r requirements-dev.txt

COPY dataworkspace /dataworkspace
COPY --from=builder ./app/bundles ./dataworkspace/dataworkspace/static/js/bundles

WORKDIR /dataworkspace/dataworkspace/static/js/bundles
RUN ls
WORKDIR /

COPY etc /etc
RUN \
    mkdir /test-results && \
    chown -R django:django /test-results

USER django

COPY test /test

FROM test AS dev

USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends nodejs npm && \
    rm -rf /tmp/* && \
    rm -rf /var/lib/apt/lists/*

RUN npm install --global --unsafe-perm nodemon

USER django

CMD ["/dataworkspace/start-dev.sh"]

FROM dev AS e2e

CMD ["/dataworkspace/start-e2e.sh"]

FROM base AS live

COPY dataworkspace /dataworkspace

# RUN cd dataworkspace

COPY etc /etc

CMD ["/dataworkspace/start.sh"]

USER django