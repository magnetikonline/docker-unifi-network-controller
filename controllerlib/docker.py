import json
import re
import subprocess
from typing import Dict, Generator, List, Optional, Tuple, Union


DOCKER_CLI_ARG_FORMAT_JSON = "--format={{json .}}"
_docker_cli_bin = ""


def find_cli() -> bool:
    global _docker_cli_bin
    if _docker_cli_bin != "":
        return True

    result = _run_command(["which", "docker"])
    if result.code != 0:
        # CLI not found
        return False

    # cache path to binary
    _docker_cli_bin = result.stdout[0]
    return True


def image_list() -> Generator[Tuple[str, Dict[str, str]], None, None]:
    _cli_exists()
    result = _run_command([_docker_cli_bin, "images", DOCKER_CLI_ARG_FORMAT_JSON])
    if result.code != 0:
        raise DockerError("unable to list images")

    for image in result.stdout:
        image = json.loads(image)
        yield (
            f"{image['Repository']}:{image['Tag']}",
            {
                "id": image["ID"],
                "repository": image["Repository"],
                "size": image["Size"],
                "tag": image["Tag"],
            },
        )


def container_list() -> Generator[Tuple[str, Dict[str, str]], None, None]:
    _cli_exists()
    result = _run_command([_docker_cli_bin, "ps", "--all", DOCKER_CLI_ARG_FORMAT_JSON])
    if result.code != 0:
        raise DockerError("unable to list containers")

    def exit_code(status):
        # attempt to extract process exit code from container (won't match if running)
        match = re.search(r"^Exited \(([0-9]+)\)", status)
        if match:
            return int(match.group(1))

        return None

    for container in result.stdout:
        container = json.loads(container)
        status = container["Status"]

        yield (
            container["Names"],
            {
                "exit_code": exit_code(status),
                "id": container["ID"],
                "image": container["Image"],
                "running": status.startswith("Up "),
                "status": status,
            },
        )


def volume_list() -> Generator[Tuple[str, Dict[str, str]], None, None]:
    _cli_exists()
    result = _run_command([_docker_cli_bin, "volume", "ls", DOCKER_CLI_ARG_FORMAT_JSON])
    if result.code != 0:
        raise DockerError("unable to list volumes")

    for volume in result.stdout:
        volume = json.loads(volume)
        yield (volume["Name"], {"mount_point": volume["Mountpoint"]})


def image_pull(repository: str, tag: str) -> None:
    _cli_exists()
    result = _run_command([_docker_cli_bin, "pull", "--quiet", f"{repository}:{tag}"])
    if result.code != 0:
        raise DockerError("unable to pull image")


def volume_create(name: str) -> None:
    _cli_exists()
    result = _run_command([_docker_cli_bin, "volume", "create", name])
    if result.code != 0:
        raise DockerError("unable to create volume")


def volume_delete(name: str) -> None:
    _cli_exists()
    result = _run_command([_docker_cli_bin, "volume", "rm", name])
    if result.code != 0:
        raise DockerError("unable to delete volume")


def container_run(
    image_repository: str,
    image_tag: str = "latest",
    bind_list: List[Tuple[str, str]] = [],
    command_arg_list: List[str] = [],
    detach: bool = False,
    name: Optional[str] = None,
    network_host: bool = False,
    publish_list: List[Tuple[int, int]] = [],
    remove_on_exit: bool = False,
    volume_list: List[Tuple[str, str]] = [],
) -> Union[bool, str]:
    _cli_exists()

    # build run arguments
    run_arg_list = [_docker_cli_bin, "run"]

    if detach:
        run_arg_list.append("--detach")

    for bind_src, bind_dst in bind_list:
        run_arg_list.extend(["--mount", f"type=bind,src={bind_src},dst={bind_dst}"])

    for volume_src, volume_dst in volume_list:
        run_arg_list.extend(
            ["--mount", f"type=volume,src={volume_src},dst={volume_dst}"]
        )

    if name is not None:
        run_arg_list.extend(["--name", name])

    if network_host:
        run_arg_list.extend(["--network", "host"])

    # only publish explicit port if host networking *not* enabled
    # https://docs.docker.com/network/host/
    if not network_host:
        for host, container in publish_list:
            run_arg_list.extend(["--publish", f"{host}:{container}/tcp"])

    if remove_on_exit:
        run_arg_list.append("--rm")

    run_arg_list.append(f"{image_repository}:{image_tag}")
    run_arg_list.extend(command_arg_list)

    result = _run_command(run_arg_list)
    if result.code != 0:
        raise DockerError("unable to run image")

    if len(result.stdout) == 1:
        return result.stdout[0]

    # didn't get a container ID back
    return False


def container_stop(name: str) -> None:
    _cli_exists()
    result = _run_command([_docker_cli_bin, "stop", name])
    if result.code != 0:
        raise DockerError("unable to stop container")


class _RunCommandResult:
    def __init__(self, code, stdout, stderr):
        # store stdout/err lines as lists - if no lines, ensure to return empty list
        def split(output):
            line_list = output.rstrip().split("\n")
            if (len(line_list) == 1) and (line_list[0] == ""):
                return []

            return line_list

        self.code = code
        self.stdout = split(stdout)
        self.stderr = split(stderr)


def _run_command(argument_list: List[str]) -> _RunCommandResult:
    result = subprocess.run(
        argument_list, encoding="utf-8", stderr=subprocess.PIPE, stdout=subprocess.PIPE
    )

    return _RunCommandResult(result.returncode, result.stdout, result.stderr)


def _cli_exists() -> None:
    if not find_cli():
        raise DockerError("unable to locate Docker CLI")


class DockerError(Exception):
    pass
