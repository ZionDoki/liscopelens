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

from liscopelens.utils.scaffold import (
    is_file_in_resources,
    get_resource_path,
    normalize_version,
    extract_version,
    find_all_versions,
    find_duplicate_keys,
)
from liscopelens.utils.structure import (
    Scope,
    Schemas,
    ActionFeat,
    LicenseFeat,
    load_schemas,
    load_licenses,
    ActionFeatOperator,
)
from liscopelens.utils.graph import Edge, GraphManager, Triple, Vertex
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
        or not is_file_in_resources(f"{Settings.LICENSE_PROPERTY_GRAPH}.{Settings.GRAPH_SAVE_FORMAT}")
        or not is_file_in_resources(f"{Settings.LICENSE_COMPATIBLE_GRAPH}.{Settings.GRAPH_SAVE_FORMAT}")
    ):
        all_licenses = load_licenses()
        infer = CompatibleInfer(schemas=schemas)
        infer.check_compatibility(all_licenses)

        for _, lic in all_licenses.items():
            infer.check_license_property(lic)

        infer.save()

    infer = CompatibleInfer(schemas=schemas)

    destination = get_resource_path()
    infer.properties_graph = GraphManager(
        str(destination.joinpath(f"{Settings.LICENSE_PROPERTY_GRAPH}.{Settings.GRAPH_SAVE_FORMAT}"))
    )
    infer.compatible_graph = GraphManager(
        str(destination.joinpath(f"{Settings.LICENSE_COMPATIBLE_GRAPH}.{Settings.GRAPH_SAVE_FORMAT}"))
    )
    return infer


class CompatibleRule(ABC):
    """
    Base class for compatibility rules.

    The foundation class that all license compatibility rules inherit from. Each rule is responsible
    for checking compatibility under specific conditions and providing detailed compatibility judgment reasons.
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
        self._last_reason = ""  # Stores the reason for the last rule execution

    @property
    def explanation(self) -> str:
        """
        Get the explanation of the rule.

        Provides detailed explanation about this rule based on the class's docstring,
        suitable for LLM reading and understanding.

        Returns:
            str: Detailed explanation of the rule
        """
        doc = self.__class__.__doc__ or ""
        return doc.strip()

    @property
    def last_reason(self) -> str:
        """Get the detailed reason for the last rule execution"""
        return self._last_reason

    def set_reason(self, reason: str) -> None:
        """Set the reason for rule execution"""
        self._last_reason = reason

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
        reason: Optional[str] = None,
        **kwargs,
    ):
        """
        Create a new edge (compatibility relationship).

        Args:
            license_a: Source license
            license_b: Target license
            compatibility: Compatibility type
            scope: Compatibility scope
            reason: Reason for compatibility judgment, if None uses the last set reason
            **kwargs: Other attributes

        Returns:
            Edge: Edge representing the compatibility relationship
        """
        # If the reason parameter is not provided, use the last set reason
        if reason is None:
            reason = self.last_reason

        if scope is None:
            return Edge(
                license_a.spdx_id,
                license_b.spdx_id,
                compatibility=compatibility,
                rule=self.__class__.__name__,
                reason=reason,
                **kwargs,
            )
        return Edge(
            license_a.spdx_id,
            license_b.spdx_id,
            compatibility=compatibility,
            scope=scope,
            rule=self.__class__.__name__,
            reason=reason,
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
        """
        Check if an edge of the specified compatibility type exists in the graph.

        Args:
            license_a: Source license
            license_b: Target license
            graph: Compatibility graph
            compatibility: Compatibility type

        Returns:
            bool: True if an edge of the specified type exists, False otherwise
        """
        return bool(graph.query_edge_by_label(license_a.spdx_id, license_b.spdx_id, compatibility=compatibility))

    @abstractmethod
    def __call__(
        self, license_a: LicenseFeat, license_b: LicenseFeat, graph: GraphManager, edge: Optional[Edge] = None
    ) -> tuple[Type["CompatibleRule"], Optional[Edge]]:
        """
        Execute the rule check and return the next rule to execute and a possible edge.

        Args:
            license_a: Source license
            license_b: Target license
            graph: Compatibility graph
            edge: Optional edge for passing information

        Returns:
            tuple: (Next rule type, Optional edge)
        """


class EndRule(CompatibleRule):
    """
    Termination rule for the rule chain.

    This rule marks the end of the compatibility checking process, performing no actual checks,
    serving only as the endpoint of the rule chain. When other rules determine compatibility,
    they pass control to this rule, indicating the check is complete.
    """

    end_rule: bool = True

    def __call__(
        self, license_a: LicenseFeat, license_b: LicenseFeat, graph: GraphManager, edge: Optional[Edge] = None
    ) -> tuple[Type[CompatibleRule], Optional[Edge]]:
        self.set_reason(f"Compatibility check process ended for licenses {license_a.spdx_id} and {license_b.spdx_id}.")
        return EndRule, edge


class DefaultCompatibleRule(CompatibleRule):
    """
    Default compatibility rule.

    If all previous rule checks pass and no conflicts are found, the two licenses are considered
    unconditionally compatible. This is a "default allow" strategy - only when specific conflict
    rules are triggered will compatibility be blocked.

    When this rule is executed, it means no compatibility conflicts were found between the two
    licenses and they can be safely combined.
    """

    def __call__(
        self, license_a: LicenseFeat, license_b: LicenseFeat, graph: GraphManager, edge: Optional[Edge] = None
    ) -> tuple[Type[CompatibleRule], Optional[Edge]]:
        reason = f"Licenses {license_a.spdx_id} and {license_b.spdx_id} passed all compatibility checks, no conflicting clauses found, determined to be unconditionally compatible."
        self.set_reason(reason)
        edge = self.new_edge(license_a, license_b, compatibility=CompatibleType.UNCONDITIONAL_COMPATIBLE)
        graph.add_edge(edge)
        return EndRule, edge


class PublicDomainRule(CompatibleRule):
    """
    Public domain license compatibility rule.

    If either license is public-domain, it is considered unconditionally compatible
    with other licenses.

    Note: This is a special rule that may need modification in the future. Public domain
    works should not be compatible with licenses that prohibit modification, as this
    would violate the basic concept of public domain.

    This is the starting rule in the chain and is executed first.
    """

    start_rule: bool = True

    def __call__(
        self, license_a: LicenseFeat, license_b: LicenseFeat, graph: GraphManager, edge: Optional[Edge] = None
    ) -> tuple[Type[CompatibleRule], Optional[Edge]]:
        if license_a.spdx_id == "public-domain" or license_b.spdx_id == "public-domain":
            pd_license = "license_a" if license_a.spdx_id == "public-domain" else "license_b"
            reason = f"One of the licenses {license_a.spdx_id} and {license_b.spdx_id} is a public domain license ({pd_license}), considered unconditionally compatible by default."
            self.set_reason(reason)
            edge = self.new_edge(license_a, license_b, compatibility=CompatibleType.UNCONDITIONAL_COMPATIBLE)
            graph.add_edge(edge)
            return EndRule, edge

        self.set_reason(
            f"Neither license {license_a.spdx_id} nor {license_b.spdx_id} is a public domain license, continuing to check other rules."
        )
        return ImmutabilityRule, None


class ImmutabilityRule(CompatibleRule):
    """
    License immutability rule.

    Checks if licenses have immutability characteristics. If either license is marked
    as immutable, they are incompatible with each other. Any interoperability between
    immutable licenses will cause conflicts. Immutability is a strict restriction that
    prohibits combination with other licenses.

    Immutability is typically identified through the "immutability" property in the
    license's structured information.

    Future enhancement: May need to add checks for interoperability between immutable licenses.
    """

    start_rule: bool = False

    def __call__(
        self, license_a: LicenseFeat, license_b: LicenseFeat, graph: GraphManager, edge: Optional[Edge] = None
    ) -> tuple[Type[CompatibleRule], Optional[Edge]]:

        license_a_immut = any(self.schemas.has_property(x, "immutability") for x in license_a.features)
        license_b_immut = any(self.schemas.has_property(x, "immutability") for x in license_b.features)

        if license_a_immut or license_b_immut:
            immut_licenses = []
            if license_a_immut:
                immut_licenses.append(license_a.spdx_id)
            if license_b_immut:
                immut_licenses.append(license_b.spdx_id)

            reason = f"License(s) {', '.join(immut_licenses)} have immutability characteristics, prohibiting combination with other licenses. Determined to be incompatible."
            self.set_reason(reason)
            edge = self.new_edge(license_a, license_b, compatibility=CompatibleType.INCOMPATIBLE)
            graph.add_edge(edge)
            return EndRule, None

        self.set_reason(
            f"Neither license {license_a.spdx_id} nor {license_b.spdx_id} is marked as immutable, continuing to check other rules."
        )
        return ExceptRelicenseRule, None


class ExceptRelicenseRule(CompatibleRule):
    """
    License exception relicense rule.

    Checks if license A contains a relicense feature. If present, adds a callback
    function to check if the relicense target license is compatible with license B.
    If the target license is compatible with license B, then license A is conditionally
    compatible with license B.

    This rule handles "exception clause" cases in licenses, where certain licenses
    allow using different license terms under specific conditions. When these conditions
    are triggered, conditional compatibility relationships can be formed.

    The scope of conditional compatibility is determined by the scope of the relicense feature.
    """

    def __call__(
        self, license_a: LicenseFeat, license_b: LicenseFeat, graph: GraphManager, edge: Optional[Edge] = None
    ) -> tuple[Type["CompatibleRule"], Optional[Edge]]:
        if relicense_feat := license_a.special.get("relicense"):
            if len(relicense_feat.target) != 0:
                reason = f"License {license_a.spdx_id} contains a relicense feature, target license(s): {relicense_feat.target}. Adding callback function to check compatibility of target license(s) with {license_b.spdx_id}."
                self.set_reason(reason)
                self.add_callback(lambda licenses, graph: self.callback(licenses, graph, license_a, license_b))
        else:
            self.set_reason(
                f"License {license_a.spdx_id} does not contain a relicense feature, continuing to check other rules."
            )
        return OrLaterRelicenseRule, None

    def callback(
        self,
        licenses: Dict[str, LicenseFeat],
        graph: GraphManager,
        license_a: LicenseFeat,
        license_b: LicenseFeat,
    ) -> None:
        """
        Callback function for the relicense rule.

        Checks the compatibility of license_a's relicense target with license_b and updates
        the compatibility graph accordingly.
        If the target license is compatible with license_b, then license_a is conditionally
        compatible with license_b.

        Args:
            licenses: Set of licenses
            graph: Compatibility graph
            license_a: License containing the relicense feature
            license_b: The other license to check compatibility against
        """
        is_compatible = self.has_edge(
            license_a, license_b, graph, compatibility=CompatibleType.UNCONDITIONAL_COMPATIBLE
        )

        if is_compatible:
            self.set_reason(
                f"Licenses {license_a.spdx_id} and {license_b.spdx_id} are already unconditionally compatible, no further checks needed."
            )
            return  # No further checks needed if already unconditionally compatible

        if relicense_feat := license_a.special.get("relicense"):
            for tgt in relicense_feat.target:
                # Check if the target license is unconditionally compatible with license_b
                is_compatible = graph.query_edge_by_label(
                    tgt, license_b.spdx_id, compatibility=CompatibleType.UNCONDITIONAL_COMPATIBLE
                )

                if bool(is_compatible):
                    # Remove existing incompatible edges
                    origin_edges = graph.query_edge_by_label(
                        license_a.spdx_id, license_b.spdx_id, compatibility=CompatibleType.INCOMPATIBLE
                    )

                    for edge_index in origin_edges:
                        graph.remove_edge(edge_index)

                    reason = f"License {license_a.spdx_id} can be relicensed as {tgt}, and {tgt} is unconditionally compatible with {license_b.spdx_id}."
                    reason += f" Therefore, {license_a.spdx_id} is conditionally compatible with {license_b.spdx_id} within the scope {license_a.special['relicense'].scope}."
                    self.set_reason(reason)

                    edge = self.new_edge(
                        license_a,
                        license_b,
                        compatibility=CompatibleType.CONDITIONAL_COMPATIBLE,
                        scope=str(license_a.special["relicense"].scope),
                    )
                    graph.add_edge(edge)
                    return

                # Check if the target license is conditionally compatible with license_b
                condition_edges = graph.query_edge_by_label(
                    tgt, license_b.spdx_id, compatibility=CompatibleType.CONDITIONAL_COMPATIBLE
                )

                for edge_index in condition_edges:
                    origin_edge = graph.get_edge_data(edge_index)
                    origin_scope = Scope.from_str(origin_edge["scope"])

                    # Calculate the new compatible scope
                    new_compatible_scope = origin_scope & license_a.special["relicense"].scope
                    if not new_compatible_scope:
                        continue

                    reason = f"License {license_a.spdx_id} can be relicensed as {tgt}, and {tgt} is conditionally compatible with {license_b.spdx_id} within the scope {origin_scope}."
                    reason += f" The intersection of the two scopes is {new_compatible_scope}, therefore {license_a.spdx_id} is conditionally compatible with {license_b.spdx_id} within this scope."
                    self.set_reason(reason)

                    edge = self.new_edge(
                        license_a,
                        license_b,
                        compatibility=CompatibleType.CONDITIONAL_COMPATIBLE,
                        scope=str(new_compatible_scope),
                    )
                    graph.add_edge(edge)


class OrLaterRelicenseRule(CompatibleRule):
    """
    Or-later version license rule.

    Checks if license A contains an "or-later" identifier, indicating the license allows
    users to choose newer versions of the same license. If present, adds a callback
    function to check if higher version licenses are compatible with license B.

    For example, for GPL-2.0-or-later license, this rule checks if GPL-3.0 is compatible
    with the target license. If the higher version license is compatible with the target
    license, then the original license will also form a compatible relationship with the target.
    """

    def __call__(
        self, license_a: LicenseFeat, license_b: LicenseFeat, graph: GraphManager, edge: Optional[Edge] = None
    ) -> tuple[Type[CompatibleRule], Optional[Edge]]:
        if "or-later" in license_a.spdx_id:
            reason = f"License {license_a.spdx_id} contains the 'or-later' identifier, indicating higher versions can be used. Adding callback function to check compatibility of higher version licenses with {license_b.spdx_id}."
            self.set_reason(reason)
            self.add_callback(lambda licenses, graph: self.callback(licenses, graph, license_a, license_b))
        else:
            self.set_reason(
                f"License {license_a.spdx_id} does not contain the 'or-later' identifier, continuing to check other rules."
            )
        return ComplianceRequirementRule, None

    def get_normalized_version(self, spdx_id: str) -> list[int]:
        """
        Get the standardized version number from a license SPDX ID.

        Example: "GPL-2.0-or-later" -> [2, 0]

        Args:
            spdx_id: The SPDX ID of the license

        Returns:
            list[int]: List of standardized version numbers
        """
        return normalize_version(extract_version(spdx_id) or "")

    def rm_existed_edges(
        self,
        graph: GraphManager,
        license_a: LicenseFeat,
        license_b: LicenseFeat,
        compatibility: CompatibleType,
        bi_direct: bool = False,
    ):
        """
        Remove edges between specified licenses in the graph.

        Args:
            graph: Compatibility graph
            license_a: Source license
            license_b: Target license
            compatibility: Compatibility type of the edge to remove
            bi_direct: Whether to remove bidirectionally (also remove edge from license_b to license_a)
        """
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
        """
        Callback function for the or-later rule.

        Checks the compatibility of higher versions of license A with license B and updates
        the compatibility graph accordingly.

        Args:
            licenses: Set of licenses
            graph: Compatibility graph
            license_a: License containing the or-later identifier
            license_b: The other license to check compatibility against
        """
        current_version = self.get_normalized_version(license_a.spdx_id)
        later_licenses = filter(
            lambda x: self.get_normalized_version(x) > current_version and "or-later" not in x,
            find_all_versions(license_a.spdx_id, licenses.keys()),
        )

        is_compatible = self.has_edge(
            license_a, license_b, graph, compatibility=CompatibleType.UNCONDITIONAL_COMPATIBLE
        )

        if is_compatible:
            self.set_reason(
                f"Licenses {license_a.spdx_id} and {license_b.spdx_id} are already unconditionally compatible, no further checks needed."
            )
            return

        later_licenses = tuple(later_licenses)
        if not later_licenses:
            self.set_reason(
                f"Could not find higher version licenses for {license_a.spdx_id}, unable to perform higher version compatibility check."
            )
            return

        for tgt in later_licenses:
            # Special case: the target license is exactly the higher version
            if tgt == license_b.spdx_id:
                reason = f"License {license_a.spdx_id} allows using higher version {tgt}, which is exactly {license_b.spdx_id}, thus they should be compatible."
                self.set_reason(reason)

                self.rm_existed_edges(graph, license_a, license_b, CompatibleType.INCOMPATIBLE, True)
                edge = self.new_edge(license_a, license_b, compatibility=CompatibleType.UNCONDITIONAL_COMPATIBLE)
                graph.add_edge(edge)
                edge = self.new_edge(license_b, license_a, compatibility=CompatibleType.UNCONDITIONAL_COMPATIBLE)
                graph.add_edge(edge)
                continue

            # Check compatibility of the higher version license with the target license
            for a, b in (tgt, license_b.spdx_id), (license_b.spdx_id, tgt):
                is_compatible = graph.query_edge_by_label(a, b, compatibility=CompatibleType.UNCONDITIONAL_COMPATIBLE)

                if bool(is_compatible):
                    reason = f"License {license_a.spdx_id} allows using higher version {tgt}, and {a} is unconditionally compatible with {b}."
                    reason += f" Therefore, {license_a.spdx_id} should also be unconditionally compatible with {license_b.spdx_id}."
                    self.set_reason(reason)

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
                    # Check conditional compatibility
                    condition_edges = graph.query_edge_by_label(
                        tgt, b, compatibility=CompatibleType.CONDITIONAL_COMPATIBLE
                    )

                    for edge_index in condition_edges:
                        origin_edge = graph.get_edge_data(edge_index)

                        reason = f"License {license_a.spdx_id} allows using higher version {tgt}, and {tgt} is conditionally compatible with {b} within the scope {origin_edge.get('scope', 'Unknown')}."
                        reason += f" Therefore, {license_a.spdx_id} is also conditionally compatible with {license_b.spdx_id} within this scope."
                        self.set_reason(reason)

                        edge = self.new_edge(
                            license_a if a == tgt else license_b,
                            license_a if b == tgt else license_b,
                            compatibility=CompatibleType.CONDITIONAL_COMPATIBLE,
                            scope=origin_edge.get("scope", ""),
                            path=tgt,
                        )
                        graph.add_edge(edge)


class ComplianceRequirementRule(CompatibleRule):
    """
    Compliance requirement rule.

    Checks if compliance requirements between licenses are satisfied. Compliance requirements
    refer to constraints imposed by one license on the use of another license. If compliance
    requirements are not met, the two licenses are incompatible.

    Compliance requirements typically include required and prohibited operations. For example,
    GPL license requires derivative works to also adopt GPL license - this is a compliance
    requirement. If another license prohibits this requirement, they are incompatible.

    The rule checks compliance in both directions: license_a's requirements on license_b,
    and license_b's requirements on license_a. Failure in either direction results in
    incompatibility determination.
    """

    def check_compliance(self, license_a: LicenseFeat, license_b: LicenseFeat) -> tuple[bool, Optional[str]]:
        """
        Check if license_a's compliance requirements are met by license_b.

        This method checks the compliance requirements of license_a, ensuring they do not
        conflict with the features of license_b.
        If a conflict is found, returns False and a description of the reason for the conflict.

        Args:
            license_a: The license imposing compliance requirements
            license_b: The license being checked for compliance

        Returns:
            tuple: (Boolean indicating if requirements are met, Reason description if not met)
        """
        # Handle triggering conditions
        if license_a.special.get("triggering"):
            new_license_a = deepcopy(license_a)

            for trigger in license_a.special["triggering"].target:
                modal, action = trigger.split(".")
                getattr(new_license_a, modal)[action] = ActionFeat.factory(action, modal, [], [])
        else:
            new_license_a = license_a

        # Get features with compliance attributes
        feats_a = list(
            filter(lambda x: self.schemas.has_property(x, FeatureProperty.COMPLIANCE), new_license_a.features)
        )

        if not feats_a:
            return True, None

        for feat_a in feats_a:
            current_compliance_modals = self.schemas[feat_a.name][FeatureProperty.COMPLIANCE]

            for modal in current_compliance_modals:
                license_a_actions = getattr(new_license_a, modal)
                license_b_actions = getattr(license_b, modal)

                # Check if license_b's actions are a subset of license_a's actions
                is_subset = set(license_b_actions.keys()).issubset(set(license_a_actions.keys()))

                if not is_subset:
                    # If not a subset, check for conflicting scopes
                    for key in set(license_b_actions.keys()) - set(license_a_actions.keys()):
                        conflict_scope = license_b_actions[key].scope & feat_a.scope
                        if conflict_scope:
                            reason = f"Compliance requirement of license {license_a.spdx_id} conflicts with the {modal}.{key} feature of {license_b.spdx_id} within scope {conflict_scope}."
                            return False, reason

                # Check scope compatibility
                for key, action in license_a_actions.items():
                    if license_b_actions.get(key, False) is False:
                        continue

                    if not ActionFeatOperator.contains(action, license_b_actions[key]):
                        reason = f"The scope of the {modal}.{key} feature in license {license_a.spdx_id} is incompatible with the corresponding feature scope in {license_b.spdx_id}."
                        return False, reason

        return True, None

    def __call__(
        self, license_a: LicenseFeat, license_b: LicenseFeat, graph: GraphManager, edge: Optional[Edge] = None
    ) -> tuple[Type[CompatibleRule], Optional[Edge]]:
        """
        Execute the compliance check rule.

        Checks compliance requirements between license_a and license_b. Failure in either
        direction leads to an incompatibility determination.

        Args:
            license_a: Source license
            license_b: Target license
            graph: Compatibility graph
            edge: Optional edge for passing information

        Returns:
            tuple: (Next rule type, Optional edge)
        """
        # Check if license_a's requirements are met by license_b
        is_compliance, reason = self.check_compliance(license_a, license_b)
        if not is_compliance:
            self.set_reason(
                f"Compliance requirements of license {license_a.spdx_id} are not met by {license_b.spdx_id}: {reason}"
            )
            edge = self.new_edge(license_a, license_b, compatibility=CompatibleType.INCOMPATIBLE)
            graph.add_edge(edge)
            return EndRule, None

        # Check if license_b's requirements are met by license_a
        is_compliance, reason = self.check_compliance(license_a=license_b, license_b=license_a)
        if not is_compliance:
            self.set_reason(
                f"Compliance requirements of license {license_b.spdx_id} are not met by {license_a.spdx_id}: {reason}"
            )
            edge = self.new_edge(license_a, license_b, compatibility=CompatibleType.INCOMPATIBLE)
            graph.add_edge(edge)
            return EndRule, None

        self.set_reason(
            f"Licenses {license_a.spdx_id} and {license_b.spdx_id} passed the compliance requirement check, continuing to check other rules."
        )
        return ClauseConflictRule, None


class ClauseConflictRule(CompatibleRule):
    """
    Clause conflict rule.

    Checks for clause conflicts between licenses. Primarily checks for two types of conflicts:
    1. A "can/must" clause in license_a appears in a "cannot" clause in license_b
    2. A "cannot" clause in license_a appears in a "can/must" clause in license_b

    If a conflict exists but can be avoided within a certain scope, license A and license B
    are conditionally compatible; otherwise, they are incompatible.

    Note:
        Only the scope within license_a that can avoid the conflict is recorded. This makes
        conditional compatibility a directed graph relationship.
        For example, A might be compatible with B within scope S, but B might be compatible
        with A within a different scope T, or not compatible at all.
    """

    def __call__(
        self, license_a: LicenseFeat, license_b: LicenseFeat, graph: GraphManager, edge: Optional[Edge] = None
    ) -> tuple[Type["CompatibleRule"], Optional[Edge]]:
        """
        Execute the clause conflict check rule.

        Searches for clause conflicts between licenses and determines if they can be
        compatible within a certain scope.

        Args:
            license_a: Source license
            license_b: Target license
            graph: Compatibility graph
            edge: Optional edge for passing information

        Returns:
            tuple: (Next rule type, Optional edge)
        """
        # Check reverse compatibility
        already_compatible = self.has_edge(
            license_b, license_a, graph, compatibility=CompatibleType.UNCONDITIONAL_COMPATIBLE
        )

        if already_compatible:
            reason = f"License {license_b.spdx_id} is already unconditionally compatible with {license_a.spdx_id}, therefore {license_a.spdx_id} is also unconditionally compatible with {license_b.spdx_id}."
            self.set_reason(reason)
            return DefaultCompatibleRule, None

        condition_scope = Scope.universe()
        conflict_flag = False
        license_a_scope = Scope.universe()

        # Check modal conflicts
        for modal_pair in itertools.product(["can", "must"], ["cannot"]):
            for modal_a, modal_b in itertools.permutations(modal_pair):
                conflicts = find_duplicate_keys(getattr(license_a, modal_a), getattr(license_b, modal_b))
                for conflict in conflicts:
                    # Check if the conflicting action has conflict attributes in the schema
                    if conflict_modals := self.schemas[conflict].get("conflicts", None):
                        if not any(modal_a in modal_pair and modal_b in modal_pair for modal_pair in conflict_modals):
                            continue

                    # Calculate the conflict scope
                    conflict_scope = ActionFeatOperator.intersect(
                        getattr(license_a, modal_a)[conflict], getattr(license_b, modal_b)[conflict]
                    )

                    # If the conflict scope is empty, there is no conflict
                    if not conflict_scope:
                        continue
                    # If the conflict scope is universal, they are completely incompatible
                    elif conflict_scope.is_universal:
                        reason = f"The {modal_a}.{conflict} of license {license_a.spdx_id} conflicts with the {modal_b}.{conflict} of {license_b.spdx_id} within the universal scope, determined to be incompatible."
                        self.set_reason(reason)
                        edge = self.new_edge(license_a, license_b, compatibility=CompatibleType.INCOMPATIBLE)
                        graph.add_edge(edge)
                        return EndRule, None

                    # Calculate the compatible scope
                    compatible_scope = conflict_scope.negate()
                    compatible_scope &= getattr(license_a, modal_a)[conflict].scope

                    # If the compatible scope is empty, they are incompatible
                    if not compatible_scope:
                        reason = f"The {modal_a}.{conflict} of license {license_a.spdx_id} conflicts with the {modal_b}.{conflict} of {license_b.spdx_id},"
                        reason += " and there is no scope to avoid the conflict, determined to be incompatible."
                        self.set_reason(reason)
                        edge = self.new_edge(license_a, license_b, compatibility=CompatibleType.INCOMPATIBLE)
                        graph.add_edge(edge)
                        return EndRule, None

                    conflict_flag = True
                    # If the compatible scope is not empty, they are conditionally compatible
                    condition_scope &= compatible_scope
                    license_a_scope &= getattr(license_a, modal_a)[conflict].scope.negate() & compatible_scope

        # If no conflict was found, they are unconditionally compatible
        if not conflict_flag:
            self.set_reason(
                f"No clause conflicts found between licenses {license_a.spdx_id} and {license_b.spdx_id}, determined to be unconditionally compatible."
            )
            return DefaultCompatibleRule, None

        # If the conditional scope is empty, they are incompatible
        if not condition_scope:
            reason = f"Clause conflicts exist between licenses {license_a.spdx_id} and {license_b.spdx_id}, and the intersection of all possible compatible scopes is empty, determined to be incompatible."
            self.set_reason(reason)
            edge = self.new_edge(license_a, license_b, compatibility=CompatibleType.INCOMPATIBLE)
            graph.add_edge(edge)
            return EndRule, None

        # If there is a feasible scope, they are conditionally compatible
        if license_a_scope:
            reason = f"Clause conflicts exist between licenses {license_a.spdx_id} and {license_b.spdx_id}, but the conflict can be avoided within the scope {license_a_scope}, determined to be conditionally compatible."
            self.set_reason(reason)
            edge = self.new_edge(
                license_a,
                license_b,
                compatibility=CompatibleType.CONDITIONAL_COMPATIBLE,
                scope=str(license_a_scope),
            )
            graph.add_edge(edge)

        self.set_reason(f"Clause conflict check completed for licenses {license_a.spdx_id} and {license_b.spdx_id}.")
        return EndRule, edge


class CompatibleInfer:
    """
    License compatibility inference.

    Infers compatibility relationships between licenses based on structured information,
    generating a compatibility knowledge graph.
    This class manages a series of rules, where each rule checks different aspects
    of compatibility conditions, collectively determining license compatibility.

    Attributes:
        callback_queque: List of callback functions to be executed.
        schemas: Schema for checking license properties.
        properties_graph: Graph storing license properties.
        compatible_graph: Graph storing license compatibility relationships.
        rules: Dictionary of compatibility rules.
        start_rule: Name of the starting rule.
        end_rule: Name of the ending rule.
    """

    start_rule: str
    end_rule: str
    rules: Dict[str, CompatibleRule] = {}

    def __init__(self, schemas: Schemas, exceptions=None):
        """
        Initialize the license compatibility inferencer.

        Args:
            schemas: License schema information
            exceptions: Optional exception handling
        """
        self.callback_queque = []
        self.schemas = schemas
        self.exceptions = exceptions
        self.properties_graph = GraphManager()
        self.compatible_graph = GraphManager()
        self.compatibility_reasons = {}  # Dictionary to store compatibility reasons

        # Initialize all rules
        for rule in CompatibleRule.__subclasses__():
            the_rule = rule(self.add_callback, schemas)
            self.rules[rule.__name__] = the_rule
            if rule.start_rule:
                self.start_rule = rule.__name__
            if rule.end_rule:
                self.end_rule = rule.__name__

    def add_callback(self, callback: Callable) -> None:
        """Add a callback function to the queue"""
        self.callback_queque.append(callback)

    def check_license_property(self, license_a: LicenseFeat):
        """
        Check and record the property features of a license.

        This method adds the features of the license to the properties graph for
        later analysis and querying.

        Args:
            license_a: The license to check
        """
        license_vertex = Vertex(label=license_a.spdx_id)

        # Record all features of the license
        for feature in license_a.features:
            edge = Triple(license_vertex, Vertex(feature.name), name=feature.modal)
            self.properties_graph.add_triplet(edge)

        # Handle relicense feature
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

    def get_compatibility_reason(self, license_a: str, license_b: str) -> Optional[str]:
        """
        Get the detailed reason for the compatibility relationship between two licenses.

        Args:
            license_a: SPDX ID of the first license
            license_b: SPDX ID of the second license

        Returns:
            str: Detailed reason for the compatibility judgment, or None if not found
        """
        key = f"{license_a}:{license_b}"
        return self.compatibility_reasons.get(key)

    def check_compatibility(self, licenses: Dict[str, LicenseFeat]):
        """
        Check compatibility between licenses.

        This method checks the compatibility relationships between all pairs of licenses
        and updates the compatibility graph.
        It executes rules in the rule chain order and collects the execution reasons for each rule.

        Args:
            licenses: Dictionary of licenses to check
        """
        for license_a, license_b in itertools.product(licenses.values(), repeat=2):
            if license_a == license_b:
                continue

            edge = None
            visited = set()
            current_rule = self.rules[self.start_rule]

            # Track reasons from all rules
            all_reasons = []

            # Execute the rule chain
            expected_cls = type(self.rules[self.end_rule])
            while not isinstance(current_rule, expected_cls):
                if type(current_rule).__name__ in visited:
                    raise ValueError(
                        f"Rule {type(current_rule).__name__} was visited twice, possible circular dependency."
                    )

                # Record the current rule and its description
                visited.add(type(current_rule).__name__)
                rule_name = type(current_rule).__name__

                # Execute the rule and get the result
                next_rule_type, edge = current_rule(license_a, license_b, self.compatible_graph, edge)

                # Collect the rule execution reason
                if current_rule.last_reason:
                    all_reasons.append(f"[{rule_name}] {current_rule.last_reason}")

                # Switch to the next rule
                current_rule = self.rules[next_rule_type.__name__]

            # If an edge was generated, add the full reason trace to the edge properties
            if edge:
                # Combine all reason information into a detailed description
                full_reason = "\n".join(all_reasons)

                # Store the reason information for later querying
                reason_key = f"{license_a.spdx_id}:{license_b.spdx_id}"
                self.compatibility_reasons[reason_key] = full_reason

        # Execute all callback functions
        while len(self.callback_queque) > 0:
            callback = self.callback_queque.pop(0)
            callback(licenses, self.compatible_graph)

    def save(self, dir_path: Optional[str] = None, save_format: Optional[str] = None) -> None:
        """
        Save the properties graph and compatibility graph to the data directory.

        Args:
            dir_path: Directory path to save the graphs
            save_format: Format to save the graphs ("json", "gml")
        """

        if save_format is None:
            save_format = Settings.GRAPH_SAVE_FORMAT

        assert save_format in ["json", "gml"], f"Unsupported save format: {save_format}"

        # Merge edges and reorder
        self.properties_graph = self.properties_graph.deduplicate_and_reorder_edges()
        self.compatible_graph = self.compatible_graph.deduplicate_and_reorder_edges()

        for src, dst, data in self.compatible_graph.edges(data=True):
            reason_key = f"{src}:{dst}"
            if reason_key in self.compatibility_reasons:
                # self.compatible_graph
                data["reason"] = self.compatibility_reasons[reason_key]

        # Save graphs to the specified location
        if dir_path:
            self.properties_graph.save(
                f"{dir_path}/{Settings.LICENSE_PROPERTY_GRAPH}.{save_format}", save_format=save_format
            )
            self.compatible_graph.save(
                f"{dir_path}/{Settings.LICENSE_COMPATIBLE_GRAPH}.{save_format}", save_format=save_format
            )
        else:
            property_path = str(get_resource_path().joinpath(f"{Settings.LICENSE_PROPERTY_GRAPH}.{save_format}"))
            compatible_path = str(get_resource_path().joinpath(f"{Settings.LICENSE_COMPATIBLE_GRAPH}.{save_format}"))
            self.properties_graph.save(property_path, save_format=save_format)
            self.compatible_graph.save(compatible_path, save_format=save_format)
