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
from pathlib import Path
from collections import defaultdict


def scan_dir(
    dir_path: Path | str,
    root_path: Path | str | None = None,
    suffix: tuple[str, ...] = (),
    stem_dict: defaultdict[str, list[Path]] | None = None,
) -> defaultdict[str, list[Path]]:
    """Scan a directory and return all files in the directory.

    Args:
        dir_path: Path | str, the directory to scan
        root_path: Path | str, the root path of the directory
        suffix: tuple[str, ...], file suffixes to filter
        stem_dict: defaultdict to update, creates new one if None

    Returns:
        defaultdict[str, list[Path]]: all files grouped by stem
    """
    if stem_dict is None:
        stem_dict = defaultdict(list)

    if isinstance(dir_path, str):
        if dir_path.startswith(("//", "\\\\")):  # GN json path
            dir_path = dir_path[2:]
        dir_path = Path(dir_path)

    if isinstance(root_path, str):
        root_path = Path(root_path)

    if root_path is None:
        tgt_path = dir_path.resolve()
    else:
        tgt_path = (root_path / dir_path).resolve()

    if not tgt_path.exists():
        return stem_dict

    if not tgt_path.is_dir():
        return stem_dict

    for fp in os.scandir(tgt_path):
        if fp.is_file() and (not suffix or fp.name.endswith(suffix)):
            path = Path(fp.path).resolve()
            stem_dict[path.stem].append(path)

    return stem_dict


def path_endswith(p: Path, suffix: Path) -> bool:
    """Check if path p ends with suffix.

    Args:
        p (Path): The path to check.
        suffix (Path): The suffix to check against.

    Returns:
        bool: True if p ends with suffix, False otherwise.
    """ 
    return p.parts[-len(suffix.parts):] == suffix.parts


if __name__ == "__main__":
    print(scan_dir("//applications/standard/call", "D:\\MyProject\\lict-one-click\\oh-4.0\\", suffix=(".md", ".json")))
