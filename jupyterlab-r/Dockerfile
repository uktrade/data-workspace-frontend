FROM debian:buster-slim

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
    CONDA_DIR=/opt/conda \
    LD_LIBRARY_PATH=/lib

ENV \
    PATH="$CONDA_DIR/bin:$PATH"

# Allow man pages to be installed: slim has hacks to exclude them, so we
# hack the hacks https://unix.stackexchange.com/a/480460/361685
RUN \
    sed -i '/path-exclude \/usr\/share\/man/d' /etc/dpkg/dpkg.cfg.d/docker && \
    sed -i '/path-exclude \/usr\/share\/groff/d' /etc/dpkg/dpkg.cfg.d/docker

RUN \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        dirmngr \
        gnupg2 \
        ssh && \
    echo "deb https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/debian/ buster main" > /etc/apt/sources.list && \
    echo "deb https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/debian/ buster-updates main" >> /etc/apt/sources.list && \
    echo "deb http://cran.ma.imperial.ac.uk/bin/linux/debian buster-cran35/" >> /etc/apt/sources.list && \
    until apt-key adv --keyserver keys.gnupg.net --recv-key 'E19F5F87128899B192B1A2C2AD5F960A256A04AF'; do sleep 10; done && \
    apt-get -o Acquire::Check-Valid-Until=false -o Acquire::Retries=10 update && \
    apt-get -o Acquire::Check-Valid-Until=false -o Acquire::Retries=10 install -y --no-install-recommends \
        build-essential=12.6 \
        gfortran=4:8.3.0-1 \
        git=1:2.20.1-2+deb10u3 \
        git-man=1:2.20.1-2+deb10u3 \
        man-db=2.8.5-2 \
        openssh-client=1:7.9p1-10+deb10u2 \
        texlive-xetex=2018.20190227-2 \
        texlive-generic-extra=2018.20190227-2 \
        texlive-fonts-recommended=2018.20190227-2 \
        wget=1.20.1-1.1 \
        r-cran-tidyverse=1.2.1-1 \
        sudo=1.8.27-1+deb10u2 \
        ca-certificates && \
    apt-get clean -y && \
        apt-get autoremove -y && \
        apt-get autoclean -y && \
        rm -rf /tmp/* && \
        rm -rf /var/lib/apt/lists/* && \
    groupadd -g 4356 jovyan && \
    useradd -u 4357 jovyan -g jovyan -m && \
    echo "root ALL=(ALL:ALL) ALL" > /etc/sudoers && \
    echo "jovyan ALL=NOPASSWD:/usr/bin/apt,/usr/bin/apt-get" >> /etc/sudoers && \
    wget https://repo.continuum.io/miniconda/Miniconda3-py37_4.8.2-Linux-x86_64.sh -O miniconda.sh && \
    echo "87e77f097f6ebb5127c77662dfc3165e  miniconda.sh" | md5sum -c && \
    mkdir -p "$CONDA_DIR" && \
    bash miniconda.sh -f -b -p "$CONDA_DIR" && \
    rm miniconda.sh && \
    echo 'channels:' > /opt/conda/.condarc && \
    echo '  - https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/conda-forge/' >> /opt/conda/.condarc && \
    echo '  - https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/anaconda/' >> /opt/conda/.condarc && \
    echo '  - https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/r/' >> /opt/conda/.condarc && \
    echo 'allow_other_channels: false' >> /opt/conda/.condarc && \
    echo 'auto_update_conda: false' >> /opt/conda/.condarc && \
    echo 'always_yes: true' >> /opt/conda/.condarc && \
    echo 'show_channel_urls: true' >> /opt/conda/.condarc && \
    conda install \
        'conda=4.8.2' \
        'font-ttf-dejavu-sans-mono==2.37' \
        'jupyterlab=2.0.0' \
        'nodejs=11.14.0' \
        'notebook=5.7.8' \
        'openssl=1.0.2p' \
        'r-base=3.4.1' \
        'r-cairo=1.5_9' \
        'r-dbi=1.0.0' \
        'r-dplyr' \
        'r-ggplot2=3.1.0' \
        'r-irkernel=0.8.12' \
        'r-openxlsx=4.1.0' \
        'r-plyr=1.8.4' \
        'r-readxl' \
        'r-rpostgres=1.1.1' \
        'r-stringr=1.3.1' \
        'r-tidyr' \
        'tini=0.18.0' \
        'tornado=5.1.1' \
        'xorg-libxext=1.3.3' \
        'xorg-libxrender=0.9.10' && \
    jupyter kernelspec uninstall python3 -f && \
    rm -r -f /opt/conda/lib/python3.7/site-packages/ipykernel && \
    conda clean -tipy && \
    chown -R jovyan $CONDA_DIR  && \
    pip install \
        pip==20.0.2 && \
    pip install \
        sentry-sdk==0.9.0 && \
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

COPY jupyterlab_database_access /jupyterlab_database_access
COPY jupyterlab_template_notebooks /jupyterlab_template_notebooks

RUN \
    pip install jupyterlab_template_notebooks/server/ && \
    jupyter serverextension enable --system --python jupyterlab_template_notebooks && \
    jupyter labextension install \
        /jupyterlab_database_access \
        /jupyterlab_template_notebooks/browser && \
    npm cache clean --force && \
    node /opt/conda/lib/python3.7/site-packages/jupyterlab/staging/yarn.js cache clean && \
    echo 'local({' > /opt/conda/lib/R/etc/Rprofile.site && \
    echo '  r = getOption("repos")' >> /opt/conda/lib/R/etc/Rprofile.site && \
    echo '  r["CRAN"] = "https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/cran/"' >> /opt/conda/lib/R/etc/Rprofile.site && \
    echo '  options(repos = r)' >> /opt/conda/lib/R/etc/Rprofile.site && \
    echo '})' >> /opt/conda/lib/R/etc/Rprofile.site && \
    Rscript -e 'install.packages(c("tidyverse", "xml2", "base64enc", "curl", "httr", "aws.ec2metadata"), clean=TRUE)' && \
    Rscript -e 'install.packages("aws.s3", repos = c("cloudyr" = "http://cloudyr.github.io/drat"), clean=TRUE)'

COPY jupyter_notebook_config.py /etc/jupyter/jupyter_notebook_config.py

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

COPY start.sh /start.sh

CMD ["/start.sh"]
