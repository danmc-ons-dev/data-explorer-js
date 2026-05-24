"""Functions assisting in file system cleanups."""

import os
import pathlib
import shutil
import time


def cleanup_temp_directories(dir_path: pathlib.Path, max_age: int, check_interval: int) -> None:
    """Cleanup the temp directory.

    Args:
        dir_path (pathlib.Path): The parent directory of the temporary directories.
        max_age (int): The max age of a directory before it gets deleted.
        check_interval (int): The number of seconds to wait between cleanups.
    """
    while True:
        if not os.path.exists(dir_path):
            raise FileNotFoundError(f"There is no directory at {dir_path}.")
        for directory in os.listdir(dir_path):
            if "temporary" not in directory:
                # print(f"Skipping {directory}.")
                continue
            directory = os.path.join(dir_path, directory)
            dir_age = time.time() - os.path.getmtime(directory)
            if dir_age >= max_age:
                shutil.rmtree(directory)
                print(f"Deleted directory {directory} of age {dir_age}")
        time.sleep(check_interval)
