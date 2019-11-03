FROM ubuntu:18.04
LABEL maintainer="Peter Mescalchin <peter@magnetikonline.com>"

ARG MONGODB_VERSION
ARG UNIFI_MD5SUM
ARG UNIFI_VERSION
ARG UNIFI_DEBFILE="unifi_sysvinit_all.deb"

ENV DEBIAN_FRONTEND="noninteractive"

RUN apt-get update && \
	# install packages
	# $UNIFI_DEBFILE requires [binutils java8-runtime-headless (openjdk-8-jre-headless) jsvc libcap2]
	apt-get install --no-install-recommends --yes \
		ca-certificates curl \
		binutils jsvc libcap2 openjdk-8-jre-headless \
		gnupg2 && \
	# add MongoDB apt repository
	apt-key adv \
		--keyserver hkp://keyserver.ubuntu.com:80 \
		--recv 0C49F3730359A14518585931BC711F9BA15703C6 && \
	echo "deb http://repo.mongodb.org/apt/ubuntu xenial/mongodb-org/${MONGODB_VERSION%.*} multiverse" \
		>/etc/apt/sources.list.d/mongodb.list && \
	# install MongoDB
	apt-get update && \
	apt-get install --no-install-recommends --yes \
		"mongodb-org=$MONGODB_VERSION" && \
	# download/verify/install UniFi network controller
	curl --remote-name "https://dl.ui.com/unifi/$UNIFI_VERSION/$UNIFI_DEBFILE" && \
	echo "$UNIFI_MD5SUM $UNIFI_DEBFILE" | md5sum --check --status && \
	dpkg --install "$UNIFI_DEBFILE" && \
	# clean up
	apt-get clean && \
	rm --force --recursive /var/lib/apt/lists && \
	rm --force "$UNIFI_DEBFILE"

# ports: [8080] device/controller communication, [8443] GUI/API
EXPOSE 8080/tcp 8443/tcp

ADD ./entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/bin/bash","/entrypoint.sh"]
