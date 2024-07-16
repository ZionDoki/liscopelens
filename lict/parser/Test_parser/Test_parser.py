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
import toml
import os
import networkx as nx
from lict.utils.graph import GraphManager
from lict.parser.base import BaseParser
from lict.utils.structure import Config, SPDXParser
from lict.parser.compatible import BaseCompatiblityParser
from lict.parser.propagate import BasePropagateParser
from lict.parser.exception import BaseExceptionParser
import json
import argparse


class TestRule:
    def __init__(self, graph: GraphManager):
        """
        TestRule for testing lict.

        Attributes:
            graph (GraphManager): The graph to be inserted licenses.

        Methods:
            rule_same_component: Insert the license into the same component.
            rule_static: Insert the license into the static library.
            rule_condition: Insert the condition license into the dependency graph.
            rule_exe: Insert the license into the dependency graph, with the license being isolated through process separation.
            rule_brother_node: Insert the license into the sibling nodes.
            test: Main method.
        """

        self.graph = graph
        root = self.graph.root_nodes[0]
        self.graph.modify_node_attribute(root, "type", "executable")

    def rule_same_component(self, license_a, license_b):
        an_node = None
        spdx = SPDXParser()
        for node in self.graph.nodes:
            if self.graph.graph.out_degree(node) == 0:
                n = self.graph.query_node_by_label(node)
                if n["type"] == "code":
                    n["licenses"] = spdx(license_a) & spdx(license_b)
                    nx.set_node_attributes(self.graph.graph, {node: n})
                    an_node = node
                    break
        for node in self.graph.nodes:
            if self.graph.graph.out_degree(node) == 0:
                n = self.graph.query_node_by_label(node)
                n["licenses"] = spdx(license_a) & spdx(license_b)
                nx.set_node_attributes(self.graph.graph, {node: n})
                an_node = node
                break
        return self.graph, an_node

    def rule_static(self, license_a, license_b):
        spdx = SPDXParser()
        pair = self.graph.get_sibling_pairs()
        an = pair[0]
        an_node_a = an_node_b = None
        if self.graph.is_leaf(an[0]):
            node = self.graph.query_node_by_label(an[0])
            new = spdx(license_a)
            node["licenses"] = new
            nx.set_node_attributes(self.graph.graph, {an[0]: node})
            an_node_a = an[0]
            if node["type"] != "code":
                self.graph.modify_node_attribute(an[0], "type", "code")
        else:
            self.graph.modify_node_attribute(an[0], "type", "static_library")
            successors = list(self.graph.successors(an[0]))
            if successors:
                child = successors[0]
                child_node = self.graph.query_node_by_label(child)
                new = spdx(license_a)
                child_node["licenses"] = new
                nx.set_node_attributes(self.graph.graph, {child: child_node})
                an_node_a = child
                if child_node["type"] != "code":
                    self.graph.modify_node_attribute(child, "type", "code")

        if self.graph.is_leaf(an[1]):
            node = self.graph.query_node_by_label(an[1])
            new = spdx(license_b)
            node["licenses"] = new
            nx.set_node_attributes(self.graph.graph, {an[1]: node})
            an_node_b = an[1]
            if node["type"] != "code":
                self.graph.modify_node_attribute(an[1], "type", "code")
        else:
            self.graph.modify_node_attribute(an[1], "type", "static_library")
            successors = list(self.graph.successors(an[1]))
            if successors:
                child = successors[0]
                child_node = self.graph.query_node_by_label(child)
                new = spdx(license_b)
                child_node["licenses"] = new
                nx.set_node_attributes(self.graph.graph, {child: child_node})
                an_node_b = child
                if child_node["type"] != "code":
                    self.graph.modify_node_attribute(child, "type", "code")
        return self.graph, an_node_a, an_node_b

    def rule_condition(self, license_a, license_b):
        pair = self.graph.get_sibling_pairs()
        an = pair[0]
        an_node_a = an_node_b = None
        if self.graph.is_leaf(an[0]):
            node = self.graph.query_node_by_label(an[0])
            spdx = SPDXParser()
            new = spdx(license_a)
            node["licenses"] = new
            nx.set_node_attributes(self.graph.graph, {an[0]: node})
            an_node_a = an[0]
            self.graph.modify_node_attribute(an[0], "type", "shared_library")
        else:
            self.graph.modify_node_attribute(an[0], "type", "shared_library")
            successors = list(self.graph.successors(an[0]))
            if successors:
                child = successors[0]
                child_node = self.graph.query_node_by_label(child)
                spdx = SPDXParser()
                new = spdx(license_a)
                child_node["licenses"] = new
                nx.set_node_attributes(self.graph.graph, {child: child_node})
                an_node_a = child
                if child_node["type"] != "shared_library":
                    self.graph.modify_node_attribute(child, "type", "shared_library")

        if self.graph.is_leaf(an[1]):
            node = self.graph.query_node_by_label(an[1])
            spdx = SPDXParser()
            new = spdx(license_b)
            node["licenses"] = new
            nx.set_node_attributes(self.graph.graph, {an[1]: node})
            an_node_b = an[1]
            if node["type"] != "shared_library":
                self.graph.modify_node_attribute(an[1], "type", "shared_library")
        else:
            self.graph.modify_node_attribute(an[1], "type", "shared_library")
            successors = list(self.graph.successors(an[1]))
            if successors:
                child = successors[0]
                child_node = self.graph.query_node_by_label(child)
                spdx = SPDXParser()
                new = spdx(license_b)
                child_node["licenses"] = new
                nx.set_node_attributes(self.graph.graph, {child: child_node})
                an_node_b = child
                if child_node["type"] != "shared_library":
                    self.graph.modify_node_attribute(child, "type", "shared_library")

        return self.graph, an_node_a, an_node_b

    def rule_exe(self, license_a, license_b):
        root = self.graph.root_nodes
        an = root[0]  # root_node
        an_node_a = an_node_b = None
        successors = list(self.graph.successors(an))
        if successors[0]:
            child = successors[0]
            if self.graph.is_leaf(child):
                child_node = self.graph.query_node_by_label(child)
                spdx = SPDXParser()
                new = spdx(license_a)
                child_node["licenses"] = new
                nx.set_node_attributes(self.graph.graph, {child: child_node})
                an_node_a = child
                self.graph.modify_node_attribute(child, "type", "executable")
            else:
                self.graph.modify_node_attribute(child, "type", "executable")
                next_successors_node = list(self.graph.successors(child))
                child = next_successors_node[0]
                child_node = self.graph.query_node_by_label(child)
                spdx = SPDXParser()
                new = spdx(license_a)
                child_node["licenses"] = new
                nx.set_node_attributes(self.graph.graph, {child: child_node})
                an_node_a = child
                self.graph.modify_node_attribute(child, "type", "static_library")
        else:
            print("进程隔离规则插入失败！")

        if successors[1]:
            child = successors[1]
            if self.graph.is_leaf(child):
                child_node = self.graph.query_node_by_label(child)
                spdx = SPDXParser()
                new = spdx(license_b)
                child_node["licenses"] = new
                nx.set_node_attributes(self.graph.graph, {child: child_node})
                an_node_b = child
                self.graph.modify_node_attribute(child, "type", "executable")
            else:
                self.graph.modify_node_attribute(child, "type", "executable")
                successors_node1 = list(self.graph.successors(child))
                child = successors_node1[0]
                child_node = self.graph.query_node_by_label(child)
                spdx = SPDXParser()
                new = spdx(license_b)
                child_node["licenses"] = new
                nx.set_node_attributes(self.graph.graph, {child: child_node})
                an_node_b = child
                self.graph.modify_node_attribute(child, "type", "static_library")
        else:
            print("进程隔离规则插入失败！")
        return self.graph, an_node_a, an_node_b

    def rule_brother_node(self, license_a, license_b):
        child_node = self.graph.query_node_by_label("node3")
        spdx = SPDXParser()
        new = spdx(license_a)
        child_node["licenses"] = new
        nx.set_node_attributes(self.graph.graph, {"node3": child_node})

        child_node = self.graph.query_node_by_label("node4")
        spdx = SPDXParser()
        new = spdx(license_b)
        child_node["licenses"] = new
        nx.set_node_attributes(self.graph.graph, {"node4": child_node})
        return self.graph, "node3", "node4"

    def test(self, rule, folder_name, results, usr_conflicts, license_a, license_b, blacklist):
        config = Config.from_toml(path="lict/config/default.toml")
        config.blacklist = blacklist or []
        new_graph = node = node_a = node_b = None
        if rule == "same_component":
            new_graph, node = self.rule_same_component(license_a, license_b)
        if rule == "static":
            new_graph, node_a, node_b = self.rule_static(license_a, license_b)
        if rule == "condition":
            new_graph, node_a, node_b = self.rule_condition(license_a, license_b)
        if rule == "exe":
            new_graph, node_a, node_b = self.rule_exe(license_a, license_b)
        if rule == "brother":
            new_graph, node_a, node_b = self.rule_brother_node(license_a, license_b)

        if nx.is_frozen(new_graph.graph):
            new_graph.graph = new_graph.graph.copy()
        an = BaseExceptionParser(argparse.Namespace(blacklist=blacklist), config=config).parse("test",
                                                                                               new_graph)
        an = BasePropagateParser(argparse.Namespace(), config=config).parse("test", an)
        an = BaseCompatiblityParser(argparse.Namespace(output=f"results/{folder_name}/"), config=config).parse("test",
                                                                                                               an)
        an.save(f"{results}/{folder_name}/graph_rule_an_{rule}.gml")

        with open(f'{results}/{folder_name}/results.json', 'r', encoding='utf-8') as file:
            results = json.load(file)
        files_set = []
        conflicts = []
        for key, value in results.items():
            if 'files' in value:
                files_set.append(value['files'])
            if 'conflicts' in value:
                conflicts.append(value["conflicts"])
        unique_conflicts = []
        for i in conflicts:
            for j in i:
                unique_conflicts.append(j)

        unique_conflicts = [list(t) for t in set(tuple(_) for _ in unique_conflicts)]
        flag = False
        if rule == "same_component":
            an_node = [[node]]
            if usr_conflicts:
                unique_conflicts = {frozenset(sublist) for sublist in unique_conflicts}
                usr_conflicts = {frozenset(sublist) for sublist in usr_conflicts}
                an_node = {frozenset(sublist) for sublist in an_node}
                files_set = {frozenset(sublist) for sublist in files_set}
                if usr_conflicts == unique_conflicts and an_node == files_set:
                    flag = True
                return flag
            else:
                if usr_conflicts == unique_conflicts:
                    flag = True
                return flag

        elif rule == "static":
            an_node = [["node3", "node5"]]
            if usr_conflicts:
                unique_conflicts = {frozenset(sublist) for sublist in unique_conflicts}
                usr_conflicts = {frozenset(sublist) for sublist in usr_conflicts}
                an_node = {frozenset(sublist) for sublist in an_node}
                files_set = {frozenset(sublist) for sublist in files_set}
                if usr_conflicts == unique_conflicts and an_node == files_set:
                    flag = True
                return flag
            else:
                if usr_conflicts == unique_conflicts:
                    flag = True
                return flag

        elif rule == "brother":
            an_node = [["node3", "node4"]]
            if usr_conflicts:
                unique_conflicts = {frozenset(sublist) for sublist in unique_conflicts}
                usr_conflicts = {frozenset(sublist) for sublist in usr_conflicts}
                an_node = {frozenset(sublist) for sublist in an_node}
                files_set = {frozenset(sublist) for sublist in files_set}
                if usr_conflicts == unique_conflicts and an_node == files_set:
                    flag = True
                return flag
            else:
                if usr_conflicts == unique_conflicts:
                    flag = True
                return flag

        else:
            an_node = []
            flag = False
            an_node.append(["node3", "node5"])
            usr_conflicts = []
            if usr_conflicts == unique_conflicts:
                flag = True
            return flag


class TestParser(BaseParser):
    arg_table = {
        "--init_file": {"type": str, "help": "the path of the graph init file", "group": "test"},
        "--user_config_file": {"type": str, "help": "the path of the config file", "group": "test"},
        "--results": {"type": str, "help": "the path of the config file", "group": "test"},
    }

    def parse(self, project_path: str, context: GraphManager):
        with open(self.args.user_config_file, "r") as f:
            user_config = toml.load(f)
            f.close()
        subgraph_list = context.get_subgraph_depth()
        # processing
        answer = {}
        try:
            os.makedirs(self.args.results)
        except FileExistsError:
            pass
        for key, value in user_config.items():
            print(key)
            folder_name = str(key)
            answer[folder_name] = []
            try:
                os.makedirs(f"{self.args.results}/{folder_name}")
            except FileExistsError:
                pass
            license_a = value['license_A']
            license_b = value['license_B']
            condition = value['condition']
            conflicts = value['conflicts']
            blacklist = value.get('blacklist', None)
            if "same_component" in condition:
                subgraph = GraphManager(self.args.init_file)
                subgraph.graph = subgraph.graph.copy()
                test = TestRule(subgraph)
                flag = test.test("same_component", folder_name, self.args.results, conflicts, license_a, license_b,
                                 blacklist)
                if not flag:
                    print(f"\033[91m{folder_name}在same_component判断错误\033[0m")
            if "static" in condition:

                subgraph = GraphManager(self.args.init_file)
                subgraph.graph = subgraph.graph.copy()
                test = TestRule(subgraph)
                flag = test.test("static", folder_name, self.args.results, conflicts, license_a, license_b, blacklist)
                if not flag:
                    print(f"\033[91m{folder_name}在static判断错误\033[0m")
            if "condition" in condition:
                subgraph = GraphManager(self.args.init_file)
                subgraph.graph = subgraph.graph.copy()
                test = TestRule(subgraph)

                flag = test.test("condition", folder_name, self.args.results, conflicts, license_a, license_b,
                                 blacklist)
                if not flag:
                    print(f"\033[91m{folder_name}在condition判断错误\033[0m")
            if "exe" in condition:
                subgraph = GraphManager(self.args.init_file)
                subgraph.graph = subgraph.graph.copy()
                test = TestRule(subgraph)
                flag = test.test("exe", folder_name, self.args.results, conflicts, license_a, license_b, blacklist)
                if not flag:
                    print(f"\033[91m{folder_name}在exe判断错误\033[0m")

            if "brother" in condition:
                subgraph = GraphManager(self.args.init_file)
                subgraph.graph = subgraph.graph.copy()
                test = TestRule(subgraph)
                flag = test.test("brother", folder_name, self.args.results, conflicts, license_a, license_b, blacklist)
                if not flag:
                    print(f"\033[91m{folder_name}在brother判断错误\033[0m")

        return context
