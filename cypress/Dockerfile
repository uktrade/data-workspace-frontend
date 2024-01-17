FROM cypress/included:12.8.1

ENV DOCKERIZE_VERSION      v0.6.1

# Install common dependencies
RUN apt-get install -y \
    wget

# Install dockerize
RUN wget https://github.com/jwilder/dockerize/releases/download/$DOCKERIZE_VERSION/dockerize-linux-amd64-$DOCKERIZE_VERSION.tar.gz \
    && tar -C /usr/local/bin -xzvf dockerize-linux-amd64-$DOCKERIZE_VERSION.tar.gz \
    && rm dockerize-linux-amd64-$DOCKERIZE_VERSION.tar.gz

WORKDIR app
COPY . cypress
COPY ./package.json .
COPY ./cypress.config.ts .
RUN npm install