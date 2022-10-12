FROM debian:buster-slim

RUN \
	apt-get update && \
	apt-get install -y --no-install-recommends \
		locales=2.28-10+deb10u1 && \
	echo "en_GB.UTF-8 UTF-8" >> /etc/locale.gen && \
	locale-gen en_GB.utf8 && \
	rm -rf /var/lib/apt/lists/*

ENV \
	LC_ALL=en_GB.UTF-8 \
	LANG=en_GB.UTF-8 \
	LANGUAGE=en_GB.UTF-8

RUN \
	apt-get update && \
	apt-get install -y --no-install-recommends \
		ca-certificates \
		dirmngr \
		gnupg2 && \
	rm -rf /var/lib/apt/lists/* && \
	echo "deb http://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/debian/ buster main" > /etc/apt/sources.list && \
	echo "deb http://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/debian-security/ buster/updates main" >> /etc/apt/sources.list && \
	echo "deb http://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/debian/ buster-updates main" >> /etc/apt/sources.list && \
	echo "deb http://cran.ma.imperial.ac.uk/bin/linux/debian buster-cran35/" >> /etc/apt/sources.list && \
	echo "Acquire{Check-Valid-Until false; Retries 10;}" >> /etc/apt/apt.conf && \
	until apt-key adv --keyserver keyserver.ubuntu.com --recv-key '95C0FAF38DB3CCAD0C080A7BDC78B2DDEABC47B7'; do sleep 10; done && \
	rm -rf /var/lib/apt/lists/* && \
	apt-get update && \
	apt-get install -y --no-install-recommends \
		cargo \
		gdebi-core \
		gfortran \
		git \
		libcairo2-dev  \
		libfontconfig1-dev \
		libgit2-dev \
		libgsl-dev \
		libxml2-dev \
		libpq-dev \
		libgdal-dev \
		libudunits2-dev \
		libjq-dev \
		libprotobuf-dev \
		protobuf-compiler \
		libnode-dev \
		lmodern \
		procps \
		r-base-dev \
		r-base\
		r-cran-base64enc \
		r-cran-curl \
		r-cran-data.table \
		r-cran-dbi \
		r-cran-httr \
		r-cran-rpostgresql \
		r-cran-xml2 \
		r-recommended \
		ssh \
		texlive \
		texlive-latex-extra \
		git-man \
		man-db\
		wget && \
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
	echo 'local({' >> /usr/lib/R/etc/Rprofile.site && \
	echo '  r = getOption("repos")' >> /usr/lib/R/etc/Rprofile.site && \
	echo '  r["CRAN"] = "https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/cran/"' >> /usr/lib/R/etc/Rprofile.site && \
	echo '  options(repos = r)' >> /usr/lib/R/etc/Rprofile.site && \
	echo '})' >> /usr/lib/R/etc/Rprofile.site

COPY build.R /home
CMD Rscript /home/build.R
