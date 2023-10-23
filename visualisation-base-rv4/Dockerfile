#FROM debian:bullseye
FROM debian:buster

ENV R_BASE_VERSION 4.3.1

RUN \
	apt-get update && \
	apt-get install -y --no-install-recommends \
		locales \
        ca-certificates \
		dirmngr \
		gnupg2 && \
    echo "en_GB.UTF-8 UTF-8" >> /etc/locale.gen && \
	locale-gen en_GB.utf8 && \
	rm -rf /var/lib/apt/lists/*

ENV \
	LC_ALL=en_GB.UTF-8 \
	LANG=en_GB.UTF-8 \
	LANGUAGE=en_GB.UTF-8

#RUN rm -rf /var/lib/apt/lists/* && \
#    rm -rf /etc/apt/sources.list && \
#    echo "deb https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/debian/ bullseye main" > /etc/apt/sources.list
#
#RUN apt-get update \
#        && apt-get install -y --no-install-recommends \
#            libopenblas0-pthread \
#		littler \
#                r-cran-docopt \
#                r-cran-littler \
#		r-base \
#		r-base-dev \
#        r-base-core \
#		r-recommended \
#	&& chown root:staff "/usr/local/lib/R/site-library" \
#	&& chmod g+ws "/usr/local/lib/R/site-library" \
#	&& ln -s /usr/lib/R/site-library/littler/examples/install.r /usr/local/bin/install.r \
#	&& ln -s /usr/lib/R/site-library/littler/examples/install2.r /usr/local/bin/install2.r \
#	&& ln -s /usr/lib/R/site-library/littler/examples/installBioc.r /usr/local/bin/installBioc.r \
#	&& ln -s /usr/lib/R/site-library/littler/examples/installDeps.r /usr/local/bin/installDeps.r \
#	&& ln -s /usr/lib/R/site-library/littler/examples/installGithub.r /usr/local/bin/installGithub.r \
#	&& ln -s /usr/lib/R/site-library/littler/examples/testInstalled.r /usr/local/bin/testInstalled.r \
#	&& rm -rf /tmp/downloaded_packages/ /tmp/*.rds \
#	&& rm -rf /var/lib/apt/lists/*

RUN \
	apt-get update && \
	apt-get install -y --no-install-recommends \
		ca-certificates \
		dirmngr \
		gnupg2 && \
	rm -rf /var/lib/apt/lists/* && \
    rm -rf /etc/apt/sources.list && \
    echo "deb https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/debian/ buster main" > /etc/apt/sources.list && \
	echo "deb http://cloud.r-project.org/bin/linux/debian buster-cran40/" >> /etc/apt/sources.list && \
	echo "Acquire{Check-Valid-Until false; Retries 10;}" >> /etc/apt/apt.conf && \
	until apt-key adv --keyserver keyserver.ubuntu.com --recv-key '95C0FAF38DB3CCAD0C080A7BDC78B2DDEABC47B7'; do sleep 10; done && \
    gpg --armor --export '95C0FAF38DB3CCAD0C080A7BDC78B2DDEABC47B7' | tee /etc/apt/trusted.gpg.d/cran_debian_key.asc && \
	apt-get update
#    && \
#    apt-get install -y --no-install-recommends \
#		r-base \
#		r-base-dev \
#		r-recommended
#    && \
#	rm -rf /var/lib/apt/lists/* && \
#	# Remove the last line from sources: the CRAN debian repo that has R itself, which we don't mirror
#	sed -i '$d' /etc/apt/sources.list && \
#	echo 'local({' >> /usr/lib/R/etc/Rprofile.site && \
#	echo '  r = getOption("repos")' >> /usr/lib/R/etc/Rprofile.site && \
#	echo '  r["CRAN"] = "https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/cran-binary-rv4/"' >> /usr/lib/R/etc/Rprofile.site && \
#	echo '  r["CRAN_1"] = "https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/cran/"' >> /usr/lib/R/etc/Rprofile.site && \
#	echo '  options(repos = r)' >> /usr/lib/R/etc/Rprofile.site && \
#	echo '})' >> /usr/lib/R/etc/Rprofile.site
