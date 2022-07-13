#!/bin/bash -e

BASEDIR="/usr/lib/unifi"

JAVA_HOME="/usr/lib/jvm/java-8-openjdk-amd64"
javaHomeArm="/usr/lib/jvm/java-8-openjdk-arm64"
if [[ -d $javaHomeArm ]]; then
	JAVA_HOME=$javaHomeArm
fi

JVM_MAX_HEAP_SIZE="1024M"
JVM_OPTS=(
	"-Xmx$JVM_MAX_HEAP_SIZE"
	"-Djava.awt.headless=true"
	"-Dfile.encoding=UTF-8"
)


cd "$BASEDIR"
exec "$JAVA_HOME/jre/bin/java" \
	${JVM_OPTS[@]} \
	-jar "$BASEDIR/lib/ace.jar" \
		start
