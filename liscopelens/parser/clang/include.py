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
import warnings

from typing import Optional

from liscopelens.parser.base import BaseParser
from liscopelens.utils.graph import GraphManager
from liscopelens.utils.scaffold import extract_folder_name


class IncludeParser(BaseParser):
    vertex_parser = []
    file_types = ("c", "h")
    arg_table = {
        "--root_path": {"type": str, "help": "the root path of the project", "group": "a"},
    }

    @staticmethod
    def parse_includes(file_content: list) -> tuple[list[str], list[str]]:
        included_one = []
        included_two = []
        include_pattern_one = re.compile(r"#include\s*[<](.*?)[>]")
        include_pattern_two = re.compile(r'#include\s*["](.*?)["]')
        try:
            for line in file_content:
                match_one = include_pattern_one.search(line)
                match_two = include_pattern_two.search(line)
                if match_one:
                    included_file = match_one.group(1)
                    included_one.append(included_file)
                if match_two:
                    included_file = match_two.group(1)
                    included_two.append(included_file)
            return included_one, included_two
        except re.error as e:
            print(e)

    @staticmethod
    def calculate_abs_dep_path(base_absolute_path: str, relative_dependency_path: str) -> str:
        """
        Calculates the absolute path of a dependency based on a given base absolute path and a relative dependency path.

        Args:
            base_absolute_path (str): The absolute path of the base file.
            relative_dependency_path (str): The relative path of the dependency from the base file.

        Returns:
            str: The absolute path of the dependency.
        """
        # Normalize the paths to handle different separators (e.g., / or \)
        base_absolute_path = os.path.normpath(base_absolute_path)
        relative_dependency_path = os.path.normpath(relative_dependency_path)
        absolute_dependency_path = os.path.join(os.path.dirname(base_absolute_path), relative_dependency_path)
        absolute_dependency_path = os.path.abspath(absolute_dependency_path)
        return absolute_dependency_path

    def parse_clang(self, file_content: list) -> tuple[list[str], list[str]]:
        """
        Process files and call parse_includes or parse_cmake based on different file names.
        Args:
            file_content:File content,stored by list

        Returns:
            tuple[list[str], list[str]]:
                - If the file is processed with `parse_includes`:
                    - included_One (list[str]): list of included files(<>).
                    - included_Two (list[str]): list of included files("").
        """
        print("Parsing .c or .h file...")
        return self.parse_includes(file_content)

    def parse(self, project_path: str, context: Optional[GraphManager] = None) -> GraphManager:
        root_vertex = self.create_vertex(project_path)
        context.add_node(root_vertex)
        if self.args.root_path is None:
            warnings.warn("can not find root path")
        else:
            print(self.args.root_path)
        for root, dirs, files in os.walk(self.args.root_path):
            # 遍历当前目录下的文件
            for file in files:
                # 读取每个文件的内容
                file_path = os.path.join(root, file)
                my_file = open(file_path, "r", encoding="utf-8", errors="replace")
                file_content = my_file.readlines()
                my_file.close()
                # 为文件创立一个节点，节点有四个属性：名称，内容，父亲，许可证。为保证节点的唯一性，添加父亲的名称
                file_vertex = self.create_vertex(file_path, content=file_content, father=root, license=None)
                context.add_node(file_vertex)
                sub_edge = self.create_edge(root, file_path, label="sub")
                context.add_edge(sub_edge)
                if file.endswith(self.file_types):
                    self.vertex_parser.append(file_vertex)
            # 递归遍历子目录
            for subdir in dirs:
                subdir_path = os.path.join(root, subdir)
                subdir_vertex = self.create_vertex(subdir_path, father=root)
                context.add_node(subdir_vertex)
                sub_edge = self.create_edge(root, subdir_path, label="sub")
                context.add_edge(sub_edge)
        for v in self.vertex_parser:
            includeone, includetwo = self.parse_clang(v["content"])
            for file in includeone:
                vertex = self.create_vertex(file)
                context.add_node(vertex)
                edge = self.create_edge(v.label, file, label="include<>")
                context.add_edge(edge)
                print(v.label + "---------->" + file)
            for file in includetwo:
                if "../" in file:
                    name = self.calculate_abs_dep_path(v.label, file)
                    edge = self.create_edge(v.label, name, label="include" "")
                    context.add_edge(edge)
                    print(v.label + "---------->" + name)
                else:
                    # bug return of self.graph.nodes is str
                    vertex_list = context.nodes
                    file = extract_folder_name(file)
                    find_flags = 0
                    for vertex in vertex_list:
                        if extract_folder_name(vertex) == file:
                            edge = self.create_edge(v.label, vertex, label="include" "")
                            context.add_edge(edge)
                            print(v.label + "---------->" + vertex)
                            find_flags = 1
                            break
                    if not find_flags:
                        print("external dependency")
                        edge = self.create_edge(v.label, file, label="include" " external")
                        context.add_edge(edge)
                        print(v.label + "---------->" + file)
        return context
