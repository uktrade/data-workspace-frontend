FROM debian:buster

RUN \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        locales=2.28-10 && \
    echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen && \
    locale-gen en_US.utf8 && \
    apt-get clean -y && \
    apt-get autoremove -y && \
    apt-get autoclean -y && \
    rm -rf /tmp/* && \
    rm -rf /var/lib/apt/lists/*

ENV \
    LC_ALL=en_US.UTF-8 \
    LANG=en_US.UTF-8 \
    LANGUAGE=en_US.UTF-8 \
    LD_LIBRARY_PATH=/lib

RUN \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        dirmngr \
        gnupg2 \
        python3 \
        python3-pip \
        python3-dev \
        python3-setuptools \
        ssh \
        vim \
        emacs \
        wget && \
    echo "deb https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/debian/ buster main" > /etc/apt/sources.list && \
    echo "deb https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/debian/ buster-updates main" >> /etc/apt/sources.list && \
    echo "Acquire{Check-Valid-Until false; Retries 10;}" >> /etc/apt/apt.conf && \
    until apt-key adv --keyserver pgp.mit.edu --recv-key 'E19F5F87128899B192B1A2C2AD5F960A256A04AF'; do sleep 10; done && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential=12.6 \
        git=1:2.20.1-2+deb10u3 \
        git-man=1:2.20.1-2+deb10u3 \
        libxext6 \
        libxrender1 \
        openssl \
        openssh-client=1:7.9p1-10+deb10u2 \
        texlive-xetex=2018.20190227-2 \
        texlive-generic-extra=2018.20190227-2 \
        texlive-fonts-recommended=2018.20190227-2 \
        ttf-dejavu \
        sudo \
        man-db=2.8.5-2 \
        tini=0.18.0-1 && \
	update-alternatives --install /usr/bin/python python /usr/bin/python3 2 && \
	update-alternatives --install /usr/bin/python python /usr/bin/python2 1 && \
    groupadd -g 4356 jovyan && \
    useradd -u 4357 jovyan -g jovyan -m && \
    echo "root ALL=(ALL:ALL) ALL" > /etc/sudoers && \
    echo "jovyan ALL=NOPASSWD:/usr/local/bin/dw-install,/usr/bin/apt,/usr/bin/apt-get" >> /etc/sudoers && \
    wget -q -O - https://deb.nodesource.com/setup_14.x | bash  && \
    apt-get install -y nodejs && \
    apt-get remove --purge -y \
        wget && \
    apt-get clean -y && \
    apt-get autoremove -y && \
    apt-get autoclean -y && \
    rm -rf /tmp/* && \
    rm -rf /var/lib/apt/lists/* && \
    # Remove the last line from sources: the CRAN debian repo that has R itself, which we don't mirror
    sed -i '$d' /etc/apt/sources.list && \
    # Avoids errors when installing Java
    mkdir -p /usr/share/man/man1mkdir -p /usr/share/man/man1

COPY jupyterlab-python/jupyterlab_database_access /jupyterlab_database_access
COPY jupyterlab-python/jupyterlab_template_notebooks /jupyterlab_template_notebooks
COPY requirements.txt python-setup.sh /root/

RUN \
    /root/python-setup.sh && \
    python3 -m pip install jupyterlab_template_notebooks/server/ && \
    jupyter serverextension enable --system --python jupyterlab_template_notebooks && \
    jupyter labextension install \
        /jupyterlab_database_access \
        /jupyterlab_template_notebooks/browser \
        @jupyter-widgets/jupyterlab-manager@2.0 && \
    npm cache clean --force && \
    echo '[global]' > /etc/pip.conf && \
    echo 'index-url = https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/pypi/' >> /etc/pip.conf && \
    echo 'no-cache-dir = false' >> /etc/pip.conf && \
    chown -R jovyan:jovyan /usr/local

COPY jupyterlab-python/jupyter_notebook_config.py /etc/jupyter/jupyter_notebook_config.py

ENTRYPOINT ["tini", "-g", "--"]

WORKDIR /home/jovyan

# The ipython history database does not play well with mobius3, surfacing
# occasional errors like "attempt to write a readonly database", so we store
# it where mobius3 does not sync
ENV IPYTHONDIR=/tmp/ipython

ENV \
    JUPYTER_CONFIG_DIR=/home/jovyan/.jupyterlab_python \
    JUPYTER_DATA_DIR=/tmp/jupyterlab_python \
    JUPYTER_RUNTIME_DIR=/tmp/jupyterlab_python/runtime

# The home directory in Data Workspace is a volume that is empty by default,
# so there is no ~/.bashrc. We delete the one here to make testing locally
# more like production
RUN \
    echo 'PS1="\w\\\\$ \[$(tput sgr0)\]"' >> /etc/bash.bashrc && \
    rm /home/jovyan/.bashrc

COPY dw-install /usr/local/bin/dw-install
COPY jupyterlab-python/start.sh /

CMD ["/start.sh"]
