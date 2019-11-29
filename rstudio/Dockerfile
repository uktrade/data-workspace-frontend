FROM debian:stretch-slim

RUN \
	apt-get update && \
	apt-get install -y --no-install-recommends \
		locales=2.24-11+deb9u4 && \
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

RUN \
	apt-get update && \
	apt-get install -y --no-install-recommends \
		dirmngr \
		gnupg2 && \
	echo "deb http://cran.ma.imperial.ac.uk/bin/linux/debian stretch-cran35/" >> /etc/apt/sources.list && \
	until apt-key adv --keyserver keys.gnupg.net --recv-key 'E19F5F87128899B192B1A2C2AD5F960A256A04AF'; do sleep 10; done && \
	rm -rf /tmp/* && \
	rm -rf /var/lib/apt/lists/* && \
	apt-get update && \
	apt-get install -y --no-install-recommends \
		gdebi-core=0.9.5.7+nmu1 \
		libatlas3-base=3.10.3-1+b1 \
		libcurl4-openssl-dev=7.52.1-5+deb9u9 \
		libopenblas-base=0.2.19-3 \
		libpq-dev=9.6.15-0+deb9u1 \
		libssl-dev=1.1.0l-1~deb9u1 \
		libssl1.1=1.1.0l-1~deb9u1 \
		libxml2-dev=2.9.4+dfsg1-2.2+deb9u2 \
		locales=2.24-11+deb9u4 \
		python3=3.5.3-1 \
		r-base-dev=3.6.1-2~stretchcran.0 \
		r-base=3.6.1-2~stretchcran.0 \
		r-recommended=3.6.1-2~stretchcran.0 \
		wget=1.18-5+deb9u3 \
		zlib1g-dev=1:1.2.8.dfsg-5 && \
	wget -q https://download2.rstudio.org/server/debian9/x86_64/rstudio-server-1.2.5001-amd64.deb && \
	echo "1ab303ea1db701a94f2afb2605c1bd501920944e9da1608b6fa1f2cc3a9a3e41  rstudio-server-1.2.5001-amd64.deb" | sha256sum -c && \
	gdebi --non-interactive rstudio-server-1.2.5001-amd64.deb && \
	rm rstudio-server-1.2.5001-amd64.deb && \
	apt-get remove --purge -y \
		dirmngr \
		gdebi-core \
		gnupg2 \
		wget && \
	apt-get clean -y && \
	apt-get autoremove -y && \
	apt-get autoclean -y && \
	rm -rf /tmp/* && \
	rm -rf /var/lib/apt/lists/*

RUN \
	echo 'www-port=8888' >> /etc/rstudio/rserver.conf && \
	echo 'auth-none=1' >> /etc/rstudio/rserver.conf && \
	echo 'server-daemonize=0' >> /etc/rstudio/rserver.conf && \
	echo 'r-cran-repos=https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/cran/' >> /etc/rstudio/rsession.conf && \
	echo 'local({' >> /usr/lib/R/etc/Rprofile.site && \
	echo '  r = getOption("repos")' >> /usr/lib/R/etc/Rprofile.site && \
	echo '  r["CRAN"] = "https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/cran/"' >> /usr/lib/R/etc/Rprofile.site && \
	echo '  options(repos = r)' >> /usr/lib/R/etc/Rprofile.site && \
	echo '})' >> /usr/lib/R/etc/Rprofile.site

COPY rstudio-start.sh /
COPY rstudio-db-creds.py /

ENV \
	USER=rstudio

RUN \
	addgroup --system --gid 4356 rstudio && \
	adduser --disabled-password --gecos '' --ingroup rstudio --uid 4357 rstudio && \
	Rscript -e "install.packages('DBI'); install.packages('RPostgres'); install.packages('stringr');" && \
	mkdir -p /etc/rstudio/connections && \
	chown rstudio /etc/rstudio/connections && \
	chown -R rstudio:rstudio /usr/local/lib/R/site-library

COPY exploretiva /exploretiva

USER rstudio
RUN \
	Rscript -e 'install.packages("/exploretiva", repos=NULL, type="source")' && \
	Rscript -e 'install.packages(c("xml2", "base64enc", "curl", "httr", "aws.ec2metadata"))' && \
	Rscript -e 'install.packages("aws.s3", repos = c("cloudyr" = "http://cloudyr.github.io/drat"))'

CMD ["/usr/lib/rstudio-server/bin/rserver"]
