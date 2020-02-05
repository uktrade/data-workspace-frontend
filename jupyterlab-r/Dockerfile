FROM debian:buster-slim

RUN \
    apt-get update && \
        apt-get install -y --no-install-recommends \
          locales=2.28-10 \
          build-essential=12.6 \
          gfortran=4:8.3.0-1 \
          git=1:2.20.1-2+deb10u1 \
          openssh-client=1:7.9p1-10+deb10u1 \
          texlive-xetex=2018.20190227-2 \
          texlive-generic-extra=2018.20190227-2 \
          texlive-fonts-recommended=2018.20190227-2 \
          wget=1.20.1-1.1 \
          r-cran-tidyverse=1.2.1-1 \
          ca-certificates && \
      echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen && \
      locale-gen en_US.utf8  && \
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

RUN \
    groupadd -g 4356 jovyan && \
    useradd -u 4357 jovyan -g jovyan -m && \
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
    chown -R jovyan $CONDA_DIR  && \
    pip install \
        pip==20.0.2 && \
    pip install \
        sentry-sdk==0.9.0

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
    echo '})' >> /opt/conda/lib/R/etc/Rprofile.site && \
    Rscript -e 'install.packages(c("tidyverse", "xml2", "base64enc", "curl", "httr", "aws.ec2metadata"), clean=TRUE)' && \
    Rscript -e 'install.packages("aws.s3", repos = c("cloudyr" = "http://cloudyr.github.io/drat"), clean=TRUE)' && \
    apt-get remove --purge -y \
      wget && \
    apt-get clean -y && \
  	apt-get autoremove -y && \
  	apt-get autoclean -y && \
  	rm -rf /tmp/* && \
  	rm -rf /var/lib/apt/lists/*


ENTRYPOINT ["tini", "-g", "--"]

USER jovyan

WORKDIR /home/jovyan

CMD ["/opt/conda/bin/jupyter", \
    "lab", \
    "--config=/etc/jupyter/jupyter_notebook_config.py", \
    "--NotebookApp.token=''", \
    "--NotebookApp.ip='0.0.0.0'", \
    "--NotebookApp.allow_remote_access=True", \
    "--NotebookApp.port=8888"]
