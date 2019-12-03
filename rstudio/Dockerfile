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
	LANGUAGE=en_US.UTF-8

COPY exploretiva /exploretiva

RUN \
	apt-get update && \
	apt-get install -y --no-install-recommends \
		dirmngr \
		gnupg2 && \
	echo "deb http://cran.ma.imperial.ac.uk/bin/linux/debian buster-cran35/" >> /etc/apt/sources.list && \
	until apt-key adv --keyserver keys.gnupg.net --recv-key 'E19F5F87128899B192B1A2C2AD5F960A256A04AF'; do sleep 10; done && \
	rm -rf /tmp/* && \
	rm -rf /var/lib/apt/lists/* && \
	apt-get update && \
	apt-get install -y --no-install-recommends \
		gdebi-core=0.9.5.7+nmu3 \
		procps=2:3.3.15-2 \
		r-base=3.6.1-2~bustercran.0 \
		r-base-dev=3.6.1-2~bustercran.0 \
		r-cran-base64enc=0.1-3-2 \
		r-cran-curl=3.3+dfsg-1 \
		r-cran-dbi=1.0.0-2 \
		r-cran-rpostgresql=0.6-2+dfsg-2 \
		r-cran-stringr=1.4.0-1 \
		r-cran-tidyverse=1.2.1-1 \
		r-cran-xml2=1.2.0-3 \
		r-cran-httr=1.4.0-3 \
		r-recommended=3.6.1-2~bustercran.0 \
		wget=1.20.1-1.1 && \
	wget -q https://download2.rstudio.org/server/bionic/amd64/rstudio-server-1.2.5019-amd64.deb && \
	echo "bfea9b32c04b721d5d2fb29be510b4378d57a6cd6c8c0dc8390b8760a87341b3  rstudio-server-1.2.5019-amd64.deb" | sha256sum -c && \
	gdebi --non-interactive rstudio-server-1.2.5019-amd64.deb && \
	rm rstudio-server-1.2.5019-amd64.deb && \
	apt-get remove --purge -y \
		dirmngr \
		gdebi-core \
		gnupg2 \
		wget && \
	apt-get clean -y && \
	apt-get autoremove -y && \
	apt-get autoclean -y && \
	rm -rf /tmp/* && \
	rm -rf /var/lib/apt/lists/* && \
	echo 'www-port=8888' >> /etc/rstudio/rserver.conf && \
	echo 'auth-none=1' >> /etc/rstudio/rserver.conf && \
	echo 'server-daemonize=0' >> /etc/rstudio/rserver.conf && \
	echo 'r-cran-repos=https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/cran/' >> /etc/rstudio/rsession.conf && \
	echo 'local({' >> /usr/lib/R/etc/Rprofile.site && \
	echo '  r = getOption("repos")' >> /usr/lib/R/etc/Rprofile.site && \
	echo '  r["CRAN"] = "https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/cran/"' >> /usr/lib/R/etc/Rprofile.site && \
	echo '  options(repos = r)' >> /usr/lib/R/etc/Rprofile.site && \
	echo '})' >> /usr/lib/R/etc/Rprofile.site && \
	Rscript -e 'install.packages("/exploretiva", repos=NULL, type="source")' && \
	Rscript -e 'install.packages(c("aws.ec2metadata"), clean=TRUE)' && \
	Rscript -e 'install.packages("aws.s3", repos = c("cloudyr" = "http://cloudyr.github.io/drat"), clean=TRUE)'

COPY rstudio-start.sh /

ENV \
	USER=rstudio

RUN \
	addgroup --system --gid 4356 rstudio && \
	adduser --disabled-password --gecos '' --ingroup rstudio --uid 4357 rstudio && \
	mkdir -p /etc/rstudio/connections && \
	chown rstudio /etc/rstudio/connections && \
	chown -R rstudio:rstudio /usr/local/lib/R/site-library

USER rstudio

CMD ["/usr/lib/rstudio-server/bin/rserver"]
