FROM cypress/included:13.6.3 AS base

ENV DOCKERIZE_VERSION      v0.6.1

# Install common dependencies
RUN apt-get install -y \
    wget

# Install dockerize
RUN wget https://github.com/jwilder/dockerize/releases/download/$DOCKERIZE_VERSION/dockerize-linux-amd64-$DOCKERIZE_VERSION.tar.gz \
    && tar -C /usr/local/bin -xzvf dockerize-linux-amd64-$DOCKERIZE_VERSION.tar.gz \
    && rm dockerize-linux-amd64-$DOCKERIZE_VERSION.tar.gz

WORKDIR app

COPY ./cypress cypress
COPY ./cypress/package.json .
COPY ./cypress/cypress-reporter-config.json .

RUN npm install

FROM base AS e2e

COPY cypress.config.ts ./cypress.config.ts

FROM base AS a11y

COPY cypress.a11y.config.ts ./cypress.config.ts