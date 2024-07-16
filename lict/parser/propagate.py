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
import warnings
import argparse
import itertools

from functools import reduce
from typing import Optional, Any

import networkx as nx
from rich.progress import Progress

from lict.constants import ScopeElement

from .base import BaseParser
from lict.checker import Checker

from lict.utils.structure import DualLicense, Scope, Config, DualUnit
from lict.utils import GraphManager, combined_generator, set2list, timer


class BasePropagateParser(BaseParser):

    arg_table = {
        "--output": {"type": str, "help": "The outputs path", "default": ""},
    }

    def __init__(self, args: argparse.Namespace, config: Config):
        super().__init__(args, config)
        self.checker = Checker()

    def parse_condition(self, condition: str) -> Optional[str]:
        """
        Parse the condition string to the enum

        Args:
            - condition (str): The condition string

        Returns:
            str: The condition enum
        """
        return self.config.literal2enum(condition)

    def reverse_topological_sort(self, graph: nx.DiGraph | nx.MultiDiGraph):
        """
        Reverse topological sort of the graph

        Args:
            - graph (nx.DiGraph | nx.MultiDiGraph): The graph to be sorted

        Returns:
            iterator: The iterator of the sorted nodes
        """
        return reversed(list(nx.topological_sort(graph)))

    def generate_processing_sequence(self, graph):
        """
        Generate the processing sequence of the graph

        Args:
            - graph (nx.DiGraph | nx.MultiDiGraph): The graph to be processed

        Returns:
            iterator: The iterator of the processing sequence
        """
        nodes_to_process = self.reverse_topological_sort(graph)
        for node in nodes_to_process:
            parents = graph.predecessors(node)
            children = graph.successors(node)
            yield node, parents, children

    def _merge_helper(self, lic_a: Any, lic_b: Any) -> dict:
        """
        Helper function for merging a group of licenses, this function implemented here is for using in reduce function

        Usage:
            ```
            dual_lic = DualLicense([...])
            for group in dual_lic:
                reduce(lambda x, y: self._merge_helper(x, y), group)
            ```

        Args:
            - lic_a (DualUnit | dict): The first license
            - lic_b (DualUnit): The second license

        Returns:
            dict: The merged license
        """
        ret = (
            {modal: self.checker.get_modal_features(lic_a.unit_spdx, modal) for modal in ("can", "must", "cannot")}
            if isinstance(lic_a, DualUnit)
            else lic_a
        )

        return {
            modal: self.checker.get_modal_features(lic_b.unit_spdx, modal).union(ret[modal])
            for modal in ("can", "must", "cannot")
        }

    def is_stricter(self, feat1: set[str], feat2: set[str]) -> bool:
        """
        Check if the first feature is stricter than the second feature.

        Usage:
            ```
            must_a = {'set_same_license', 'impose_further_restriction'}
            must_b = {'set_same_license'}

            self.is_stricter(must_a, must_b)
            ```

        Args:
            - feat1 (set[str]): The first feature
            - feat2 (set[str]): The second feature
            - reverse (bool): The reverse flag

        Returns:
            bool: The result of the comparison
        """
        for key in ["set_same_license", "impose_further_restriction"]:

            if key in feat1 and key not in feat2:
                return True

        return len(feat1) > len(feat2)

    def get_feats(self, spdx_id: str, modal: str) -> set[str]:
        """
        Get the features of the license

        Usage:
            ```
            self.get_feats("MIT", "can")

            ```

        Args:
            - spdx_id (str): The SPDX ID of the license
            - modal (str): The modal of the license

        Returns:
            set[str]: The features of the license
        """
        return self.checker.get_modal_features(spdx_id, modal)

    def merge_all_feats(self, dual_lic: frozenset[DualUnit]) -> dict[str, set[str]]:
        """
        Merge all the features of the licenses

        Usage:
            ```
            dual_lic = DualLicense([...])
            self.merge_all_feats(dual_lic)

            ```

        Args:
            - dual_lic (DualLicense): The dual license

        Returns:
            dict: The merged features
        """

        if len(dual_lic) > 1:
            return reduce(self._merge_helper, itertools.chain(*dual_lic))

        return {modal: self.get_feats(next(iter(dual_lic)).unit_spdx, modal) for modal in ("can", "must", "cannot")}

    def get_strict_outbound(self, dual_lic: DualLicense, reverse: bool = False) -> DualLicense:
        """
        Get the strict outbound licenses.

        Usage:
            ```
            dual_lic = DualLicense([...])
            out_bound = self.get_strict_outbound(dual_lic)

            ```

        Args:
            - dual_lic (DualLicense): The dual license
            - reverse (bool): The reverse flag

        Returns:
            DualLicense: The strict outbound licenses
        """

        ret_group = None

        if not dual_lic:
            return dual_lic

        for group in dual_lic:

            if not ret_group:
                ret_group = group
                ret_merge = self.merge_all_feats(group)
                continue

            group_merge = self.merge_all_feats(group)

            for modal in ("must", "cannot"):

                if self.is_stricter(ret_merge[modal], group_merge[modal]) != reverse:
                    break

                if self.is_stricter(group_merge[modal], ret_merge[modal]) != reverse:
                    ret_group = group
                    ret_merge = group_merge
                    break

            if (len(ret_merge["can"]) < len(group_merge["can"])) != reverse:
                ret_group = group
                ret_merge = group_merge

            if (len(ret_group) > len(group)) != reverse:
                ret_group = group
                ret_merge = group_merge

        if ret_group is None:
            return DualLicense([])

        return DualLicense([ret_group])

    def get_outbound(self, dual_lic: DualLicense, condition: Optional[str]) -> DualLicense:
        """
        Get the outbound licenses.

        Usage:
            ```
            dual_lic = DualLicense([...])
            out_bound = self.get_outbound(dual_lic, "commercial")
            ```

        Args:
            - dual_lic (DualLicense): The dual license
            - condition (str): The condition

        Returns:
            DualLicense: The outbound licenses
        """
        if not dual_lic:
            return dual_lic

        default_spread = "DEFAULT" in self.config.permissive_spreads

        new = DualLicense()
        for group in dual_lic:
            new_group = set()
            for lic in group:
                if not self.checker.is_license_exist(lic.unit_spdx):
                    continue

                if lic["condition"] in self.config.license_isolations:
                    continue

                relicense_id = self.checker.get_relicense(lic.unit_spdx, scope=Scope({lic["condition"]: set()}))

                if relicense_id == "public-domain":
                    continue

                if self.checker.is_copyleft(lic.unit_spdx):
                    new_group.add(DualUnit(lic["spdx_id"], condition, lic["exceptions"]))

                # * when the license is not copyleft, we need to check current component condition whether is in the permissive_spreads
                elif condition in self.config.permissive_spreads or default_spread:
                    new_group.add(DualUnit(lic["spdx_id"], condition, lic["exceptions"]))

            if new_group:
                new.add(frozenset(new_group))

        # ! when only calculate the propagation of the licenses, filter stricter licenses will cause unepxected result
        # return self.get_strict_outbound(new, reverse=True)
        return new

    def parse(self, project_path: str, context: Optional[GraphManager] = None) -> GraphManager:
        """
        Parse the licenses propagation.

        This function will parse the licenses propagation in the graph. But only adopt the scenario that the
        licenses in file level, and these file will package to the single binary file or something like that.

        Args:
            - project_path (str): The project path
            - context (GraphManager): The graph manager

        Returns:
            GraphManager: The updated graph manager
        """

        if not context:
            context = GraphManager()

        with Progress() as progress:
            total_nodes = len(context.graph.nodes)
            task = progress.add_task(f"[cyan]Parsing propogation...", total=total_nodes)
            for sub in nx.weakly_connected_components(context.graph):
                for current_node, _, children in self.generate_processing_sequence(context.graph.subgraph(sub).copy()):

                    if license_groups := context.nodes[current_node].get("licenses"):
                        current_outbound = license_groups
                    else:
                        current_outbound = None

                    current_condition = self.parse_condition(context.nodes[current_node].get("type", None))

                    if current_condition in self.config.license_isolations:
                        context.nodes[current_node]["license_isolation"] = True

                    for child in children:

                        dual_lic = context.nodes[child].get("outbound", None)

                        if not dual_lic:
                            continue

                        if child_outbound := context.nodes[child].get("outbound", None):
                            if not current_outbound:
                                current_outbound = child_outbound
                            current_outbound = child_outbound & current_outbound

                    if not current_outbound:
                        progress.update(task, advance=1)
                        continue

                    context.nodes[current_node]["before_check"] = current_outbound
                    current_outbound = current_outbound.add_condition(current_condition)
                    outbound = self.get_outbound(current_outbound, current_condition)
                    context.nodes[current_node]["outbound"] = outbound

                    progress.update(task, advance=1)

        if output := getattr(self.args, "output", None):
            os.makedirs(output, exist_ok=True)
            context.save(output + "/propagated.gml")

        return context
