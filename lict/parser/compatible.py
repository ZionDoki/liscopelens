# coding=utf-8
# Author: Zion, Zihao Zhang
# Date: 2023/12/18
# Contact: liuza20@lzu.edu.cn, zhzihao2023@lzu.edu.cn

import argparse
import itertools

import networkx as nx
from rich.progress import track

from .base import BaseParser
from lict.checker import Checker
from lict.constants import CompatibleType, ScopeElement

from lict.utils import GraphManager, combined_generator
from lict.utils.structure import DualLicense, Scope, Config


class BaseCompatiblityParser(BaseParser):

    arg_table = {
        "--ignore-unk": {"action": "store_true", "help": "Ignore unknown licenses", "default": False},
        "--out-gml": {"type": str, "help": "The output path of the graph", "default": ""},
    }

    def __init__(self, args: argparse.Namespace, config: Config):
        super().__init__(args, config)
        self.checker = Checker()

    def parse_condition(self, condition: str) -> str:
        return self.config.literal2enum(condition)

    def reverse_topological_sort(self, graph):
        return reversed(list(nx.topological_sort(graph)))

    def generate_processing_sequence(self, graph):
        nodes_to_process = self.reverse_topological_sort(graph)
        for node in nodes_to_process:
            parents = graph.predecessors(node)
            children = graph.successors(node)
            yield node, parents, children

    def check_compatiblity(self, license_a: str, license_b: str, scope_a: Scope, scope_b: Scope, ignore_unk=False):
        compatible_results = (CompatibleType.CONDITIONAL_COMPATIBLE, CompatibleType.UNCONDITIONAL_COMPATIBLE)
        if ignore_unk:
            compatible_results += (CompatibleType.UNKNOWN,)

        license_a2b = self.checker.check_compatibility(license_a, license_b, scope=scope_a)
        license_b2a = self.checker.check_compatibility(license_b, license_a, scope=scope_b)

        if license_a2b in compatible_results or license_b2a in compatible_results:

            if license_a2b != license_b2a and CompatibleType.UNCONDITIONAL_COMPATIBLE in (license_a2b, license_b2a):
                Warning.warn(f"{license_a} -{license_a2b}-> {license_b}, {license_b} -{license_b2a}-> {license_a}.")
            return license_a2b if license_a2b in compatible_results else license_b2a

        return CompatibleType.INCOMPATIBLE

    def filter_dual_pair(
        self,
        base_dl: DualLicense,
        other_dl: DualLicense = None,
        ignore_unk: bool = False,
    ) -> tuple[DualLicense, DualLicense, bool]:
        """
        Check the compatibility between two dual licenses.

        ! Attention: This method suppose that the dual licenses are in the same file. This behavior
        ! will cause the method to not consider conditional compatibility. Once this set of Dual
        ! Licenses cannot be unconditionally compatible, a conflict will be reported.

        Args:
            - dual_a: The dual licenses to be checked

        Returns:
            - The compatibility type of the two dual licenses
        """

        if not isinstance(base_dl, DualLicense):
            raise ValueError("base_dl should be a DualLicense  object")

        if other_dl is not None and not isinstance(other_dl, DualLicense):
            raise ValueError("other_dl should be a DualLicense  object")

        if other_dl is None:
            other_dl = base_dl

        base_compatible = DualLicense()
        other_compatbile = DualLicense()

        conflict_flag = False
        conflict = []
        for base_group, other_group in itertools.product(base_dl, other_dl):

            conflict_flag = False

            if ignore_unk:
                base_group = tuple(filter(lambda x: self.checker.is_license_exist(x["spdx_id"]), base_group))
                other_group = tuple(filter(lambda x: self.checker.is_license_exist(x["spdx_id"]), other_group))

            for license_a, license_b in itertools.product(base_group, other_group):
                spdx_a, spdx_b = license_a["spdx_id"], license_b["spdx_id"]
                conds_a = license_a["condition"]
                conds_b = license_b["condition"]

                if license_a["spdx_id"] == license_b["spdx_id"]:
                    continue

                scope_a = Scope({conds_a: set()}) if conds_a else conds_a
                scope_b = Scope({conds_b: set()}) if conds_b else conds_b

                spdx_a_list = (
                    [spdx_a + "-with-" + exception for exception in license_a["exceptions"]]
                    if license_a["exceptions"]
                    else [spdx_a]
                )

                spdx_b_list = (
                    [spdx_b + "-with-" + exception for exception in license_b["exceptions"]]
                    if license_b["exceptions"]
                    else [spdx_b]
                )

                for spdx_a, spdx_b in itertools.product(spdx_a_list, spdx_b_list):
                    result = self.check_compatiblity(spdx_a, spdx_b, scope_a, scope_b, ignore_unk)
                    if result != CompatibleType.INCOMPATIBLE:
                        break

                if result == CompatibleType.INCOMPATIBLE:
                    conflict.append((spdx_a, spdx_b))
                    conflict_flag = True
                    break

            # * check all the licenses in the group are compatible then add the group to the compatible results
            if not conflict_flag:
                base_compatible.add(base_group)
                other_compatbile.add(other_group)

        return base_compatible, other_compatbile, conflict_flag, conflict

    def parse(self, project_path: str, context: GraphManager = None) -> GraphManager:
        ignore_unk = getattr(self.args, "ignore_unk", False)
        out_gml = getattr(self.args, "out_gml", "")

        for sub in track(nx.weakly_connected_components(context.graph), "Parsing compatibility..."):
            for current_node, parents, children in self.generate_processing_sequence(
                context.graph.subgraph(sub).copy()
            ):

                candidate_nodes = tuple(combined_generator([current_node], children))

                for i, node_a in enumerate(candidate_nodes):

                    conflict_stack = []
                    # * check the current node first that has licenses
                    if node_a == current_node and (license_groups := context.nodes[current_node].get("licenses")):

                        results, _, conflict_flag, conflict = self.filter_dual_pair(license_groups, ignore_unk=ignore_unk)

                        if not results and conflict_flag:
                            edge = self.create_edge(
                                node_a, node_a, label=CompatibleType.INCOMPATIBLE, type="compatible_result", conflict=conflict
                            )
                            context.add_edge(edge)
                        else:
                            context.nodes[node_a]["outbound_license"] = results

                    filtered_a = context.nodes[node_a].get("compatible_license", None)
                    if not filtered_a:
                        filtered_a = context.nodes[node_a].get("outbound_license", None)

                    for node_b in candidate_nodes[i + 1 :]:

                        dual_b = context.nodes[node_b].get("compatible_license", None)
                        if not dual_b:
                            dual_b = context.nodes[node_b].get("outbound_license", None)

                        if (node_a == current_node) and dual_b:
                            if condition := self.parse_condition(context.nodes[node_b].get("type", None)):
                                context.nodes[node_b]["outbound_license"] = dual_b.add_condition(condition)
                                if condition in self.config.license_isolations:
                                    context.nodes[node_b]["license_isolation"] = True

                        if not (filtered_a and dual_b):
                            continue

                        if context.nodes[node_a].get("license_isolation", False):
                            continue

                        if context.nodes[node_b].get("license_isolation", False):
                            continue

                        compatible_a, compatible_b, conflict_flag, conflict = self.filter_dual_pair(
                            filtered_a, dual_b, ignore_unk=ignore_unk
                        )

                        if conflict_flag:
                            conflict_stack.append(node_b)

                        if not compatible_a:
                            incompatible_type = (
                                CompatibleType.PARTIAL_INCOMPATIBLE
                                if len(conflict_stack) > 1
                                else CompatibleType.INCOMPATIBLE
                            )

                            for node in conflict_stack:
                                edge = self.create_edge(
                                    node_a, node, compatible=incompatible_type, type="compatible_result", conflict=conflict
                                )
                                context.add_edge(edge)
                            # * terminate the loop
                            break
                        else:
                            filtered_a = compatible_a
                            context.nodes[node_a]["compatible_license"] = compatible_a
                            context.nodes[node_b]["compatible_license"] = compatible_b

                    # * 计算出站许可证
                    if filtered_a and (outbound_from_a := filtered_a.get_outbound(self.config)):

                        origin_nodes = context.get_predecessors_of_type(node_a, edge_type="spread_to")
                        if origin_nodes:
                            for origin_node in origin_nodes:
                                edge = self.create_edge(origin_node, current_node, type="spread_to")
                                context.add_edge(edge)
                        else:
                            edge = self.create_edge(node_a, current_node, type="spread_to")
                            context.add_edge(edge)

                        if current_outbound := context.nodes[current_node].get("outbound_license", None):
                            context.nodes[current_node]["outbound_license"] = current_outbound & outbound_from_a
                        else:
                            context.nodes[current_node]["outbound_license"] = outbound_from_a

        if out_gml:
            context.save(out_gml)
        return context
