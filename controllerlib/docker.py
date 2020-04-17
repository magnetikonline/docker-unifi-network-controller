import json
import re
import subprocess


DOCKER_CLI_ARG_FORMAT_JSON = "--format={{json .}}"
_docker_cli_bin = None


def find_cli():
    global _docker_cli_bin
    if _docker_cli_bin is not None:
        return True

    result = _run_command(["which", "docker"])
    if result.code != 0:
        # CLI not found
        return False

    # cache path to binary
    _docker_cli_bin = result.stdout[0]
    return True


def image_list():
    _cli_exists()
    result = _run_command([_docker_cli_bin, "images", DOCKER_CLI_ARG_FORMAT_JSON])
    if result.code != 0:
        raise DockerError("unable to list images")

    for image in result.stdout:
        image = json.loads(image)
        yield f"{image['Repository']}:{image['Tag']}", {
            "id": image["ID"],
            "repository": image["Repository"],
            "size": image["Size"],
            "tag": image["Tag"],
        }


def container_list():
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

        yield container["Names"], {
            "exit_code": exit_code(status),
            "id": container["ID"],
            "image": container["Image"],
            "running": status.startswith("Up "),
            "status": status,
        }


def volume_list():
    _cli_exists()
    result = _run_command([_docker_cli_bin, "volume", "ls", DOCKER_CLI_ARG_FORMAT_JSON])
    if result.code != 0:
        raise DockerError("unable to list volumes")

    for volume in result.stdout:
        volume = json.loads(volume)
        yield volume["Name"], {"mount_point": volume["Mountpoint"]}


def image_pull(repository, tag):
    _cli_exists()
    result = _run_command([_docker_cli_bin, "pull", "--quiet", f"{repository}:{tag}"])
    if result.code != 0:
        raise DockerError("unable to pull image")


def volume_create(name):
    _cli_exists()
    result = _run_command([_docker_cli_bin, "volume", "create", name])
    if result.code != 0:
        raise DockerError("unable to create volume")


def volume_delete(name):
    _cli_exists()
    result = _run_command([_docker_cli_bin, "volume", "rm", name])
    if result.code != 0:
        raise DockerError("unable to delete volume")


def container_run(
    image_repository,
    image_tag="latest",
    bind_list=[],
    command_arg_list=[],
    detach=False,
    name=None,
    network_host=False,
    publish_list=[],
    remove_on_exit=False,
    volume_list=[],
):
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


def container_stop(name):
    _cli_exists()
    result = _run_command([_docker_cli_bin, "stop", name])
    if result.code != 0:
        raise DockerError("unable to stop container")


def _run_command(argument_list):
    result = subprocess.run(
        argument_list, encoding="utf-8", stderr=subprocess.PIPE, stdout=subprocess.PIPE
    )

    return _RunCommandResult(result.returncode, result.stdout, result.stderr)


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


def _cli_exists():
    if not find_cli():
        raise DockerError("unable to locate Docker CLI")


class DockerError(Exception):
    pass
