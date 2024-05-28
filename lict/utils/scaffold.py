import os
import shutil
import tempfile
import importlib.resources
from lict.constants import Settings

from typing import Generator


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
        package_name = f"{Settings.PACAKAGE_NAME}.{Settings.RESOURCE_NAME}"

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
        package_name = f"{Settings.PACAKAGE_NAME}.{Settings.RESOURCE_NAME}"

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
        package_name = f"{Settings.PACAKAGE_NAME}.{Settings.RESOURCE_NAME}"

    temp_dir = tempfile.mkdtemp()

    try:
        temp_file = os.path.join(temp_dir, filename)
        with open(temp_file, "w") as f:
            f.write(content)

        destination = importlib.resources.files(f"{package_name}")
        shutil.copy(temp_file, os.path.join(destination, filename))
    finally:
        shutil.rmtree(temp_dir)


def get_resource_path(package_name: str = None, resource_name: str = None) -> str:
    """
    Get the path to the resources of a package

    Args:
        package_name (str): the package name
        resource_name (str): the resource name

    Returns:
        str: the path to the resources of the package
    """

    package_name = package_name if package_name else Settings.PACAKAGE_NAME
    resource_name = resource_name if resource_name else Settings.RESOURCE_NAME

    resource_path = f"{package_name}.{resource_name}"

    return importlib.resources.files(resource_path).joinpath("")


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


def find_duplicate_keys(dict_a: dict[str, any], dict_b: dict[str, any]) -> set[str]:
    """
    TODO: Add docstring
    """
    return set(dict_a.keys()) & set(dict_b.keys())


def zip_with_none(list_a: list[any], list_b: list[any]):
    """
    TODO: Add docstring
    """
    visited, result = set(), []

    for elem_a in list_a:
        for elem_b in list_b:
            if elem_a == elem_b:
                result.append((elem_a, elem_b))
                visited.add(elem_b)
                break
        result.append((elem_a, None))

    for elem_b in list_b:
        if elem_b not in visited:
            result.append((None, elem_b))
    return result


def extract_folder_name(path: str) -> str:
    """
    Calculate the file name in a certain file path.

    Args:
        path (str): The path of the file.

    Returns:
        str: The file name.
    """
    if "\\" in path:
        parts = path.split("\\")
        folder_name = parts[-1]
        return folder_name
    elif "/" in path:
        parts = path.split("/")
        folder_name = parts[-1]
        return folder_name
    else:
        return path


def combined_generator(origin_generator: Generator, *args: list[Generator]):
    """
    Combine multiple generators into one generator.

    Args:
        origin_generator (generator): The original generator.
        *args (generator): The generators to be combined.

    Returns:
        generator: The combined generator.
    """
    for item in origin_generator:
        yield item

    for arg in args:
        for item in arg:
            yield item
