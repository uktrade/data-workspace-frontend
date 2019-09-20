FROM rocker/rstudio:3.5.3

RUN \
	echo 'www-port=8888' >> /etc/rstudio/rserver.conf && \
	echo 'www-port=8888' >> /etc/rstudio/disable_auth_rserver.conf && \
	echo 'r-cran-repos=https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/cran/' >> /etc/rstudio/rsession.conf && \
	echo 'local({' >> /usr/local/lib/R/etc/Rprofile.site && \
	echo '  r = getOption("repos")' >> /usr/local/lib/R/etc/Rprofile.site && \
	echo '  r["CRAN"] = "https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/cran/"' >> /usr/local/lib/R/etc/Rprofile.site && \
	echo '  options(repos = r)' >> /usr/local/lib/R/etc/Rprofile.site && \
	echo '})' >> /usr/local/lib/R/etc/Rprofile.site

RUN \
	apt-get update && \
	apt-get install -y --no-install-recommends \
		libpq-dev \
		libxml2-dev \
		zlib1g-dev && \
	apt-get clean && \
	rm -rf /var/lib/apt/lists/ && \
	Rscript -e "install.packages('DBI'); install.packages('RPostgres'); install.packages('stringr');"

COPY exploretiva /exploretiva
RUN \
	Rscript -e 'install.packages("/exploretiva", repos=NULL, type="source")'

COPY rstudio-start.sh /
COPY rstudio-db-creds.py /
