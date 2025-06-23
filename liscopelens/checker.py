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

import warnings

from typing import Optional

from liscopelens.constants import CompatibleType
from liscopelens.infer import generate_knowledge_graph
from liscopelens.utils.structure import LicenseFeat, Scope


class Checker:
    """Compatibility checker class"""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):

        if Checker._initialized:
            return

        self.infer = generate_knowledge_graph(reinfer=True)
        Checker._initialized = True

    @property
    def properties_graph(self):
        """Return the properties graph"""
        return self.infer.properties_graph

    @property
    def compatible_graph(self):
        """Wrapper for the compatible graph"""
        return self.infer.compatible_graph

    def is_license_exist(self, license_name: str) -> bool:
        """
        Check if the license exists in the properties graph

        Args:
            - license_name: The name of the license

        Returns:
            - True if the license exists, False otherwise
        """
        # * because the node may return {}, only return is None we can sure the node is not exist

        return self.properties_graph.query_node_by_label(license_name) is not None

    def is_copyleft(self, license_name: str) -> bool:
        """
        Check if the license is copyleft

        Args:
            - license_name: The name of the license

        Returns:
            - True if the license is copyleft, False otherwise
        """
        if not self.is_license_exist(license_name):
            raise ValueError(f"The license {license_name} does not exist")
        for _, target, data in self.properties_graph.graph.out_edges(license_name, data=True):
            if data.get("name") == "must" and target == "set_same_license":
                return True
        return False

    def get_relicense(self, license_name: str, scope: Optional[Scope] = None) -> str | None:
        """
        Get the relicense of the license

        Args:
            - license_name: The name of the license
            - scope: (Optional) The scope of the scenes to be used in project

        Returns:
            - The name of the relicense
        """
        if not self.is_license_exist(license_name):
            raise ValueError(f"The license {license_name} does not exist")
        for _, target, data in self.properties_graph.graph.out_edges(license_name, data=True):
            if data.get("name") == "relicense":
                target_scope = Scope.from_str(data.get("scope", ""))
                if scope and scope in target_scope:
                    return target
        return None

    def get_modal_features(self, license_name: str, modal: str) -> set[str]:
        """
        Get the modal features of the license

        Args:
            - license_name: The name of the license
            - modal: The name of the modal

        Returns:
            - The modal features of the license
        """
        if not self.is_license_exist(license_name):
            raise ValueError(f"The license {license_name} does not exist")

        rets = set()
        for _, target, data in self.properties_graph.graph.out_edges(license_name, data=True):
            if data.get("name") == modal:
                rets.add(target)
        return rets

    def check_compatibility(
        self,
        license_a: str | LicenseFeat,
        license_b: str | LicenseFeat,
        scope: Scope,
    ) -> CompatibleType:
        """
        Check the compatibility between two licenses

        Args:
            - license_a: The name of the first license
            - license_b: The name of the second license
            - scope: (Optional) The scope of the scenes to be used in project

        Returns:
            - The compatibility type of the two licenses
        """

        if scope and not isinstance(scope, Scope):
            raise ValueError("scope should be a Scope object")

        if isinstance(license_a, str):
            license_a_id = license_a
        elif isinstance(license_a, LicenseFeat):
            license_a_id = license_a.spdx_id
        else:
            raise ValueError("license_a should be either a string or a LicenseFeat object")

        if isinstance(license_b, str):
            license_b_id = license_b
        elif isinstance(license_b, LicenseFeat):
            license_b_id = license_b.spdx_id
        else:
            raise ValueError("license_b should be either a string or a LicenseFeat object")

        edge_index = self.compatible_graph.query_edge_by_label(license_a_id, license_b_id)
        if edge_index:
            edge = self.compatible_graph.get_edge_data(edge_index[0])
            if edge and edge["compatibility"] == CompatibleType.CONDITIONAL_COMPATIBLE:

                compatible_scope = Scope.from_str(edge["scope"])

                if scope in compatible_scope:
                    return CompatibleType.CONDITIONAL_COMPATIBLE

                return CompatibleType.INCOMPATIBLE

            return CompatibleType(edge.get("compatibility", CompatibleType.UNKNOWN))
        else:
            warnings.warn(f"The compatibility of the licenses {license_a_id}->{license_b_id} is unknown")
            return CompatibleType.UNKNOWN
