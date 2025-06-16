import os
import re
import shutil
import requests
import subprocess

def parse_src_rpm(src_rpm):
    """
    Parses the source RPM filename to extract the package name, version, and release.

    Args:
        src_rpm (str): The source RPM filename.

    Returns:
        dict: A dictionary containing 'name', 'version', and 'release' if parsing is successful.
              None if the input is invalid.
    """
    # Define the regex pattern for extracting name, version, and release
    pattern = r"^([\w\-.\+]+)-([\d\w\-.\+\^\~]+)-([\d\w\-.\~\+]+)\.src\.rpm$"

    match = re.match(pattern, src_rpm)
    if match:
        return {
            "name": match.group(1),
            "version": match.group(2),
            "release": match.group(3),
        }
    else:
        return None

def exec_bash(bash_cmd: str) -> str:
    """
    Простая обертка для выполнения bash-команд
    :param bash_cmd: Команда в строковом формате
    :return: Возвращает результат выполнения в UTF-8 кодировке
    """
    ps = subprocess.Popen(bash_cmd,
                          shell=True,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL)
    return ps.communicate()[0].decode(encoding='utf-8', errors='replace')


def flatten(directory):
    for dirpath, _, filenames in os.walk(directory, topdown=False):
        for filename in filenames:
            i = 0
            source = os.path.join(dirpath, filename)
            target = os.path.join(directory, filename)

            while os.path.exists(target):
                i += 1
                file_parts = os.path.splitext(os.path.basename(filename))

                target = os.path.join(
                    directory,
                    file_parts[0] + "_" + str(i) + file_parts[1],
                )

            shutil.move(source, target)

            print("Moved ", source, " to ", target)

        if dirpath != directory:
            os.rmdir(dirpath)

            print("Deleted ", dirpath)


def get_response(*args, **kwargs):
    try:
        response: requests.Response = requests.get(*args, **kwargs)
        return response
    except ConnectionError:
        return None
