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
		cargo=0.43.1-3~deb10u1 \
		gdebi-core=0.9.5.7+nmu3 \
		gfortran=4:8.3.0-1 \
		git=1:2.20.1-2+deb10u3 \
		libcairo2-dev=1.16.0-4+deb10u1 \
		libfontconfig1-dev=2.13.1-2 \
		libgit2-dev=0.27.7+dfsg.1-0.2 \
		libgsl-dev=2.5+dfsg-6 \
		libxml2-dev=2.9.4+dfsg1-7+deb10u4 \
		libpq-dev=11.16-0+deb10u1 \
		libgdal-dev=2.4.0+dfsg-1+b1 \
		libudunits2-dev=2.2.26-5 \
		libjq-dev=1.5+dfsg-2+b1 \
		libprotobuf-dev=3.6.1.3-2 \
		protobuf-compiler=3.6.1.3-2 \
		libnode-dev=10.24.0~dfsg-1~deb10u1 \
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
	echo 'local({' >> /usr/lib/R/etc/Rprofile.site && \
	echo '  r = getOption("repos")' >> /usr/lib/R/etc/Rprofile.site && \
	echo '  r["CRAN"] = "https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/cran/"' >> /usr/lib/R/etc/Rprofile.site && \
	echo '  options(repos = r)' >> /usr/lib/R/etc/Rprofile.site && \
	echo '})' >> /usr/lib/R/etc/Rprofile.site

COPY build.R /home
CMD Rscript /home/build.R
