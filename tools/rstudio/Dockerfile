FROM debian:buster

RUN \
	echo "deb http://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/debian/ buster main" > /etc/apt/sources.list && \
	echo "deb http://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/debian-security/ buster/updates main" >> /etc/apt/sources.list && \
	echo "deb http://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/debian/ buster-updates main" >> /etc/apt/sources.list && \
	echo "Acquire{Check-Valid-Until false; Retries 10;}" >> /etc/apt/apt.conf && \
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

COPY rstudio/exploretiva /exploretiva

RUN \
	apt-get update && \
	apt-get install -y --no-install-recommends \
		ca-certificates \
		dirmngr \
		gnupg2 && \
	echo "deb http://cran.ma.imperial.ac.uk/bin/linux/debian buster-cran35/" >> /etc/apt/sources.list && \
	until apt-key adv --keyserver pgp.mit.edu --recv-key 'E19F5F87128899B192B1A2C2AD5F960A256A04AF'; do sleep 10; done && \
	apt-get clean -y && \
	apt-get autoremove -y && \
	apt-get autoclean -y && \
	rm -rf /tmp/* && \
	rm -rf /var/lib/apt/lists/* && \
	apt-get update && \
	apt-get install -y --no-install-recommends \
		gdebi-core=0.9.5.7+nmu3 \
		gfortran=4:8.3.0-1 \
		git=1:2.20.1-2+deb10u3 \
		libgit2-dev=0.27.7+dfsg.1-0.2 \
		libgsl-dev=2.5+dfsg-6 \
		libxml2-dev \
		libpq-dev \
		libgdal-dev \
		lmodern=2.004.5-6 \
		procps=2:3.3.15-2 \
		r-base-dev=3.6.1-2~bustercran.0 \
		r-base=3.6.1-2~bustercran.0 \
		r-cran-base64enc=0.1-3-2 \
		r-cran-curl=3.3+dfsg-1 \
		r-cran-data.table=1.12.0+dfsg-1 \
		r-cran-dbi=1.0.0-2 \
		r-cran-httr=1.4.0-3 \
		r-cran-rpostgresql=0.6-2+dfsg-2 \
		r-cran-xml2=1.2.0-3 \
		r-recommended=3.6.1-2~bustercran.0 \
		ssh=1:7.9p1-10+deb10u2 \
		texlive=2018.20190227-2 \
		texlive-latex-extra=2018.20190227-2 \
		git-man=1:2.20.1-2+deb10u3 \
		man-db=2.8.5-2 \
                vim \
                emacs \
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
	# Remove the last line from sources: the CRAN debian repo that has R itself, which we don't mirror
	sed -i '$d' /etc/apt/sources.list && \
	echo 'www-port=8888' >> /etc/rstudio/rserver.conf && \
	echo 'auth-none=1' >> /etc/rstudio/rserver.conf && \
	echo 'server-daemonize=0' >> /etc/rstudio/rserver.conf && \
	echo 'local({' >> /usr/lib/R/etc/Rprofile.site && \
	echo '  r = getOption("repos")' >> /usr/lib/R/etc/Rprofile.site && \
	echo '  r["CRAN"] = "https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/cran-binary/"' >> /usr/lib/R/etc/Rprofile.site && \
	echo '  r["CRAN_1"] = "https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/cran/"' >> /usr/lib/R/etc/Rprofile.site && \
	echo '  options(repos = r)' >> /usr/lib/R/etc/Rprofile.site && \
	echo '})' >> /usr/lib/R/etc/Rprofile.site && \
	echo 'CRAN=https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/cran-binary/' >> /etc/rstudio/repos.conf && \
	echo 'CRAN_1=https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/cran/' >> /etc/rstudio/repos.conf && \
	echo 'session-timeout-minutes=0' >> /etc/rstudio/rsession.conf && \
	echo 'session-save-action-default=no' >> /etc/rstudio/rsession.conf && \
	Rscript -e 'install.packages("/exploretiva", repos=NULL, type="source")' && \
	Rscript -e 'install.packages(c("aws.s3", "aws.ec2metadata", "ggraph", "igraph", "RPostgres", "text2vec", "tidytext", "tm", "topicmodels", "widyr", "wordcloud2", "tidyverse"), repos="https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/cran-binary/", clean=TRUE)'

COPY rstudio/rstudio-start.sh /

ENV \
	USER=rstudio

RUN \
	addgroup --system --gid 4356 rstudio && \
	adduser --disabled-password --gecos '' --ingroup rstudio --uid 4357 rstudio && \
	chown -R rstudio:rstudio /usr/local/lib/R/site-library && \
	# Avoids errors when installing Java
	mkdir -p /usr/share/man/man1mkdir -p /usr/share/man/man1 && \
	echo "root ALL=(ALL:ALL) ALL" > /etc/sudoers && \
	echo "rstudio ALL=NOPASSWD:/usr/bin/apt,/usr/bin/apt-get,/usr/bin/R" >> /etc/sudoers && \
	echo 'PS1="\[\033[01;34m\]\w\[\033[00m\]\$ "' >> /etc/bash.bashrc && \
	rm /home/rstudio/.bashrc

CMD ["/rstudio-start.sh"]
