import os
import shutil
import tempfile
import importlib.resources
from ..constants import Config


def load_resource(filename: str, package_name: str = None) -> str:
    """
    Load a file from the resources of a package

    Args:
        filename (str): the file name
        package_name (str): the package name

    Returns:
        str: the content of the file
    """
    if package_name is None:
        package_name = f"{Config.PACAKAGE_NAME}.{Config.RESOURCE_NAME}"

    resources = importlib.resources.files(package_name)
    with resources.joinpath(filename).open("r", encoding="utf8") as f:
        return f.read()


def is_file_in_resources(filename: str, package_name: str = None) -> bool:
    """
    Check if a file is in the resources of a package

    Args:
        filename (str): the file name
        package_name (str): the package name

    Returns:
        bool: whether the file is in the resources of the package
    """
    if package_name is None:
        package_name = f"{Config.PACAKAGE_NAME}.{Config.RESOURCE_NAME}"

    try:
        return importlib.resources.is_resource(package_name, filename)
    except ModuleNotFoundError:

        return False


def write_to_resources(filename: str, content: str | bytes, package_name: str = None):
    """
    Write a file to the resources of a package

    Args:
        filename (str): the file name
        content (str): the content of the file

    Returns:
        None, but write the file to the resources of the package
    """

    if package_name is None:
        package_name = f"{Config.PACAKAGE_NAME}.{Config.RESOURCE_NAME}"

    temp_dir = tempfile.mkdtemp()

    try:
        temp_file = os.path.join(temp_dir, filename)
        with open(temp_file, "w") as f:
            f.write(content)

        destination = importlib.resources.files(f"{package_name}")
        shutil.copy(temp_file, os.path.join(destination, filename))
    finally:
        shutil.rmtree(temp_dir)


def get_resource_path(package_name: str = None) -> str:
    """
    Get the path to the resources of a package

    Args:
        package_name (str): the package name

    Returns:
        str: the path to the resources of the package
    """

    if package_name is None:
        package_name = f"{Config.PACAKAGE_NAME}.{Config.RESOURCE_NAME}"

    return importlib.resources.files(package_name)


def delete_duplicate_str(data: list[str]) -> list[str]:
    """
    Delete duplicate strings in a list

    Args:
        data (list[str]): the input list

    Returns:
        list[str]: the list without duplicate strings
    """
    immutable_dict = set([str(item) for item in data])
    data = [eval(i) for i in immutable_dict]
    return data
