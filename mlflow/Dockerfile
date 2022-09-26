FROM python:3.9-buster

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl bzip2 make ca-certificates && \
    curl https://ftp.gnu.org/gnu/parallel/parallel-20190522.tar.bz2 > parallel-20190522.tar.bz2 && \
    tar xjf parallel-20190522.tar.bz2 && \
    cd parallel-20190522 && \
    ./configure && make && make install && \
    cd / && \
    rm -rf parallel-20190522 parallel-20190522.tar.bz2


WORKDIR /app

COPY requirements-mlflow.txt .

RUN pip install -r requirements-mlflow.txt

COPY proxy.py .
COPY start.sh .

CMD ["/app/start.sh"]