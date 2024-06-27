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

import json
from lict.parser.base import BaseParser
from lict.utils.graph import GraphManager


from rich.progress import track


class GnParser(BaseParser):
    gn_dict = {"deps": {}}
    visted = set()
    arg_table = {
        "--gn_tool": {"type": str, "help": "the path of the gn tool in executable form", "group": "gn"},
        "--gn_file": {"type": str, "help": "the path of the gn deps graph output file", "group": "gn"},
    }

    def parse(self, project_path: str, context: GraphManager = None) -> GraphManager:
        if self.args.gn_file is not None:
            with open(file=self.args.gn_file, mode="r", encoding="UTF-8") as file:
                gn_data = json.load(file)
                file.close()
                targets = gn_data["targets"]
                for key, value in track(targets.items(), "Parsing GN file..."):
                    if (key, value["type"]) not in self.visted:
                        vertex = self.create_vertex(key, type=value["type"])
                        context.add_node(vertex)
                        self.visted.add((key, value["type"]))
                        if value.get("deps", None):
                            for dep in value["deps"]:
                                dep_type = targets[dep]["type"]
                                if (dep, dep_type) not in self.visted:
                                    vertex_dep = self.create_vertex(dep, type=dep_type)
                                    context.add_node(vertex_dep)
                                    self.visted.add((dep, dep_type))
                                    sub_edge = self.create_edge(key, dep, label="deps")
                                    context.add_edge(sub_edge)
                                else:
                                    sub_edge = self.create_edge(key, dep, label="deps")
                                    context.add_edge(sub_edge)
                        if value.get("sources", None):
                            for code in value["sources"]:
                                if code not in self.visted:
                                    vertex = self.create_vertex(code, type="code")
                                    self.visted.add(code)
                                    context.add_node(vertex)
                                    sub_edge = self.create_edge(key, code, label="sources")
                                    context.add_edge(sub_edge)
                                else:
                                    sub_edge = self.create_edge(key, code, label="sources")
                                    context.add_edge(sub_edge)
                    else:
                        if value.get("deps", None):
                            for dep in value["deps"]:
                                dep_type = targets[dep]["type"]
                                if (dep, dep_type) not in self.visted:
                                    vertex_dep = self.create_vertex(dep, type=dep_type)
                                    context.add_node(vertex_dep)
                                    self.visted.add((dep, dep_type))
                                    sub_edge = self.create_edge(key, dep, label="deps")
                                    context.add_edge(sub_edge)
                                else:
                                    sub_edge = self.create_edge(key, dep, label="deps")
                                    context.add_edge(sub_edge)
                        if value.get("sources", None):
                            for code in value["sources"]:
                                if code not in self.visted:
                                    vertex = self.create_vertex(code, type="code")
                                    self.visted.add(code)
                                    context.add_node(vertex)
                                    sub_edge = self.create_edge(key, code, label="sources")
                                    context.add_edge(sub_edge)
                                else:
                                    sub_edge = self.create_edge(key, code, label="sources")
                                    context.add_edge(sub_edge)
        return context
