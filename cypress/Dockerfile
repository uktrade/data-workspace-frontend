FROM cypress/included:13.6.3

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
COPY cypress.config.ts .

RUN npm install
