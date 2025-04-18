#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# Copyright (c) 2024 Lanzhou University
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import os
import re

import time
import shutil
import tempfile
import importlib.resources
from importlib.resources.abc import Traversable

from typing import Generator, Optional, TypeVar, Callable, Iterable
from liscopelens.constants import Settings


T = TypeVar("T")


def timer(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        ret = func(*args, **kwargs)
        cons = time.time() - start
        if cons > 1e-2:
            print(f"{func.__name__} cost {cons} seconds")
        if cons > 2:
            raise ValueError(f"{func.__name__} cost {cons} seconds")
        return ret

    return wrapper


def load_resource(filename: str, package_name: Optional[str] = None, source_name: Optional[str] = None) -> str:
    """
    Load a file from the resources of a package

    Args:
        filename (str): the file name
        package_name (str): the package name
        source_name (str): the source name

    Returns:
        str: the content of the file
    """
    if source_name is None:
        source_name = Settings.RESOURCE_NAME

    if package_name is None:
        package_name = f"{Settings.PACKAGE_NAME}.{source_name}"

    resources = importlib.resources.files(package_name)
    with resources.joinpath(filename).open("r", encoding="utf8") as f:
        return f.read()


def is_file_in_resources(
    filename: str, package_name: Optional[str] = None, resource_name: Optional[str] = None
) -> bool:
    """
    Check if a file is in the resources of a package

    Args:
        filename (str): the file name
        package_name (str): the package name
        source_name (str): the source name

    Returns:
        bool: whether the file is in the resources of the package
    """
    if resource_name is None:
        resource_name = Settings.RESOURCE_NAME

    if package_name is None:
        package_name = f"{Settings.PACKAGE_NAME}.{resource_name}"

    try:
        return importlib.resources.files(package_name).joinpath(filename).is_file()
    except ModuleNotFoundError:
        return False


def write_to_resources(filename: str, content: str, package_name: Optional[str] = None):
    """
    Write a file to the resources of a package

    Args:
        filename (str): the file name
        content (str): the content of the file
        package_name (Optional[str]): the name of the package containing resources

    Returns:
        None, but write the file to the resources of the package
    """

    if package_name is None:
        package_name = f"{Settings.PACKAGE_NAME}.{Settings.RESOURCE_NAME}"

    temp_dir = tempfile.mkdtemp()

    try:
        temp_file = os.path.join(temp_dir, filename)
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(content)

        # 获取资源文件夹的路径
        with importlib.resources.path(package_name, "") as destination:
            shutil.copy(temp_file, os.path.join(destination, filename))

    finally:
        shutil.rmtree(temp_dir)


def get_resource_path(
    file_name: Optional[str] = None, package_name: Optional[str] = None, resource_name: Optional[str] = None
) -> Traversable:
    """
    Get the path to the resources of a package

    Args:
        package_name (str): the package name
        resource_name (str): the resource name

    Returns:
        str: the path to the resources of the package
    """

    package_name = package_name if package_name else Settings.PACKAGE_NAME
    resource_name = resource_name if resource_name else Settings.RESOURCE_NAME

    resource_path = f"{package_name}.{resource_name}"

    if file_name:
        return importlib.resources.files(resource_path).joinpath(file_name)

    return importlib.resources.files(resource_path)


def delete_duplicate_str(data: list[str]) -> list[str]:
    """
    Delete duplicate strings in a list

    Args:
        data (list[str]): the input list

    Returns:
        list[str]: the list without duplicate strings

    ! deprecated in next version
    """
    # 使用集合去除重复项
    unique_data = list(set(data))
    return unique_data


def find_duplicate_keys(dict_a: dict[str, T], dict_b: dict[str, T]) -> set[str]:
    """
    TODO: Add docstring
    """
    return set(dict_a.keys()) & set(dict_b.keys())


def zip_with_none(list_a: list[T], list_b: list[T]):
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


def combined_generator(origin_generator: Generator | list, *args: list[Generator]):
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


def extract_version(spdx_id: str) -> str | None:
    """
    Extract the version number from a license ID.

    Args:
        spdx_id (str): The license ID.

    Returns:
        str | None: The version number
    """
    version_pattern = r"(\d+\.\d+(\.\d+)?)"
    match = re.search(version_pattern, spdx_id)
    if match:
        return match.group(1)
    return None


def normalize_version(version: str) -> list[int]:
    """
    Normalize the version number. Let version str could be compared.

    Args:
        version (str): The version number.

    Returns:
        list[int]: The normalized version number.
    """
    return [int(x) for x in re.sub(r"(\.0+)*$", "", version).split(".")]


def find_all_versions(spdx_idx: str, licenses: Iterable[str], filter_func: Optional[Callable] = None) -> list[str]:
    """
    Find all versions of a license.

    Args:
        spdx_idx (str): The SPDX ID of the license.
        licenses (list[str]): The list of licenses.
        filter_func (callable): The filter function.

    Returns:
        list[str]: The list of versions of the license.
    """
    prefix = spdx_idx.split("-")[0]
    return [
        license for license in licenses if license.split("-")[0] == prefix and (not filter_func or filter_func(license))
    ]


def set2list(data: set) -> list:
    """
    Convert a set to a list.

    Args:
        data (set): The input set.

    Returns:
        list: The output list.
    """
    if isinstance(data, (set, frozenset)):
        return [set2list(item) for item in data]
    elif isinstance(data, dict):
        return {key: set2list(value) for key, value in data.items()}
    elif isinstance(data, (list, tuple)):
        converted = (set2list(item) for item in data)
        return list(converted) if isinstance(data, list) else tuple(converted)
    else:
        return data
