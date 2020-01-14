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
        libexecinfo-dev=1.1-r0 \
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
    echo '  - https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/r/' >> /opt/conda/.condarc && \
    echo 'allow_other_channels: false' >> /opt/conda/.condarc && \
    echo 'auto_update_conda: false' >> /opt/conda/.condarc && \
    echo 'always_yes: true' >> /opt/conda/.condarc && \
    echo 'show_channel_urls: true' >> /opt/conda/.condarc && \
    conda install \
        'conda=4.5.11' \
        'font-ttf-dejavu-sans-mono==2.37' \
        'jupyterlab=0.35.5' \
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
    conda clean -tipsy && \
    apk del .build-deps && \
    chown -R jovyan $CONDA_DIR

# The R package tidyverse depends on fs, which needs automake 1.14, which is not supplied by apk
# https://github.com/r-lib/fs/issues/210, and automake 1.14 needs a version of Perl earlier than
# 5.22 https://github.com/easybuilders/easybuild-easyconfigs/issues/1822#issuecomment-311507178
# and odd numbers of Perl are development versions, so choosing the latest 5.20
RUN \
    apk add --no-cache --virtual .build-deps \
        wget=1.20.3-r0 && \
    wget https://www.cpan.org/src/5.0/perl-5.20.3.tar.gz && \
    echo "3524e3a76b71650ab2f794fd68e45c366ec375786d2ad2dca767da424bbb9b4a  perl-5.20.3.tar.gz" | sha256sum -c && \
    tar -zxvf perl-5.20.3.tar.gz && \
    cd perl-5.20.3 && \
    ./Configure -des && \
    make && \
    # make test && \
    make install && \
    cd .. && \
    rm -r -f perl-5.20.3 && \
    wget https://ftp.gnu.org/gnu/automake/automake-1.14.1.tar.gz && \
    echo "814c2333f350ce00034a1fe718e0e4239998ceea7b0aff67e9fd273ed6dfc23b  automake-1.14.1.tar.gz" | sha256sum -c && \
    tar -zxvf automake-1.14.1.tar.gz && \
    rm -r -f automake-1.14.1.tar.gz && \
    cd automake-1.14.1 && \
    ./configure && \
    make && \
    make install && \
    cd .. && \
    rm -r -f automake-1.14.1 && \
    apk del .build-deps

COPY jupyterlab_database_access /jupyterlab_database_access
COPY jupyterlab_template_notebooks /jupyterlab_template_notebooks

RUN \
    pip install jupyterlab_template_notebooks/server/ && \
    jupyter serverextension enable --system --python jupyterlab_template_notebooks && \
    jupyter labextension install \
        /jupyterlab_database_access \
        /jupyterlab_template_notebooks/browser && \
    npm cache clean --force && \
    node /opt/conda/lib/python3.7/site-packages/jupyterlab/staging/yarn.js cache clean

COPY jupyter_notebook_config.py /etc/jupyter/jupyter_notebook_config.py

RUN \
    echo 'local({' > /opt/conda/lib/R/etc/Rprofile.site && \
    echo '  r = getOption("repos")' >> /opt/conda/lib/R/etc/Rprofile.site && \
    echo '  r["CRAN"] = "https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/cran/"' >> /opt/conda/lib/R/etc/Rprofile.site && \
    echo '  options(repos = r)' >> /opt/conda/lib/R/etc/Rprofile.site && \
    echo '})' >> /opt/conda/lib/R/etc/Rprofile.site

RUN \
    Rscript -e 'install.packages(c("tidyverse", "xml2", "base64enc", "curl", "httr", "aws.ec2metadata"), clean=TRUE)' && \
    Rscript -e 'install.packages("aws.s3", repos = c("cloudyr" = "http://cloudyr.github.io/drat"), clean=TRUE)'

ENTRYPOINT ["tini", "-g", "--"]

USER jovyan

WORKDIR /home/jovyan
