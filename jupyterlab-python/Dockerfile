FROM alpine:3.8

ENV \
    LC_ALL=en_US.UTF-8 \
    LANG=en_US.UTF-8 \
    LANGUAGE=en_US.UTF-8 \
    CONDA_DIR=/opt/conda \
    LD_LIBRARY_PATH=/lib

ENV \
    PATH="$CONDA_DIR/bin:$PATH"

# Must be the same as the s3sync user in the s3sync container so it
# can modify files
RUN \
    addgroup -S -g 4356 jovyan && \
    adduser -S -u 4357 jovyan -G jovyan

RUN \
    apk add --no-cache \
        bash=4.4.19-r1 \
        autoconf=2.69-r2 \
        build-base=0.5-r1 \
        gfortran=6.4.0-r9 \
        git=2.18.2-r0 \
        linux-headers=4.4.6-r2 \
        texlive-xetex=20170524-r5 \
        texmf-dist-latexextra=2017.46770-r0 && \
    apk add --no-cache --virtual .build-deps \
        wget=1.20.3-r0 && \
    wget https://alpine-pkgs.sgerrand.com/sgerrand.rsa.pub -O /etc/apk/keys/sgerrand.rsa.pub && \
    echo "8d6f142f06af51fa5533245d48f2248f  /etc/apk/keys/sgerrand.rsa.pub" | md5sum -c && \
    wget https://github.com/sgerrand/alpine-pkg-glibc/releases/download/2.28-r0/glibc-2.28-r0.apk && \
    echo "e1107610a518b879adeb39a2d4b2385e  glibc-2.28-r0.apk" | md5sum -c && \
    apk add --no-cache \
        glibc-2.28-r0.apk && \
    rm /etc/apk/keys/sgerrand.rsa.pub && \
    rm glibc-2.28-r0.apk && \
    wget http://repo.continuum.io/miniconda/Miniconda3-4.5.11-Linux-x86_64.sh -O miniconda.sh && \
    echo "e1045ee415162f944b6aebfe560b8fee  miniconda.sh" | md5sum -c && \
    mkdir -p "$CONDA_DIR" && \
    bash miniconda.sh -f -b -p "$CONDA_DIR" && \
    rm miniconda.sh && \
    echo 'channels:' > /opt/conda/.condarc && \
    echo '  - https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/conda-forge/' >> /opt/conda/.condarc && \
    echo '  - https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/anaconda/' >> /opt/conda/.condarc && \
    echo 'allow_other_channels: false' >> /opt/conda/.condarc && \
    echo 'auto_update_conda: false' >> /opt/conda/.condarc && \
    echo 'always_yes: true' >> /opt/conda/.condarc && \
    echo 'show_channel_urls: true' >> /opt/conda/.condarc && \
    conda install \
        'bokeh=0.13.0' \
        'conda=4.5.11' \
        'font-ttf-dejavu-sans-mono==2.37' \
        'gensim=3.5.0' \
        'ipympl=0.2.1' \
        'ipython-sql=0.3.9' \
        'ipython=6.5.0' \
        'jupyterlab=0.35.5' \
        'matplotlib=3.0.0' \
        'nltk=3.3.0' \
        'nodejs=11.14.0' \
        'notebook=5.7.8' \
        'numpy=1.17.2' \
        'openssl=1.0.2p' \
        'pandas=0.23.4' \
        'psycopg2=2.7.5' \
        'scipy=1.3.1' \
        'scikit-learn=0.21.3' \
        'seaborn=0.9.0' \
        'spacy=2.1.8' \
        'tini=0.18.0' \
        'tornado=5.1.1' \
        'xorg-libxext=1.3.3' \
        'xorg-libxrender=0.9.10' && \
    conda clean -tipsy && \
    pip install \
        pip==19.2.3 && \
    pip install \
        aiocontextvars==0.2.2 \
        sentry-sdk==0.9.0 && \
    apk del .build-deps && \
    chown -R jovyan $CONDA_DIR

RUN \
    python -m spacy download en && \
    python -m nltk.downloader -d /usr/local/share/nltk_data wordnet stopwords gutenberg

COPY jupyterlab_database_access /jupyterlab_database_access
COPY jupyterlab_template_notebooks /jupyterlab_template_notebooks

RUN \
    pip install jupyterlab_template_notebooks/server/ && \
    jupyter serverextension enable --system --python jupyterlab_template_notebooks && \
    jupyter labextension install \
        /jupyterlab_database_access \
        /jupyterlab_template_notebooks/browser \
        @jupyter-widgets/jupyterlab-manager \
        jupyter-matplotlib && \
    npm cache clean --force && \
    node /opt/conda/lib/python3.7/site-packages/jupyterlab/staging/yarn.js cache clean

COPY jupyter_notebook_config.py /etc/jupyter/jupyter_notebook_config.py

RUN \
    echo '[global]' > /etc/pip.conf && \
    echo 'index-url = https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/pypi/' >> /etc/pip.conf

ENTRYPOINT ["tini", "-g", "--"]

USER jovyan

WORKDIR /home/jovyan
