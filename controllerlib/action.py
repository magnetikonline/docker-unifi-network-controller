import os
import tarfile
from typing import AbstractSet

from controllerlib import docker

CONTROLLER_REPOSITORY_NAME = "magnetikonline/unifi-network-controller"
CONTROLLER_PORT_COMMS = 8080
CONTROLLER_PORT_GUI = 8443
CONTROLLER_BASE_DIR = "/usr/lib/unifi"

BACKUP_REPOSITORY_NAME = "alpine"
BACKUP_RESTORE_BACKUP_PATH = "/backup"
BACKUP_RESTORE_VOLUME_MOUNT_PATH = "/data"
BACKUP_ARCHIVE_KEY_FILE_LIST = [
    "./db/version",
    "./db/WiredTiger",
    "./firmware.json",
    "./system.properties",
]


def start_server(image_tag: str, server_prefix: str, no_host_network: bool) -> None:
    # confirm controller Docker image exists, if not pull it
    _image_pull(CONTROLLER_REPOSITORY_NAME, image_tag)

    # query containers, confirm server container does not exist, otherwise exit
    container_name = _container_server_name(server_prefix)
    if container_name in dict(docker.container_list()):
        raise FatalError(f"container [{container_name}] already exists")

    # query Docker volumes, create any that are required
    volume_name_data = _volume_data_name(server_prefix)
    volume_name_logs = _volume_logs_name(server_prefix)

    volume_list = dict(docker.volume_list()).keys()
    _volume_create(volume_name_data, volume_list)
    _volume_create(volume_name_logs, volume_list)

    # start server
    print(
        f"Starting server [{CONTROLLER_REPOSITORY_NAME}:{image_tag}] as [{container_name}]"
    )

    try:
        container_id = docker.container_run(
            image_repository=CONTROLLER_REPOSITORY_NAME,
            image_tag=image_tag,
            detach=True,
            name=container_name,
            network_host=not no_host_network,
            publish_list=[
                (CONTROLLER_PORT_COMMS, CONTROLLER_PORT_COMMS),
                (CONTROLLER_PORT_GUI, CONTROLLER_PORT_GUI),
            ],
            remove_on_exit=True,
            volume_list=[
                (volume_name_data, f"{CONTROLLER_BASE_DIR}/data"),
                (volume_name_logs, f"{CONTROLLER_BASE_DIR}/logs"),
            ],
        )
    except docker.DockerError:
        raise FatalError("unable to start server")

    print(f"Running as container ID [{container_id}]")


def stop_server(server_prefix: str) -> None:
    container_name = _container_server_name(server_prefix)
    container_list = dict(docker.container_list())

    # confirm server container exists and is running
    if container_name not in container_list:
        raise FatalError(f"container [{container_name}] not does exist")

    if not container_list[container_name]["running"]:
        raise FatalError(f"container [{container_name}] not running")

    print(f"Stopping server [{container_name}]")

    try:
        docker.container_stop(container_name)
    except docker.DockerError:
        raise FatalError("unable to stop server")

    print("Server has stopped")


def backup(server_prefix: str, archive_dir: str, archive_name: str) -> None:
    # confirm data volume for backup exists
    volume_name_data = _volume_data_name(server_prefix)
    if volume_name_data not in dict(docker.volume_list()):
        raise FatalError(f"data volume [{volume_name_data}] does not exist for backup")

    # confirm image used for backup exists, if not pull it
    _image_pull(BACKUP_REPOSITORY_NAME)

    try:
        # execute backup of volume - using temporary container
        docker.container_run(
            image_repository=BACKUP_REPOSITORY_NAME,
            bind_list=[(archive_dir, BACKUP_RESTORE_BACKUP_PATH)],
            command_arg_list=[
                "/bin/sh",
                "-c",
                _backup_archive_cmd(f"{BACKUP_RESTORE_BACKUP_PATH}/{archive_name}"),
            ],
            remove_on_exit=True,
            volume_list=[(volume_name_data, BACKUP_RESTORE_VOLUME_MOUNT_PATH)],
        )
    except docker.DockerError:
        raise FatalError(f"unable to backup data volume [{volume_name_data}]")

    print(f"Backup successfully created at [{archive_dir}/{archive_name}]")


def _backup_archive_cmd(file: str) -> str:
    # command to a) create tar archive of data volume b) change ownership to current user
    return (
        f'/bin/tar c -zf "{file}" -C "{BACKUP_RESTORE_VOLUME_MOUNT_PATH}" . && '
        f'chown {os.getuid()}:{os.getgid()} "{file}"'
    )


def restore(server_prefix: str, archive_dir: str, archive_name: str) -> None:
    # confirm archive exists/is an archive and contains controller data files
    _restore_verify_archive(f"{archive_dir}/{archive_name}")

    # data archive considered valid
    # confirm controller isn't currently running as we're rebuilding the data volume and it can't be in use
    container_name = _container_server_name(server_prefix)
    for name, data in docker.container_list():
        if name == container_name and data["running"]:
            raise FatalError(
                f"container [{container_name}] currently running, "
                "associated data volume must not be in use for restore"
            )

    # remove (possible) existing data volume
    volume_name_data = _volume_data_name(server_prefix)
    for name, _ in docker.volume_list():
        if name != volume_name_data:
            continue

        # found existing volume - remove it
        try:
            docker.volume_delete(volume_name_data)
            print(f"Removed existing data volume [{volume_name_data}]")
        except docker.DockerError:
            raise FatalError(
                f"unable to remove existing data volume [{volume_name_data}]"
            )

    # confirm image used for restore exists, if not pull it and create new volume
    _image_pull(BACKUP_REPOSITORY_NAME)
    _volume_create(volume_name_data)

    # restore archive into new data volume
    try:
        # execute backup of volume - using temporary container
        docker.container_run(
            image_repository=BACKUP_REPOSITORY_NAME,
            bind_list=[(archive_dir, BACKUP_RESTORE_BACKUP_PATH)],
            command_arg_list=[
                "/bin/sh",
                "-c",
                _restore_archive_cmd(f"{BACKUP_RESTORE_BACKUP_PATH}/{archive_name}"),
            ],
            remove_on_exit=True,
            volume_list=[(volume_name_data, BACKUP_RESTORE_VOLUME_MOUNT_PATH)],
        )
    except docker.DockerError:
        raise FatalError(f"unable to restore data volume [{volume_name_data}]")

    print(f"Data volume successfully restored from [{archive_dir}/{archive_name}]")


def _restore_verify_archive(archive_path: str) -> None:
    # open archive, confirm it's a tar file
    try:
        archive_tar = tarfile.open(archive_path, mode="r")
    except OSError:
        raise FatalError(f"unable to open archive [{archive_path}]")
    except tarfile.TarError:
        raise FatalError(f"it appears [{archive_path}] is not a tar file")

    # analyse, confirming it contains key controller data files
    key_file_count = 0
    for tar_file in archive_tar.getmembers():
        if tar_file.name in BACKUP_ARCHIVE_KEY_FILE_LIST:
            key_file_count += 1

    archive_tar.close()
    if key_file_count < len(BACKUP_ARCHIVE_KEY_FILE_LIST):
        # didn't find every file expected
        raise FatalError(
            f"archive [{archive_path}] doesn't appear to be a controller data backup"
        )

    # archive passed verification


def _restore_archive_cmd(file: str) -> str:
    # command to a) move into the root of the Docker volume b) extract tar mounted at host into volume
    return f'cd "{BACKUP_RESTORE_VOLUME_MOUNT_PATH}" && tar x -f "{file}"'


def _container_server_name(server_prefix: str) -> str:
    return f"{server_prefix}-server"


def _volume_data_name(server_prefix: str) -> str:
    return f"{server_prefix}-data"


def _volume_logs_name(server_prefix: str) -> str:
    return f"{server_prefix}-logs"


def _image_pull(repository: str, tag: str = "latest") -> None:
    image_name = f"{repository}:{tag}"
    if image_name in dict(docker.image_list()):
        # no work
        return

    print(f"Docker image [{image_name}] not available - attempting to pull")

    try:
        docker.image_pull(repository, tag)
    except docker.DockerError:
        raise FatalError(f"unable to pull [{image_name}]")

    print("Successfully pulled Docker image")


def _volume_create(name: str, existing_volume_list: AbstractSet[str] = set()) -> None:
    if name in existing_volume_list:
        # no work
        return

    try:
        docker.volume_create(name)
    except docker.DockerError:
        raise FatalError(f"unable to create volume [{name}]")

    print(f"Created volume [{name}]")


class FatalError(Exception):
    pass
