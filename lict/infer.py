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

"""
Checker and Rules for license itself compatible inference
Inferring compatibility based on structured information
"""

import itertools

from abc import ABC, abstractmethod
from typing import Dict, Type, Optional, Callable
from copy import deepcopy

from lict.utils.scaffold import (
    is_file_in_resources,
    get_resource_path,
    normalize_version,
    extract_version,
    find_all_versions,
    find_duplicate_keys,
)
from lict.utils.structure import (
    Scope,
    Schemas,
    ActionFeat,
    LicenseFeat,
    load_schemas,
    load_licenses,
    ActionFeatOperator,
)
from lict.utils.graph import Edge, GraphManager, Triple, Vertex
from .constants import Settings, CompatibleType, FeatureProperty


def generate_knowledge_graph(reinfer: bool = False) -> "CompatibleInfer":
    """
    Infer license compatibility and properties based on structured information,
    generate knowledge graph for further usage.

    Args:
        reinfer (bool): whether to re-infer the compatibility and properties
    Returns:
        infer (CompatibleInfer): the infer for license compatibility.
    """
    schemas = load_schemas()

    if (
        reinfer
        or not is_file_in_resources(f"{Settings.LICENSE_PROPERTY_GRAPH}")
        or not is_file_in_resources(f"{Settings.LICENSE_COMPATIBLE_GRAPH}")
    ):
        all_licenses = load_licenses()
        infer = CompatibleInfer(schemas=schemas)
        infer.check_compatibility(all_licenses)

        for _, lic in all_licenses.items():
            infer.check_license_property(lic)

        infer.save()

    infer = CompatibleInfer(schemas=schemas)

    destination = get_resource_path()
    infer.properties_graph = GraphManager(str(destination.joinpath(Settings.LICENSE_PROPERTY_GRAPH)))
    infer.compatible_graph = GraphManager(str(destination.joinpath(Settings.LICENSE_COMPATIBLE_GRAPH)))
    return infer


class CompatibleRule(ABC):
    """
    Base class for compatibility rules.

    TODO: add helper function to check if there is a compatible edge in the graph.
    """

    __instance = None
    start_rule: bool = False
    end_rule: bool = False

    def __new__(cls, *args, **kwargs):
        if not isinstance(cls.__instance, cls):
            cls.__instance = super(CompatibleRule, cls).__new__(cls)
        return cls.__instance

    def __init__(self, add_callback: Callable, schemas: Schemas) -> None:
        super().__init__()
        self.add_callback = add_callback
        self.schemas = schemas

    def callback(
        self,
        licenses: Dict[str, LicenseFeat],
        graph: GraphManager,
        license_a: LicenseFeat,
        license_b: LicenseFeat,
    ):
        """Callback function to be executed after the rule is checked."""

    def new_edge(
        self,
        license_a: LicenseFeat,
        license_b: LicenseFeat,
        compatibility: CompatibleType,
        scope: Optional[str] = None,
        **kwargs,
    ):
        if scope is None:
            return Edge(
                license_a.spdx_id,
                license_b.spdx_id,
                compatibility=compatibility,
                rule=self.__class__.__name__,
                **kwargs,
            )
        return Edge(
            license_a.spdx_id,
            license_b.spdx_id,
            compatibility=compatibility,
            scope=scope,
            rule=self.__class__.__name__,
            **kwargs,
        )

    def get_callback(self, *args, **kwargs):
        """Get the callback function with arguments."""
        return lambda: self.callback(*args, **kwargs)

    def has_edge(
        self,
        license_a: LicenseFeat,
        license_b: LicenseFeat,
        graph: GraphManager,
        compatibility: CompatibleType = CompatibleType.UNCONDITIONAL_COMPATIBLE,
    ) -> bool:
        return bool(graph.query_edge_by_label(license_a.spdx_id, license_b.spdx_id, compatibility=compatibility))

    @abstractmethod
    def __call__(
        self, license_a: LicenseFeat, license_b: LicenseFeat, graph: GraphManager, edge: Optional[Edge] = None
    ) -> tuple[Type["CompatibleRule"], Optional[Edge]]:
        pass


class EndRule(CompatibleRule):

    end_rule: bool = True

    def __call__(
        self, license_a: LicenseFeat, license_b: LicenseFeat, graph: GraphManager, edge: Optional[Edge] = None
    ) -> tuple[Type[CompatibleRule], Optional[Edge]]:
        return EndRule, edge


class DefaultCompatibleRule(CompatibleRule):
    """
    If all rule checks are passed, then the licenses are compatible.
    """

    def __call__(
        self, license_a: LicenseFeat, license_b: LicenseFeat, graph: GraphManager, edge: Optional[Edge] = None
    ) -> tuple[Type[CompatibleRule], Optional[Edge]]:
        edge = self.new_edge(license_a, license_b, compatibility=CompatibleType.UNCONDITIONAL_COMPATIBLE)
        graph.add_edge(edge)
        return EndRule, edge


class PublicDomainRule(CompatibleRule):
    """
    TODO: This rule need remove after Public-domain license's feature is added.
    If any of the licenses is public domain, then they are compatible.
    ! KNOWN ERR: Public-domain cannot compatible with the license has cannot modify requirement.
    """

    start_rule: bool = True

    def __call__(
        self, license_a: LicenseFeat, license_b: LicenseFeat, graph: GraphManager, edge: Optional[Edge] = None
    ) -> tuple[Type[CompatibleRule], Optional[Edge]]:
        if license_a.spdx_id == "public-domain" or license_b.spdx_id == "public-domain":
            edge = self.new_edge(license_a, license_b, compatibility=CompatibleType.UNCONDITIONAL_COMPATIBLE)
            graph.add_edge(edge)
            return EndRule, edge
        return ImmutabilityRule, None


class ImmutabilityRule(CompatibleRule):
    """
    If any of the licenses is immutable, then they are incompatible. Any interoperability will cause conflicts to occur.

    TODO: need check interoperability between immutable licenses.
    """

    start_rule: bool = False

    def __call__(
        self, license_a: LicenseFeat, license_b: LicenseFeat, graph: GraphManager, edge: Optional[Edge] = None
    ) -> tuple[Type[CompatibleRule], Optional[Edge]]:

        license_a_immut = any(self.schemas.has_property(x, "immutability") for x in license_a.features)
        license_b_immut = any(self.schemas.has_property(x, "immutability") for x in license_b.features)
        if license_a_immut or license_b_immut:
            edge = self.new_edge(license_a, license_b, compatibility=CompatibleType.INCOMPATIBLE)
            graph.add_edge(edge)
            return EndRule, None

        return ExceptRelicenseRule, None


class ExceptRelicenseRule(CompatibleRule):
    """
    Check if there is a relicense in the license_a, if so, add a callback to check relicense target whether
    or not compatible with license_b. If does, then license_a is conditional compatible with license_b.
    """

    def __call__(
        self, license_a: LicenseFeat, license_b: LicenseFeat, graph: GraphManager, edge: Optional[Edge] = None
    ) -> tuple[Type["CompatibleRule"], Optional[Edge]]:
        relicense_feat = license_a.special.get("relicense")
        if relicense_feat := license_a.special.get("relicense"):
            if len(relicense_feat.target) != 0:
                self.add_callback(lambda licenses, graph: self.callback(licenses, graph, license_a, license_b))
        return OrLaterRelicenseRule, None

    def callback(
        self,
        licenses: Dict[str, LicenseFeat],
        graph: GraphManager,
        license_a: LicenseFeat,
        license_b: LicenseFeat,
    ) -> None:

        is_compatible = self.has_edge(
            license_a, license_b, graph, compatibility=CompatibleType.UNCONDITIONAL_COMPATIBLE
        )

        if is_compatible:
            return

        if relicense_feat := license_a.special.get("relicense"):
            for tgt in relicense_feat.target:

                is_compatible = graph.query_edge_by_label(
                    tgt, license_b.spdx_id, compatibility=CompatibleType.UNCONDITIONAL_COMPATIBLE
                )

                if bool(is_compatible):
                    origin_edges = graph.query_edge_by_label(
                        license_a.spdx_id, license_b.spdx_id, compatibility=CompatibleType.INCOMPATIBLE
                    )

                    for edge_index in origin_edges:
                        graph.remove_edge(edge_index)

                    edge = self.new_edge(
                        license_a,
                        license_b,
                        compatibility=CompatibleType.CONDITIONAL_COMPATIBLE,
                        scope=str(license_a.special["relicense"].scope),
                    )
                    graph.add_edge(edge)
                    return

                condition_edges = graph.query_edge_by_label(
                    tgt, license_b.spdx_id, compatibility=CompatibleType.CONDITIONAL_COMPATIBLE
                )

                for edge_index in condition_edges:
                    origin_edge = graph.get_edge_data(edge_index)
                    origin_scope = Scope.from_str(origin_edge["scope"])

                    new_compatible_scope = origin_scope & license_a.special["relicense"].scope
                    if not new_compatible_scope:
                        continue

                    edge = self.new_edge(
                        license_a,
                        license_b,
                        compatibility=CompatibleType.CONDITIONAL_COMPATIBLE,
                        scope=str(new_compatible_scope),
                    )
                    graph.add_edge(edge)


class OrLaterRelicenseRule(CompatibleRule):
    """
    Check if there is a or-later relicense in the license_a, if so, add a callback to check relicense target.
    If the target is compatible with license_b, then license_a is conditional compatible with license_b.
    """

    def __call__(
        self, license_a: LicenseFeat, license_b: LicenseFeat, graph: GraphManager, edge: Optional[Edge] = None
    ) -> tuple[Type[CompatibleRule], Optional[Edge]]:
        if "or-later" in license_a.spdx_id:
            self.add_callback(lambda licenses, graph: self.callback(licenses, graph, license_a, license_b))
        return ComplianceRequirementRule, None

    def get_normalized_version(self, spdx_id: str) -> list[int]:
        return normalize_version(extract_version(spdx_id) or "")

    def rm_existed_edges(
        self,
        graph: GraphManager,
        license_a: LicenseFeat,
        license_b: LicenseFeat,
        compatibility: CompatibleType,
        bi_direct: bool = False,
    ):
        origin_edges = graph.query_edge_by_label(license_a.spdx_id, license_b.spdx_id, compatibility=compatibility)

        for edge_index in origin_edges:
            graph.remove_edge(edge_index)

        if bi_direct:
            origin_edges = graph.query_edge_by_label(license_b.spdx_id, license_a.spdx_id, compatibility=compatibility)

            for edge_index in origin_edges:
                graph.remove_edge(edge_index)

    def callback(
        self, licenses: dict[str, LicenseFeat], graph: GraphManager, license_a: LicenseFeat, license_b: LicenseFeat
    ) -> None:
        current_version = self.get_normalized_version(license_a.spdx_id)
        later_licenses = filter(
            lambda x: self.get_normalized_version(x) > current_version and "or-later" not in x,
            find_all_versions(license_a.spdx_id, licenses.keys()),
        )

        is_compatible = self.has_edge(
            license_a, license_b, graph, compatibility=CompatibleType.UNCONDITIONAL_COMPATIBLE
        )

        if is_compatible:
            return

        later_licenses = tuple(later_licenses)
        for tgt in later_licenses:

            if tgt == license_b.spdx_id:

                self.rm_existed_edges(graph, license_a, license_b, CompatibleType.INCOMPATIBLE, True)
                edge = self.new_edge(license_a, license_b, compatibility=CompatibleType.UNCONDITIONAL_COMPATIBLE)
                graph.add_edge(edge)
                edge = self.new_edge(license_b, license_a, compatibility=CompatibleType.UNCONDITIONAL_COMPATIBLE)
                graph.add_edge(edge)
                continue

            for a, b in (tgt, license_b.spdx_id), (license_b.spdx_id, tgt):

                is_compatible = graph.query_edge_by_label(a, b, compatibility=CompatibleType.UNCONDITIONAL_COMPATIBLE)

                if bool(is_compatible):
                    self.rm_existed_edges(graph, license_a, license_b, CompatibleType.INCOMPATIBLE, True)
                    self.rm_existed_edges(graph, license_a, license_b, CompatibleType.CONDITIONAL_COMPATIBLE, True)

                    edge = self.new_edge(
                        license_a if a == tgt else license_b,
                        license_a if b == tgt else license_b,
                        compatibility=CompatibleType.UNCONDITIONAL_COMPATIBLE,
                        path=tgt,
                    )
                    graph.add_edge(edge)
                else:

                    condition_edges = graph.query_edge_by_label(
                        tgt, b, compatibility=CompatibleType.CONDITIONAL_COMPATIBLE
                    )

                    for edge_index in condition_edges:
                        origin_edge = graph.get_edge_data(edge_index)

                        edge = self.new_edge(
                            license_a if a == tgt else license_b,
                            license_a if b == tgt else license_b,
                            compatibility=CompatibleType.CONDITIONAL_COMPATIBLE,
                            scope=origin_edge["scope"],
                            path=tgt,
                        )
                        graph.add_edge(edge)


class ComplianceRequirementRule(CompatibleRule):
    """
    Check compliance requirement of license_a and license_b whether are not satisfied.
    """

    def check_compliance(self, license_a: LicenseFeat, license_b: LicenseFeat) -> bool:
        """
        Check if the compliance requirement of license_a is satisfied by license_b.

        Args:
            license_a: LicenseFeat, the license to be checked.
            license_b: LicenseFeat, the license to be checked.
        Returns:
            bool, True if the compliance requirement is satisfied.
        """

        if license_a.special.get("triggering"):
            new_license_a = deepcopy(license_a)

            for trigger in license_a.special["triggering"].target:
                modal, action = trigger.split(".")
                getattr(new_license_a, modal)[action] = ActionFeat.factory(action, modal, [], [])

        else:
            new_license_a = license_a

        feats_a = list(
            filter(lambda x: self.schemas.has_property(x, FeatureProperty.COMPLIANCE), new_license_a.features)
        )

        for feat_a in feats_a:
            current_compliance_modals = self.schemas[feat_a.name][FeatureProperty.COMPLIANCE]
            for modal in current_compliance_modals:
                license_a_actions = getattr(new_license_a, modal)
                license_b_actions = getattr(license_b, modal)

                is_subset = set(license_b_actions.keys()).issubset(set(license_a_actions.keys()))

                if not is_subset:
                    for key in set(license_b_actions.keys()) - set(license_a_actions.keys()):
                        conflict_scope = license_b_actions[key].scope & feat_a.scope
                        if conflict_scope:
                            return False

                # if is_subset, then check if the scope is compatible
                for key, action in license_a_actions.items():

                    if license_b_actions.get(key, False) == False:
                        continue

                    if not ActionFeatOperator.contains(action, license_b_actions[key]):
                        return False

        return True

    def __call__(
        self, license_a: LicenseFeat, license_b: LicenseFeat, graph: GraphManager, edge: Optional[Edge] = None
    ) -> tuple[Type[CompatibleRule], Optional[Edge]]:

        is_compliance = self.check_compliance(license_a, license_b)
        if not is_compliance:
            edge = self.new_edge(license_a, license_b, compatibility=CompatibleType.INCOMPATIBLE)
            graph.add_edge(edge)
            return EndRule, None

        is_compliance = self.check_compliance(license_b, license_a)
        if not is_compliance:
            edge = self.new_edge(license_a, license_b, compatibility=CompatibleType.INCOMPATIBLE)
            graph.add_edge(edge)
            return EndRule, None

        return ClauseConflictRule, None


class ClauseConflictRule(CompatibleRule):
    """
    Check license_a.(can|must) in license_b.(cannot) or either license_a.(cannot) in license_b.(can|must).
    If conflict exists, but there is a scope that can avoid conflict, then license_a is conditional
    compatible with license_b, otherwise, license_a is incompatible with license_b.

    Attention:
        Only record the scope of license_a that can avoid conflict. this will make the conditional
    compatible as a directed graph.
    """

    def __call__(
        self, license_a: LicenseFeat, license_b: LicenseFeat, graph: GraphManager, edge: Optional[Edge] = None
    ) -> tuple[Type["CompatibleRule"], Optional[Edge]]:

        # ! Check *Other Direction* if <license_b, license_a> has already been compatible.
        already_compatible = self.has_edge(
            license_b, license_a, graph, compatibility=CompatibleType.UNCONDITIONAL_COMPATIBLE
        )

        if already_compatible:
            return DefaultCompatibleRule, None

        condition_scope = Scope.universe()
        conflict_flag = False

        license_a_scope = Scope.universe()

        for modal_pair in itertools.product(["can", "must"], ["cannot"]):
            for modal_a, modal_b in itertools.permutations(modal_pair):
                conflicts = find_duplicate_keys(getattr(license_a, modal_a), getattr(license_b, modal_b))
                for conflict in conflicts:

                    # * if conflict action has conflicts property in schema, then check if the modal in conflict
                    if conflict_modals := self.schemas[conflict].get("conflicts", None):
                        if not any(modal_a in modal_pair and modal_b in modal_pair for modal_pair in conflict_modals):
                            continue

                    conflict_scope = ActionFeatOperator.intersect(
                        getattr(license_a, modal_a)[conflict], getattr(license_b, modal_b)[conflict]
                    )
                    # * only if conflict scope empty no conflict, else if it is universal then incompatible
                    if not conflict_scope:
                        continue
                    elif conflict_scope.is_universal:
                        edge = self.new_edge(license_a, license_b, compatibility=CompatibleType.INCOMPATIBLE)
                        graph.add_edge(edge)
                        return EndRule, None
                    compatible_scope = conflict_scope.negate()
                    # *  if compatible scope in license_a is empty, then incompatible
                    compatible_scope &= getattr(license_a, modal_a)[conflict].scope
                    if not compatible_scope:
                        edge = self.new_edge(license_a, license_b, compatibility=CompatibleType.INCOMPATIBLE)
                        graph.add_edge(edge)
                        return EndRule, None

                    conflict_flag = True
                    # if compatible scope is not empty, then conditional compatible
                    condition_scope &= compatible_scope
                    license_a_scope &= getattr(license_a, modal_a)[conflict].scope.negate() & compatible_scope

        if not conflict_flag:
            return DefaultCompatibleRule, None

        if not condition_scope:
            edge = self.new_edge(license_a, license_b, compatibility=CompatibleType.INCOMPATIBLE)
            graph.add_edge(edge)
            return EndRule, None

        if license_a_scope:
            edge = self.new_edge(
                license_a,
                license_b,
                compatibility=CompatibleType.CONDITIONAL_COMPATIBLE,
                scope=str(license_a_scope),
            )
            graph.add_edge(edge)

        return EndRule, edge


class CompatibleInfer:
    """
    Infer license compatibility based on structured information.

    Properties:
        callback_queque: List[callable], the callback functions to be executed.
        schemas: Schemas, the schema to check the properties of licenses.
        properties_graph: GraphManager, the graph to store the properties of licenses.
        compatible_graph: GraphManager, the graph to store the compatibility of licenses.
        rules: Dict[str, CompatibleRule], the rules to check the compatibility.
        start_rule: str, the start rule to check the compatibility.
        end_rule: str, the end rule to check the compatibility.
    """

    start_rule: str
    end_rule: str
    rules: Dict[str, CompatibleRule] = {}

    def __init__(self, schemas: Schemas, exceptions=None):
        self.callback_queque = []
        self.schemas = schemas
        self.exceptions = exceptions
        self.properties_graph = GraphManager()
        self.compatible_graph = GraphManager()

        for rule in CompatibleRule.__subclasses__():
            the_rule = rule(self.add_callback, schemas)
            self.rules[rule.__name__] = the_rule
            if rule.start_rule:
                self.start_rule = rule.__name__
            if rule.end_rule:
                self.end_rule = rule.__name__

    def add_callback(self, callback: Callable) -> None:
        self.callback_queque.append(callback)

    def check_license_property(self, license_a: LicenseFeat):
        """
        TODO: need change
        """
        license_vertex = Vertex(label=license_a.spdx_id)

        for feature in license_a.features:
            edge = Triple(license_vertex, Vertex(feature.name), name=feature.modal)

            relicense_feat = license_a.special.get("relicense", None)
            if relicense_feat:
                for tgt in relicense_feat.target:
                    relicense_edge = Triple(
                        license_vertex,
                        Vertex(tgt),
                        name="relicense",
                        scope=str(license_a.special["relicense"].scope),
                    )
                    self.properties_graph.add_triplet(relicense_edge)

            self.properties_graph.add_triplet(edge)

    def check_compatibility(self, licenses: Dict[str, LicenseFeat]):
        """
        Check compatibility between licenses.

        Args:
            licenses: Dict[str, LicenseFeat], the licenses to be checked.

        Returns:
            None, but update the compatible graph.
        """
        for license_a, license_b in itertools.product(licenses.values(), repeat=2):
            if license_a == license_b:
                continue

            edge = None
            visited = set()
            current_rule = self.rules[self.start_rule]
            while not (type(current_rule) == type(self.rules[self.end_rule])):
                if type(current_rule).__name__ in visited:
                    raise ValueError(f"Rule {type(current_rule).__name__} is visited twice.")

                visited.add(type(current_rule).__name__)
                next_rule_type, edge = current_rule(license_a, license_b, self.compatible_graph, edge)
                current_rule = self.rules[next_rule_type.__name__]

        while len(self.callback_queque) > 0:
            callback = self.callback_queque.pop(0)
            callback(licenses, self.compatible_graph)

    def infer_parir_compatibility(self, license_a: LicenseFeat, license_b: LicenseFeat):
        """
        !deprecated
        """
        if license_a == license_b:
            return

        for license_a, license_b in ((license_a, license_b), (license_b, license_a)):
            edge = None
            visited = set()
            current_rule = self.rules[self.start_rule]
            while not (type(current_rule) == type(self.rules[self.end_rule])):
                if type(current_rule).__name__ in visited:
                    raise ValueError(f"Rule {type(current_rule).__name__} is visited twice.")

                visited.add(type(current_rule).__name__)
                next_rule_type, edge = current_rule(license_a, license_b, self.compatible_graph, edge)
                current_rule = self.rules[next_rule_type.__name__]

        while len(self.callback_queque) > 0:
            callback = self.callback_queque.pop(0)
            callback(self.compatible_graph)

    def save(self, dir_path: Optional[str] = None):
        """
        Save the property and compatible graph to the data directory.

        Args:
            dir_path: str, the directory to save the graph.

        Returns:
            None, but save the graph to the data directory.
        """

        self.properties_graph = self.properties_graph.deduplicate_and_reorder_edges()
        self.compatible_graph = self.compatible_graph.deduplicate_and_reorder_edges()

        if dir_path:
            self.properties_graph.save(f"{dir_path}/{Settings.LICENSE_PROPERTY_GRAPH}")
            self.compatible_graph.save(f"{dir_path}/{Settings.LICENSE_COMPATIBLE_GRAPH}")
        else:
            property_path = str(get_resource_path().joinpath(Settings.LICENSE_PROPERTY_GRAPH))
            compatible_path = str(get_resource_path().joinpath(Settings.LICENSE_COMPATIBLE_GRAPH))
            self.properties_graph.save(property_path)
            self.compatible_graph.save(compatible_path)
