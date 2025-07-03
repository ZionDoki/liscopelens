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

"""
The constants of the project. 

The constants are used to store the configurations of the project,
and the enum types are used to define the types of the project.
"""

from enum import StrEnum, IntEnum


class Settings(StrEnum):
    """configurations of the project."""

    PACKAGE_NAME = "liscopelens"
    RESOURCE_NAME = "resources"
    LICENSE_PROPERTY_GRAPH = "properties_graph"
    LICENSE_COMPATIBLE_GRAPH = "compatible_graph"
    LICENSE_FEATURE = "licenses_feature.json"
    GRAPH_SAVE_FORMAT = "json"



class CompatibleType(IntEnum):
    """
    Enum type of compatibility graph edges.

    - UNCONDITIONAL_COMPATIBLE: The licenses are compatible unconditionally.
    - CONDITIONAL_COMPATIBLE: The licenses are compatible conditionally.
    - INCOMPATIBLE: The licenses are incompatible.
    - UNKNOWN: The compatibility of the licenses is unknown, this will cause the warning.

    The compatibility graph is a directed graph, and the edge from license A to license B
    means the compatibility of license A to license B.

    Direction in CONDITIONAL_COMPATIBLE edge means from License A could find a way that
    TODO: ...
    """

    UNCONDITIONAL_COMPATIBLE = 0
    CONDITIONAL_COMPATIBLE = 1
    PARTIAL_INCOMPATIBLE = 2
    INCOMPATIBLE = 3
    UNKNOWN = 4


class FeatureType(StrEnum):
    """enum type of feature type."""

    CAN = "can"
    CANNOT = "cannot"
    MUST = "must"
    SPECIAL = "special"


class FeatureProperty(StrEnum):
    """enum type of feature property."""

    COMPLIANCE = "compliance"


class ScopeToken(StrEnum):
    """enum type of scope token."""

    UNIVERSE = "UNIVERSAL"


class ScopeElement(StrEnum):
    """
    enum type of scope element.

    ! The value must be consistent with the member variable.
    """

    COMPILE = "COMPILE"
    DYNAMIC_LINKING = "DYNAMIC_LINKING"
    STATIC_LINKING = "STATIC_LINKING"
    EXECUTABLE = "EXECUTABLE"
    IN_CATEGORY = "IN_CATEGORY"
    GENERATED = "GENERATED"
    TRADEMARK = "TRADEMARK"
    SOURCE_FORM = "SOURCE_FORM"
    OBJECT_FORM = "OBJECT_FORM"
    DERIVED = "DERIVED"
    ASK_FOR_AUTH = "ASK_FOR_AUTH"
