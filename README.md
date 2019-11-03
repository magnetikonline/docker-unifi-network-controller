# Docker UniFi Network Controller
Docker image and CLI management utility for a [UniFi Network Controller](https://help.ubnt.com/hc/en-us/articles/360012282453-UniFi-How-to-Install-Upgrade-the-UniFi-Network-Controller-Software) for configuration and management of [Ubiquiti](https://www.ui.com/) wireless networking infrastructure.

- [Overview](#overview)
- [Building](#building)
- [Usage](#usage)
	- [Basic](#basic)
	- [Adding persistent storage](#adding-persistent-storage)
- [Controller utility](#controller-utility)
	- [Starting](#starting)
	- [Stopping](#stopping)
	- [Backup](#backup)
	- [Restore](#restore)

## Overview
- Image components:
	- Ubuntu 18.04 base.
	- OpenJDK 8.
	- Ubiquiti Debian/Ubuntu Linux UniFi Network Controller.
	- MongoDB 3.4 for backend data store.
- Controller by default bootstraps it's own MongoDB process, thus entire stack can be executed within a single Docker container.
- Python CLI utility for start/stop of controller and handy backup/restore tasks.

## Building
To build an image with controller & MongoDB versions pinned to [`version`](version):

```sh
$ ./build.sh
```

Alternatively, to pull a pre-built image from Docker Hub:

```sh
$ docker pull magnetikonline/unifi-network-controller:5.10.25
```

Images are tagged with their UniFi Network Controller release version.

## Usage

### Basic
To start the controller container:

```sh
$ docker run \
	--detach \
	--network host \
	--publish "8080:8080/tcp" \
	--publish "8443:8443/tcp" \
	--rm \
	"magnetikonline/unifi-network-controller:5.10.25"
```

Published ports are for the following functions:
- `8080`: Device and controller communication.
- `8443`: Controller GUI/API.

Full list of [local ingress ports used](https://help.ubnt.com/hc/en-us/articles/218506997-UniFi-Ports-Used#1).

The `--network host` argument enables [host networking](https://docs.docker.com/network/host/):
- Will (likely) ensure the controller can discover/communicate with the local network and allow devices to reach the controller.
- Discards the need for published port (`--publish`) arguments, but won't hurt to still provide.

Once running the controller will present the initial welcome screen at `https://127.0.0.1:8443`.

### Adding persistent storage
You will _probably_ want controller data stored on a persistent Docker volume, rather than within an ephemeral container:

```sh
# create volume - if not already exists
$ docker volume create "controller-data"

# start controller, mounting volume at /usr/lib/unifi/data
$ docker run \
	--detach \
	--mount "type=volume,src=controller-data,dst=/usr/lib/unifi/data" \
	--network host \
	--publish "8080:8080/tcp" \
	--publish "8443:8443/tcp" \
	--rm \
	"magnetikonline/unifi-network-controller:5.10.25"
```

Or avoid all this boilerplate and use instead the [Controller utility](#controller-utility) outlined below.

## Controller utility
The [`controller.py`](controller.py) CLI utility provides the following functions:
- Start/stop the controller, using the version set in [`version`](version). Will automatically create both data/log persistent Docker volumes if required.
- Backup of the full data volume to a compressed tar archive.
- Restore of an existing backup tar archive into a fresh Docker data volume.

### Starting
```sh
$ ./controller.py start --help
usage: controller.py start [-h] [--no-host-network]
                           [--server-prefix SERVER_PREFIX]

optional arguments:
  -h, --help            show this help message and exit
  --no-host-network     disable Docker host networking (may break ability to
                        locate local network devices)
  --server-prefix SERVER_PREFIX
                        prefix for controller container and associated mounted
                        volumes (default: unifi-network-controller)

# start the server
$ ./controller.py start

Starting server [magnetikonline/unifi-network-controller:5.10.25] as [unifi-network-controller-server]
Running as container ID [ABCD...]
```

**Note:** if `--server-prefix` is used to set an alternative prefix for the server/controller and associated volumes it must be used with all related stop/backup/restore operations.

### Stopping
```sh
$ ./controller.py stop

Stopping server [unifi-network-controller-server]
Server has stopped
```

### Backup
The backup operation takes the full contents of the controller data Docker volume (MongoDB database, firmware downloads, miscellaneous config) and creates a compressed tar archive, which can be used for a full restore.

```sh
$ ./controller.py backup --file "/path/to/backup.tgz"

Backup successfully created at [/path/to/backup.tgz]
```

### Restore
Complementing the backup operation, restore takes an existing backup tar archive and extracts contents into a fresh Docker data volume.

**Note:** this _will_ clobber any existing controller data volume which may exist - use with care.

```sh
$ ./controller.py restore --file "/path/to/backup.tgz"

Removed existing data volume [unifi-network-controller-data]
Created volume [unifi-network-controller-data]
Data volume successfully restored from [/path/to/backup.tgz]
```
