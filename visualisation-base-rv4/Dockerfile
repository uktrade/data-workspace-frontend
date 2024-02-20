FROM debian:bullseye

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

RUN \
	apt-get update && \
	apt-get install -y --no-install-recommends \
		ca-certificates \
		dirmngr \
		gnupg2 && \
	rm -rf /var/lib/apt/lists/* && \
    echo "deb https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/debian/ bullseye main" > /etc/apt/sources.list && \
	echo "Acquire{Check-Valid-Until false; Retries 10;}" >> /etc/apt/apt.conf && \
	until apt-key adv --keyserver keyserver.ubuntu.com --recv-key '95C0FAF38DB3CCAD0C080A7BDC78B2DDEABC47B7'; do sleep 10; done && \
    gpg --armor --export '95C0FAF38DB3CCAD0C080A7BDC78B2DDEABC47B7' | tee /etc/apt/trusted.gpg.d/cran_debian_key.asc && \
    rm -rf /var/lib/apt/lists/* && \
	apt-get update && \
    apt-get install -y \
        r-base \
        r-recommended && \
	rm -rf /var/lib/apt/lists/* && \
	# Remove the last line from sources: the CRAN debian repo that has R itself, which we don't mirror
	sed -i '$d' /etc/apt/sources.list && \
	echo 'local({' >> /usr/lib/R/etc/Rprofile.site && \
	echo '  r = getOption("repos")' >> /usr/lib/R/etc/Rprofile.site && \
	echo '  r["CRAN"] = "https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/cran-binary-rv4/"' >> /usr/lib/R/etc/Rprofile.site && \
	echo '  r["CRAN_1"] = "https://s3-eu-west-2.amazonaws.com/mirrors.notebook.uktrade.io/cran/"' >> /usr/lib/R/etc/Rprofile.site && \
	echo '  options(repos = r)' >> /usr/lib/R/etc/Rprofile.site && \
	echo '})' >> /usr/lib/R/etc/Rprofile.site
