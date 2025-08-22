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
import json
import time
import warnings
import argparse
import itertools
from uuid import uuid4
from pathlib import Path
from typing import Generator, Optional

import networkx as nx
from rich.progress import Progress

from liscopelens.checker import Checker
from liscopelens.constants import CompatibleType

from liscopelens.utils import GraphManager, set2list
from liscopelens.utils.structure import DualLicense, Scope, Config

from .base import BaseParser


class BaseCompatiblityParser(BaseParser):

    arg_table = {
        "--ignore-unk": {"action": "store_true", "help": "Ignore unknown licenses", "default": False},
        "--output": {"type": str, "help": "The outputs path", "default": ""},
    }

    def __init__(self, args: argparse.Namespace, config: Config):
        super().__init__(args, config)
        self.checker = Checker()

    def parse_condition(self, condition: str) -> Optional[str]:
        """
        Parse the condition string to the enum using config's literal mapping

        Args:
            - condition (str): The condition string to parse

        Returns:
            Optional[str]: The parsed enum value, or None if no mapping exists
        """
        return self.config.literal2enum(condition)

    def topological_traversal(self, graph: nx.DiGraph) -> Generator[str, None, None]:
        """Topological sort the graph."""
        return nx.topological_sort(graph)

    def generate_processing_sequence(self, graph):
        """
        Generate the processing sequence of the graph

        Args:
            - graph (nx.DiGraph | nx.MultiDiGraph): The graph to be processed

        Returns:
            iterator: The iterator of the processing sequence
        """
        nodes_to_process = self.topological_traversal(graph)
        for node in nodes_to_process:
            parents = graph.predecessors(node)
            children = graph.successors(node)
            yield node, parents, children

    def check_compatiblity(
        self, license_a: str, license_b: str, scope_a: Scope, scope_b: Scope, ignore_unk=False,
        condition_type: Optional[str] = None
    ) -> CompatibleType:
        """
        Check the compatibility between two licenses

        Usage:
            ```
            parser = BaseCompatiblityParser(args, config)
            parser.check_compatiblity("GPL-2.0-only", "GPL-3.0-or-later", Scope.from_str("UNIVERSAL"))
            ```

        Args:
            - license_a (str): The first license
            - license_b (str): The second license
            - scope_a (Scope): The scope of the first license
            - scope_b (Scope): The scope of the second license
            - ignore_unk (bool): Ignore unknown licenses

        Returns:
            CompatibleType: The compatibility type
        """
        compatible_results = (CompatibleType.CONDITIONAL_COMPATIBLE, CompatibleType.UNCONDITIONAL_COMPATIBLE)
        if ignore_unk:
            compatible_results += (CompatibleType.UNKNOWN,)

        # Convert condition type to enum if provided
        if condition_type:
            condition_enum = self.parse_condition(condition_type)
            if condition_enum:
                scope_a = Scope({condition_enum: set()}) if scope_a is None else scope_a
                scope_b = Scope({condition_enum: set()}) if scope_b is None else scope_b

        license_a2b = self.checker.check_compatibility(license_a, license_b, scope=scope_a)
        license_b2a = self.checker.check_compatibility(license_b, license_a, scope=scope_b)

        if license_a2b in compatible_results or license_b2a in compatible_results:

            if license_a2b != license_b2a and CompatibleType.UNCONDITIONAL_COMPATIBLE in (license_a2b, license_b2a):
                warnings.warn(f"{license_a} -{license_a2b}-> {license_b}, {license_b} -{license_b2a}-> {license_a}.")
            return license_a2b if license_a2b in compatible_results else license_b2a

        return CompatibleType.INCOMPATIBLE

    def filter_dual_license(
        self,
        dual_lic: DualLicense,
        blacklist: Optional[list[str]] = None,
        ignore_unk: bool = False,
        condition_type: Optional[str] = None,
    ) -> tuple[DualLicense, set[frozenset[str]]]:
        """
        Check the compatibility of the dual license, filter group that contains the blacklist license or conflict license.

        Args:
            - dual_lic (DualLicense): The dual license
            - blacklist (list[str]): The blacklist of the licenses
            - ignore_unk (bool): Ignore unknown licenses

        Returns:
            DualLicense: The compatible dual licenses
            tuple[frozenset[str]]: The conflict licenses
            tuple[frozenset[str]]: The hit conflict licenses
        """

        if not isinstance(dual_lic, DualLicense):
            raise ValueError("dual_lic should be a DualLicense object")

        if not dual_lic:
            return DualLicense(), set()

        conflicts = set()
        blacklist = blacklist or []

        new_dual_lic = dual_lic.copy()

        for group in dual_lic:

            if group not in new_dual_lic:
                continue

            rm_flag = False
            for lic in group:
                if frozenset((lic,)) in conflicts:
                    rm_flag = True

                if lic.unit_spdx in blacklist:
                    conflicts.add(frozenset((lic.unit_spdx,)))
                    rm_flag = True

            if rm_flag:
                new_dual_lic.remove(group)

        for group in dual_lic:

            if group not in new_dual_lic:
                continue

            group_rm_flag = False

            new_group = filter(lambda x: (self.checker.is_license_exist(x.unit_spdx) or not ignore_unk), group)

            for license_a, license_b in itertools.combinations(new_group, 2):

                if license_a["spdx_id"] == license_b["spdx_id"]:
                    continue

                if frozenset((license_a.unit_spdx, license_b.unit_spdx)) in conflicts:
                    group_rm_flag = True
                    continue

                scope_a = Scope({license_a["condition"]: set()}) if license_a["condition"] else license_a["condition"]
                scope_b = Scope({license_b["condition"]: set()}) if license_b["condition"] else license_b["condition"]

                result = self.check_compatiblity(
                    license_a.unit_spdx,
                    license_b.unit_spdx,
                    scope_a,
                    scope_b,
                    ignore_unk,
                    condition_type
                )
                if result == CompatibleType.INCOMPATIBLE:
                    conflicts.add(frozenset((license_a.unit_spdx, license_b.unit_spdx)))
                    group_rm_flag = True

            if group_rm_flag:
                new_dual_lic.remove(group)

        return new_dual_lic, conflicts

    def is_conflict_happened(self, dual_lic: Optional[DualLicense], conflicts: set[frozenset[str]]) -> bool:
        """
        Check if the conflict happened in the dual license

        Any license group in the dual license that does not contain the conflict license will return False.

        Args:
            - dual_lic (DualLicense): The dual license
            - conflicts (set[frozenset[str]]): The conflict licenses

        Returns:
            bool: If the conflict happened
        """

        if not dual_lic:
            return False

        for group in dual_lic:
            if not any(lic in [du.unit_spdx for du in group] for lic in itertools.chain(*conflicts)):
                return False

        return True

    def parse(self, project_path: Path, context: Optional[GraphManager] = None) -> GraphManager:
        """
        Parse the compatibility of the licenses

        This method will parse the compatibility of the licenses in the graph. But only adopt the scenario that the
        licenses in file level, and these file will package to the single binary file or something like that.

        Args:
            - project_path (str): The path of the project, **but not used**.
            - context (GraphManager): The context of the graph

        Returns:
            GraphManager: The context of the graph
        """
        global_conflicts_table: dict[str, set[frozenset[str]]] = {}
        ignore_unk = getattr(self.args, "ignore_unk", False)
        blacklist = getattr(self.config, "blacklist", [])

        # 节点类型到预设类型的映射缓存，避免重复转换
        condition_cache: dict[str, Optional[str]] = {}

        if not context:
            raise ValueError("The context should not be None")

        with Progress() as progress:
            start_time = time.time()
            total_nodes = len(context.graph.nodes)
            task = progress.add_task("[red]Parsing compatibility...", total=total_nodes)
            for sub in nx.weakly_connected_components(context.graph):
                # Conflict patterns within this weakly connected component
                local_conflicts_table: dict[str, set[frozenset[str]]] = {}
                for current_node, parents, _ in self.generate_processing_sequence(context.graph.subgraph(sub).copy()):
                    
                    def _mark_parent_edges_with_conflict(parent_node: str, child_node: str, conflict_id: str) -> None:
                        """Mark all edges from parent_node to child_node with the conflict id."""
                        edges_dict = context.graph.get_edge_data(parent_node, child_node)
                        if isinstance(edges_dict, dict):
                            for key, edata in edges_dict.items():
                                cg = edata.get("conflict_group", set())
                                if not isinstance(cg, set):
                                    cg = set(cg) if isinstance(cg, (list, tuple)) else set()
                                if conflict_id not in cg:
                                    cg.add(conflict_id)
                                    context.graph[parent_node][child_node][key]["conflict_group"] = cg

                    dual_before_check = context.nodes()[current_node].get("before_check", None)
                    node_type = context.nodes()[current_node].get("type", None)

                    # 获取节点的预设类型
                    if node_type:
                        if node_type not in condition_cache:
                            condition_cache[node_type] = self.parse_condition(node_type)
                        condition_enum = condition_cache[node_type]
                    else:
                        condition_enum = None

                    if dual_before_check is None:
                        progress.update(task, advance=1)
                        continue

                    # 在兼容性检查时传入条件类型
                    dual_after_check, conflicts = self.filter_dual_license(
                        dual_before_check, blacklist=blacklist, ignore_unk=ignore_unk,
                        condition_type=condition_enum
                    )

                    current_outbound = context.nodes()[current_node].get("outbound", None)

                    new_pattern_flag, parent_conflict_flag = True, False
                    new_pattern = conflicts.copy()

                    for parent in parents:

                        # _ current node has no outbound, then break
                        if not current_outbound:
                            break

                        conflict_group = context.nodes()[parent].get("conflict_group", None)
                        if conflict_group is None:
                            continue

                        parent_conflict_flag = True
                        for conflict_id in conflict_group:
                            conflict_pattern = local_conflicts_table.get(conflict_id, None)
                            if conflict_pattern is None:
                                conflict_pattern = global_conflicts_table.get(conflict_id, set())

                            # _ here to check if current node has contribution to the conflict then add conflict_id to it
                            if self.is_conflict_happened(dual_after_check, conflict_pattern):
                                context.nodes()[current_node]["conflict_group"] = (
                                    context.nodes()[current_node].get("conflict_group", set()).union({conflict_id})
                                )
                                # Mark parent->current edges as conflict edges
                                _mark_parent_edges_with_conflict(parent, current_node, conflict_id)

                            if dual_after_check:
                                continue

                            # new_pattern = set(filter(lambda conflict: conflict not in conflict_pattern, conflicts))
                            new_pattern = set(
                                [conflict for conflict in new_pattern if conflict not in conflict_pattern]
                            )

                            if len(new_pattern) != len(conflicts):
                                context.nodes()[current_node]["conflict_group"] = (
                                    context.nodes()[current_node].get("conflict_group", set()).union({conflict_id})
                                )
                                _mark_parent_edges_with_conflict(parent, current_node, conflict_id)

                            if not new_pattern:
                                new_pattern_flag = False

                    if dual_after_check:
                        progress.update(task, advance=1)
                        continue

                    if not parent_conflict_flag:

                        uuid = str(uuid4())
                        for conflict_id, conflict_set in local_conflicts_table.items():
                            if conflicts == conflict_set:
                                uuid = conflict_id
                                break

                        local_conflicts_table[uuid] = conflicts
                        context.nodes()[current_node]["conflict_group"] = {uuid}
                        context.nodes()[current_node]["first"] = True
                        # Mark edges from all parents to current for context
                        for p in parents:
                            _mark_parent_edges_with_conflict(p, current_node, uuid)

                    elif new_pattern_flag:

                        uuid = str(uuid4())
                        for conflict_id, conflict_set in local_conflicts_table.items():
                            if new_pattern == conflict_set:
                                uuid = conflict_id
                                break

                        local_conflicts_table[uuid] = new_pattern
                        context.nodes()[current_node]["conflict_group"] = (
                            context.nodes()[current_node].get("conflict_group", set({})).union({uuid})
                        )
                        for p in parents:
                            _mark_parent_edges_with_conflict(p, current_node, uuid)

                    progress.update(
                        task, advance=1, description=f"[red]Processing compatibility {time.time() - start_time:.2f}s"
                    )

                # Merge this component's conflict patterns into global mapping
                global_conflicts_table.update(local_conflicts_table)

        if output := getattr(self.args, "output", None):
            os.makedirs(output, exist_ok=True)
            context.save(output + "/compatible_checked.json")
            ret_results = {}
            for node, node_data in context.nodes(data=True):
                conflict_group = node_data.get("conflict_group", None)
                if not (
                    conflict_group
                    and (current_licenses := node_data.get("licenses", None))
                    and (outbound := node_data.get("outbound", None))
                ):
                    continue

                for conflict_id in conflict_group:
                    ret_results[conflict_id] = ret_results.get(conflict_id, {"conflicts": global_conflicts_table[conflict_id]})

                    # 收集通过sources边关联的许可证
                    sources_licenses = set()
                    for _, child_node, edge_data in context.graph.out_edges(node, data=True):
                        if edge_data.get("label") == "sources":
                            child_licenses = context.nodes()[child_node].get("licenses", None)
                            if child_licenses:
                                for lic in itertools.chain(*child_licenses):
                                    sources_licenses.add(lic.unit_spdx)

                    for lic in itertools.chain(*global_conflicts_table[conflict_id]):
                        if lic not in [lic.unit_spdx for lic in itertools.chain(*current_licenses)]:
                            continue

                        # 检查许可证是否在outbound（deps传播）或sources中
                        in_outbound = lic in [lic.unit_spdx for lic in itertools.chain(*outbound)]
                        in_sources = lic in sources_licenses
                        
                        if not in_outbound and not in_sources:
                            continue

                        node_identifier = node

                        if node_data.get("path"):
                            node_identifier = node_data["path"]
                        elif hasattr(self.args, "node_attr") and self.args.node_attr:
                            if hasattr(self.args, self.args.node_attr):
                                attr_value = getattr(self.args, self.args.node_attr)
                                if attr_value:
                                    node_identifier = attr_value
                            elif self.args.node_attr in node_data:
                                attr_value = node_data[self.args.node_attr]
                                if attr_value:
                                    node_identifier = attr_value
                        elif "src_path" in node_data and node_data["src_path"]:
                            node_identifier = node_data["src_path"]

                        ret_results[conflict_id][lic] = (
                            ret_results[conflict_id].get(lic, set()).union({node_identifier})
                        )

            with open(output + "/results.json", "w", encoding="utf8") as f:
                f.write(json.dumps(ret_results, default=lambda x: set2list(x) if isinstance(x, set) else x, indent=4))

        return context
