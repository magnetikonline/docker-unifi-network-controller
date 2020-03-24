#!/bin/bash -e

DIRNAME=$(dirname "$0")
DOCKER_REPOSITORY=${DOCKER_REPOSITORY-"magnetikonline/unifi-network-controller"}


. "$DIRNAME/version"

docker build \
	--build-arg "MONGODB_VERSION=$MONGODB_VERSION" \
	--build-arg "UNIFI_MD5SUM=$UNIFI_MD5SUM" \
	--build-arg "UNIFI_VERSION=$UNIFI_VERSION" \
	--tag "$DOCKER_REPOSITORY:$UNIFI_VERSION" \
		"$DIRNAME"
