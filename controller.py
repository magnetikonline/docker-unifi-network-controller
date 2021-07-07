#!/usr/bin/env python3

import argparse
import os.path
import re
import sys
from typing import Any, Dict, Tuple

from controllerlib import action, docker

VERSION_FILE = "version"
SERVER_PREFIX_DEFAULT = "unifi-network-controller"
SERVER_PREFIX_ALLOWED_REGEXP = r"^[a-zA-Z0-9][a-zA-Z0-9_-]+[a-zA-Z0-9]$"


def exit_error(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def read_arguments() -> Tuple[str, Dict[str, Any]]:
    # create parser
    parser = argparse.ArgumentParser(
        description="Execution and management for UniFi Network Controller Docker image"
    )
    subparsers = parser.add_subparsers(dest="command")

    def add_server_prefix(parser):
        parser.add_argument(
            "--server-prefix",
            default=SERVER_PREFIX_DEFAULT,
            help="prefix for controller container and associated mounted volumes (default: %(default)s)",
        )

    # command - start
    parser_start = subparsers.add_parser("start")
    parser_start.add_argument(
        "--no-host-network",
        action="store_true",
        help="disable Docker host networking (may break ability to locate local network devices)",
    )

    add_server_prefix(parser_start)

    # command - stop
    parser_stop = subparsers.add_parser("stop")
    add_server_prefix(parser_stop)

    # command - backup
    parser_backup = subparsers.add_parser("backup")
    parser_backup.add_argument(
        "--file", help="target backup archive", metavar="ARCHIVE", required=True
    )

    add_server_prefix(parser_backup)

    # command - restore
    parser_restore = subparsers.add_parser("restore")
    parser_restore.add_argument(
        "--file", help="source backup archive", metavar="ARCHIVE", required=True
    )

    add_server_prefix(parser_restore)

    arg_list = parser.parse_args()

    def validate_server_prefix():
        if not re.search(SERVER_PREFIX_ALLOWED_REGEXP, arg_list.server_prefix):
            exit_error(
                f"invalid --server-prefix of [{arg_list.server_prefix}], expecting {SERVER_PREFIX_ALLOWED_REGEXP}"
            )

    def file_path_canonical(file):
        directory, filename = os.path.split(os.path.realpath(file))
        if not os.path.isdir(directory):
            exit_error(f"file path [{file}] not a valid directory")

        return (directory, filename)

    if arg_list.command == "start":
        validate_server_prefix()
        return (
            "start",
            {
                "no_host_network": arg_list.no_host_network,
                "server_prefix": arg_list.server_prefix,
            },
        )

    if arg_list.command == "stop":
        validate_server_prefix()
        return ("stop", {"server_prefix": arg_list.server_prefix})

    if arg_list.command == "backup":
        validate_server_prefix()
        return (
            "backup",
            {
                "file": file_path_canonical(arg_list.file),
                "server_prefix": arg_list.server_prefix,
            },
        )

    if arg_list.command == "restore":
        validate_server_prefix()
        return (
            "restore",
            {
                "file": file_path_canonical(arg_list.file),
                "server_prefix": arg_list.server_prefix,
            },
        )

    # no command given
    exit_error("no command given, require one of {start,stop,backup,restore}")
    return ("", {})


def load_version() -> str:
    # load version file
    line_list = []
    file_path = f"{os.path.dirname(__file__)}/{VERSION_FILE}"

    try:
        fh = open(file_path, "r")
        line_list = fh.readlines()
        fh.close()
    except OSError:
        exit_error(f"unable to open version file at [{file_path}]")

    # scan lines, looking for last version definition
    version = None
    for line in line_list:
        match = re.search(r'^UNIFI_VERSION="([^"]+)"', line)
        if match:
            version = match.group(1)

    if version is not None:
        return version

    # not found
    exit_error(f"unable to determine image version from [{file_path}]")
    return ""


def main():
    command, command_data = read_arguments()

    # confirm Docker CLI exists
    if not docker.find_cli():
        exit_error("unable to find Docker CLI")

    # execute requested command
    try:
        if command == "start":
            action.start_server(
                image_tag=load_version(),
                server_prefix=command_data["server_prefix"],
                no_host_network=command_data["no_host_network"],
            )

            return

        if command == "stop":
            action.stop_server(server_prefix=command_data["server_prefix"])
            return

        if command == "backup":
            action.backup(
                server_prefix=command_data["server_prefix"],
                archive_dir=command_data["file"][0],
                archive_name=command_data["file"][1],
            )

            return

        if command == "restore":
            action.restore(
                server_prefix=command_data["server_prefix"],
                archive_dir=command_data["file"][0],
                archive_name=command_data["file"][1],
            )

            return
    except action.FatalError as err:
        exit_error(str(err))


if __name__ == "__main__":
    main()
