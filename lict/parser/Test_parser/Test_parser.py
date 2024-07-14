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
from lict.utils.structure import Config, DualUnit, DualLicense, SPDXParser
from lict.parser.compatible import BaseCompatiblityParser
from rich.progress import track
import argparse


def insert_graph(graph_a: GraphManager, graph_b: GraphManager) -> GraphManager:
    nodes_a = graph_a.nodes
    for node_a in nodes_a:
        source_node = graph_a.query_node_by_label(node_a)
        target_node = graph_b.query_node_by_label(node_a)
        target_node["type"] = source_node["type"]
        if "licenses" in source_node:
            target_node["licenses"] = source_node["licenses"]
        nx.set_node_attributes(graph_b.graph, {node_a: target_node})


class TestRule:
    def __init__(self, graph: GraphManager):
        self.graph = graph
        root = self.graph.root_nodes[0]
        self.graph.modify_node_attribute(root, "type", "executable")

    # A，B位于同一组件
    def rule_a(self, license_a, license_b):
        an_node = None
        for node in self.graph.nodes:
            if self.graph.graph.out_degree(node) == 0:
                n = self.graph.query_node_by_label(node)
                if n["type"] == "code":
                    new = DualLicense()
                    new_group = set()
                    new_group.add(DualUnit(license_a, filename=node))
                    new_group.add(DualUnit(license_b, filename=node))
                    new.add(tuple(new_group))
                    n["licenses"] = new
                    nx.set_node_attributes(self.graph.graph, {node: n})
                    an_node = node
                    break
        for node in self.graph.nodes:
            if self.graph.graph.out_degree(node) == 0:
                n = self.graph.query_node_by_label(node)
                new = DualLicense()
                new_group = set()
                new_group.add(DualUnit(license_a, filename=node))
                new_group.add(DualUnit(license_b, filename=node))
                new.add(tuple(new_group))
                n["licenses"] = new
                nx.set_node_attributes(self.graph.graph, {node: n})
                an_node = node
                break
        return self.graph, an_node

    # A,B位于兄弟结点且可传播(静态链接)
    def rule_b(self, license_a, license_b):
        pair = self.graph.get_sibling_pairs()  # 获取包含叶子节点的兄弟节点对
        an = pair[0]  # 获取第一个兄弟节点对

        if self.graph.is_leaf(an[0]):
            node = self.graph.query_node_by_label(an[0])
            if ("and" in license_a) or ("with" in license_a) or ("or" in license_a):
                spdx = SPDXParser()
                new = spdx(license_a, an[0], expand=True)
            else:
                new = DualLicense()
                new_group = set()
                new_group.add(DualUnit(license_a, filename=an[0]))
                new.add(tuple(new_group))
            node["licenses"] = new
            nx.set_node_attributes(self.graph.graph, {an[0]: node})
            an_node_A = an[0]
            if node["type"] != "code":
                self.graph.modify_node_attribute(an[0], "type", "code")
        else:
            self.graph.modify_node_attribute(an[0], "type", "static_library")
            successors = list(self.graph.successors(an[0]))  # 转换生成器为列表
            if successors:
                chid = successors[0]
                chid_node = self.graph.query_node_by_label(chid)
                if ("and" in license_a) or ("with" in license_a) or ("or" in license_a):
                    spdx = SPDXParser()
                    new = spdx(license_a, an[0], expand=True)
                else:
                    new = DualLicense()
                    new_group = set()
                    new_group.add(DualUnit(license_a, filename=an[0]))
                    new.add(tuple(new_group))
                chid_node["licenses"] = new
                nx.set_node_attributes(self.graph.graph, {chid: chid_node})
                an_node_A = chid
                if chid_node["type"] != "code":
                    self.graph.modify_node_attribute(chid, "type", "code")

        if self.graph.is_leaf(an[1]):
            node = self.graph.query_node_by_label(an[1])
            if ("and" in license_b) or ("with" in license_b) or ("or" in license_b):
                spdx = SPDXParser()
                new = spdx(license_b, an[1], expand=True)
            else:
                new = DualLicense()
                new_group = set()
                new_group.add(DualUnit(license_b, filename=an[1]))
                new.add(tuple(new_group))
            node["licenses"] = new
            nx.set_node_attributes(self.graph.graph, {an[1]: node})
            an_node_B = an[1]
            if node["type"] != "code":
                self.graph.modify_node_attribute(an[1], "type", "code")
        else:
            self.graph.modify_node_attribute(an[1], "type", "static_library")
            successors = list(self.graph.successors(an[1]))  # 转换生成器为列表
            if successors:
                chid = successors[0]
                chid_node = self.graph.query_node_by_label(chid)
                if ("and" in license_b) or ("with" in license_b) or ("or" in license_b):
                    spdx = SPDXParser()
                    new = spdx(license_b, an[1], expand=True)
                else:
                    new = DualLicense()
                    new_group = set()
                    new_group.add(DualUnit(license_b, filename=an[1]))
                    new.add(tuple(new_group))
                chid_node["licenses"] = new
                nx.set_node_attributes(self.graph.graph, {chid: chid_node})
                an_node_B = chid
                if chid_node["type"] != "code":
                    self.graph.modify_node_attribute(chid, "type", "code")

        return self.graph, an_node_A, an_node_B

    # 位于不同节点且不可传播(动态链接)
    def rule_c(self, license_a, license_b):
        pair = self.graph.get_sibling_pairs()  # 获取包含叶子节点的兄弟节点对
        an = pair[0]  # 获取第一个兄弟节点对

        if self.graph.is_leaf(an[0]):
            node = self.graph.query_node_by_label(an[0])
            new = DualLicense()
            new_group = set()
            new_group.add(DualUnit(license_a, filename=an[0]))
            new.add(tuple(new_group))
            node["licenses"] = new
            nx.set_node_attributes(self.graph.graph, {an[0]: node})
            an_node_A = an[0]
            self.graph.modify_node_attribute(an[0], "type", "shared_library")
        else:
            self.graph.modify_node_attribute(an[0], "type", "shared_library")
            successors = list(self.graph.successors(an[0]))  # 转换生成器为列表
            if successors:
                chid = successors[0]
                chid_node = self.graph.query_node_by_label(chid)
                new = DualLicense()
                new_group = set()
                new_group.add(DualUnit(license_a, filename=chid))
                new.add(tuple(new_group))
                chid_node["licenses"] = new
                nx.set_node_attributes(self.graph.graph, {chid: chid_node})
                an_node_A = chid
                if chid_node["type"] != "shared_library":
                    self.graph.modify_node_attribute(chid, "type", "shared_library")

        if self.graph.is_leaf(an[1]):
            node = self.graph.query_node_by_label(an[1])
            new = DualLicense()
            new_group = set()
            new_group.add(DualUnit(license_b, filename=an[1]))
            new.add(tuple(new_group))
            node["licenses"] = new
            nx.set_node_attributes(self.graph.graph, {an[1]: node})
            an_node_B = an[1]
            if node["type"] != "shared_library":
                self.graph.modify_node_attribute(an[1], "type", "shared_library")
        else:
            self.graph.modify_node_attribute(an[1], "type", "shared_library")
            successors = list(self.graph.successors(an[1]))  # 转换生成器为列表
            if successors:
                chid = successors[0]
                chid_node = self.graph.query_node_by_label(chid)
                new = DualLicense()
                new_group = set()
                new_group.add(DualUnit(license_b, filename=chid))
                new.add(tuple(new_group))
                chid_node["licenses"] = new
                nx.set_node_attributes(self.graph.graph, {chid: chid_node})
                an_node_B = chid
                if chid_node["type"] != "shared_library":
                    self.graph.modify_node_attribute(chid, "type", "shared_library")

        return self.graph, an_node_A, an_node_B

    # exe程序隔离
    def rule_d(self, license_a, license_b):
        root = self.graph.root_nodes  # 获取根节点任意往下走两个
        an = root[0]  # 根节点
        successors = list(self.graph.successors(an))

        if successors[0]:
            child = successors[0]
            if self.graph.is_leaf(child):
                chid_node = self.graph.query_node_by_label(child)
                new = DualLicense()
                new_group = set()
                new_group.add(DualUnit(license_a, filename=child))
                new.add(tuple(new_group))
                chid_node["licenses"] = new
                nx.set_node_attributes(self.graph.graph, {child: chid_node})
                an_node_A = child
                self.graph.modify_node_attribute(child, "type", "executable")
            else:
                self.graph.modify_node_attribute(child, "type", "executable")
                successors_node1 = list(self.graph.successors(child))
                child = successors_node1[0]
                chid_node = self.graph.query_node_by_label(child)
                new = DualLicense()
                new_group = set()
                new_group.add(DualUnit(license_a, filename=child))
                new.add(tuple(new_group))
                chid_node["licenses"] = new
                nx.set_node_attributes(self.graph.graph, {child: chid_node})
                an_node_A = child
                self.graph.modify_node_attribute(child, "type", "static_library")
        else:
            print("进程隔离规则插入失败！")

        if successors[1]:
            child = successors[1]
            if self.graph.is_leaf(child):
                chid_node = self.graph.query_node_by_label(child)
                new = DualLicense()
                new_group = set()
                new_group.add(DualUnit(license_b, filename=child))
                new.add(tuple(new_group))
                chid_node["licenses"] = new
                nx.set_node_attributes(self.graph.graph, {child: chid_node})
                an_node_B = child
                self.graph.modify_node_attribute(child, "type", "executable")
            else:
                self.graph.modify_node_attribute(child, "type", "executable")
                successors_node1 = list(self.graph.successors(child))
                child = successors_node1[0]
                chid_node = self.graph.query_node_by_label(child)
                new = DualLicense()
                new_group = set()
                new_group.add(DualUnit(license_b, filename=child))
                new.add(tuple(new_group))
                chid_node["licenses"] = new
                nx.set_node_attributes(self.graph.graph, {child: chid_node})
                an_node_B = child
                self.graph.modify_node_attribute(child, "type", "static_library")
        else:
            print("进程隔离规则插入失败！")

        if self.graph.is_leaf(an[0]):
            node = self.graph.query_node_by_label(an[0])
            new = DualLicense()
            new_group = set()
            new_group.add(DualUnit(license_a, filename=an[0]))
            new.add(tuple(new_group))
            node["licenses"] = new
            nx.set_node_attributes(self.graph.graph, {an[0]: node})
            an_node_A = an[0]
            self.graph.modify_node_attribute(an[0], "type", "executable")
        else:
            self.graph.modify_node_attribute(an[0], "type", "executable")
            successors = list(self.graph.successors(an[0]))  # 转换生成器为列表
            if successors:
                chid = successors[0]
                chid_node = self.graph.query_node_by_label(chid)
                new = DualLicense()
                new_group = set()
                new_group.add(DualUnit(license_a, filename=chid))
                new.add(tuple(new_group))
                chid_node["licenses"] = new
                nx.set_node_attributes(self.graph.graph, {chid: chid_node})
                an_node_A = chid
                if chid_node["type"] != "shared_library":
                    self.graph.modify_node_attribute(chid, "type", "shared_library")

        if self.graph.is_leaf(an[1]):
            node = self.graph.query_node_by_label(an[1])
            new = DualLicense()
            new_group = set()
            new_group.add(DualUnit(license_b, filename=an[1]))
            new.add(tuple(new_group))
            node["licenses"] = new
            nx.set_node_attributes(self.graph.graph, {an[1]: node})
            an_node_B = an[1]
            if node["type"] != "shared_library":
                self.graph.modify_node_attribute(an[1], "type", "shared_library")
        else:
            successors = list(self.graph.successors(an[1]))  # 转换生成器为列表
            if successors:
                chid = successors[0]
                chid_node = self.graph.query_node_by_label(chid)
                new = DualLicense()
                new_group = set()
                new_group.add(DualUnit(license_b, filename=chid))
                new.add(tuple(new_group))
                chid_node["licenses"] = new
                nx.set_node_attributes(self.graph.graph, {chid: chid_node})
                an_node_B = chid
                if chid_node["type"] != "shared_library":
                    self.graph.modify_node_attribute(chid, "type", "shared_library")

        return self.graph, an_node_A, an_node_B


class TestParser(BaseParser):
    gn_dict = {"deps": {}}
    visted = set()
    arg_table = {
        "--gn_file": {"type": str, "help": "the path of the gn file", "group": "test"},
        "--user_config_file": {"type": str, "help": "the path of the config file", "group": "test"},
    }

    def parse(self, project_path: str, context: GraphManager):
        # 加载依赖图
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

        # 加载用户配置
        with open("D:\study\compliance_license_compatibility\lict\parser\Test_parser\\user_config.toml", "r") as f:
            user_config = toml.load(f)
            f.close()
        config = Config.from_toml(path="lict/config/default.toml")
        subgraph_list = context.get_subgraph_depth()
        idx = 0
        num = 1
        # processing
        # debug 此处传入子图会报错 networkx.exception.NetworkXError: Frozen graph can't be modified，传入整图则不会报错
        answer = {}
        for key, value in user_config.items():

            folder_name = str(value['description'])
            answer[folder_name] = []
            # 创建文件夹，如果文件夹已存在则忽略
            try:
                os.makedirs(folder_name)
                # print(f"文件夹 '{folder_name}' 创建成功。")
            except FileExistsError:
                # print(f"文件夹 '{folder_name}' 已存在。")
                pass
            num += 1

            license_a = value['license_A']
            license_b = value['license_B']
            condition = value['condition']
            if "1" in condition:
                # Rule1----A，B位于同一结点
                #subgraph = subgraph_list[idx]
                subgraph = GraphManager("D:\study\compliance_license_compatibility\lict\parser\Test_parser\init.gml")
                subgraph.graph = subgraph.graph.copy()
                test = TestRule(subgraph)
                newgraph_rule1, node = test.rule_a(license_a, license_b)
                print(node)
                newgraph_rule1.save(f"{folder_name}\\graph_rule1.gml")
                # insert_graph(newgraph_rule1, context)
                idx += 1
                # 解冻图形
                if nx.is_frozen(newgraph_rule1.graph):
                    # print("该图被冻结")
                    newgraph_rule1.graph = newgraph_rule1.graph.copy()
                # print("接下来处理的是规则1")
                an = BaseCompatiblityParser(argparse.Namespace(), config=config).parse("test", newgraph_rule1)
                an.save(f"{folder_name}\\graph_rule1_an.gml")
                found = False
                for u, v, k, data in an.graph.edges(keys=True, data=True):
                    if data.get('type') == "compatible_result":
                        found = True
                        edge_data = data
                        break

                if found:
                    # print("检测到冲突")
                    answer[folder_name].append("1")
                else:
                    pass
                conflict = [node]

            if "2" in condition:
                # Rule2---A,B为两个不同叶子节点，静态链接（明确一点，函数取得的初始结点对的父节点肯定是一样的，二者均往下取直至没有叶子节点，理论上只用走一个）
                # subgraph = subgraph_list[idx]
                subgraph = GraphManager(
                    "D:\study\compliance_license_compatibility\lict\parser\Test_parser\init.gml")
                subgraph.graph = subgraph.graph.copy()
                test = TestRule(subgraph)
                newgraph_rule2, node_a, node_b = test.rule_b(license_a, license_b)
                print(node_a, node_b)
                newgraph_rule2.save(f"{folder_name}\\graph_rule2.gml")
                #  insert_graph(newgraph_rule2, context)
                idx += 1
                # 解冻图形
                if nx.is_frozen(newgraph_rule2.graph):
                    # print("该图被冻结")
                    newgraph_rule2.graph = newgraph_rule2.graph.copy()
                # print("接下来处理的是规则2")
                an = BaseCompatiblityParser(argparse.Namespace(), config=config).parse("test", newgraph_rule2)
                an.save(f"{folder_name}\\graph_rule2_an.gml")
                found = False
                for u, v, k, data in an.graph.edges(keys=True, data=True):
                    if data.get('type') == "compatible_result":
                        found = True
                        edge_data = data
                        break

                if found:
                    # print("检测到冲突")
                    answer[folder_name].append("2")
                else:
                    pass
                conflict = [node_a, node_b]

            if "3" in condition:
                # Rule3---A,B为两个不同叶子节点，动态链接
                # subgraph = subgraph_list[idx]
                subgraph = GraphManager(
                    "D:\study\compliance_license_compatibility\lict\parser\Test_parser\init.gml")
                subgraph.graph = subgraph.graph.copy()
                test = TestRule(subgraph)
                newgraph_rule3, node_a, node_b = test.rule_c(license_a, license_b)
                newgraph_rule3.save(f"{folder_name}\\graph_rule3.gml")
                # insert_graph(newgraph_rule3, context)
                idx += 1
                # 解冻图形
                if nx.is_frozen(newgraph_rule3.graph):
                    # print("该图被冻结")
                    newgraph_rule3.graph = newgraph_rule3.graph.copy()
                # print("接下来处理的是规则3")
                an = BaseCompatiblityParser(argparse.Namespace(), config=config).parse("test", newgraph_rule3)
                an.save(f"{folder_name}\\graph_rule3_an.gml")
                found = False
                for u, v, k, data in an.graph.edges(keys=True, data=True):
                    if data.get('type') == "compatible_result":
                        found = True
                        edge_data = data
                        break

                if found:
                    # print("检测到冲突")
                    answer[folder_name].append("3")
                else:
                    pass
                conflict = [node_a, node_b]

            if "4" in condition:
                # Rule4---exe
                # subgraph = subgraph_list[idx]
                subgraph = GraphManager(
                    "D:\study\compliance_license_compatibility\lict\parser\Test_parser\init.gml")
                subgraph.graph = subgraph.graph.copy()
                test = TestRule(subgraph)
                flag = 2
                newgraph_rule4, node_a, node_b = test.rule_d(license_a, license_b)
                newgraph_rule4.save(f"{folder_name}\\graph_rule4.gml")
                # insert_graph(newgraph_rule4, context)
                idx += 1
                # 解冻图形
                if nx.is_frozen(newgraph_rule4.graph):
                    # print("该图被冻结")
                    newgraph_rule4.graph = newgraph_rule4.graph.copy()
                # print("接下来处理的是规则4")
                an = BaseCompatiblityParser(argparse.Namespace(), config=config).parse("test", newgraph_rule4)
                an.save(f"{folder_name}\\graph_rule4_an.gml")
                found = False
                for u, v, k, data in an.graph.edges(keys=True, data=True):
                    if data.get('type') == "compatible_result":
                        found = True
                        edge_data = data
                        break

                if found:
                    # print("检测到冲突")
                    answer[folder_name].append("3")
                else:
                    pass
                conflict = [node_a, node_b]

            # context.save("answer.gml")
        for key, value in answer.items():
            # if "1" in value:
            #     print(str(key) + "位于同一结点时发生冲突！")
            # if "2" in value:
            #     print(str(key) + "位于不同静态链接库时发生冲突！")
            # if "3" in value:
            #     print(str(key) + "位于不同动态链接库时发生冲突！")
            # if "4" in value:
            #     print(str(key) + "进程隔断时发生冲突！！")
            pass
        return context
