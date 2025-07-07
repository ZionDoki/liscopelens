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
Hvigor project parser constants.
"""

from enum import Enum


TS_EXTS = {".ts", ".js", ".ets"}
NATIVE_EXTS = {".c", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".so", ".a", ".o", ".hh"}


class HvigorProfile(Enum):
    """
    Enum for Hvigor profile types.
    """

    PACKAGE_PROFILE = "oh-package.json5"
    BUILD_PROFILE = "build-profile.json5"
    APP_PROFILE = "AppScope/app.json5"
    MODULE_PROFILE = "src/*/module.json5"
    HVIGOR_PROFILE = "hvigor/hvigor-config.json5"


class HvigorVertexType(Enum):
    """
    Enum for Hvigor vertex types.
    """

    PROJECT = "project"
    MODULE = "module"
    NATIVE_MODULE = "native_module"
    NATIVE_CODE = "native_code"
    ARKTS_CODE = "arkts_code"
    RESOURCE = "resource"
    FILE = "file"
    UNKNOWN = "unknown"
    EXTERNAL_PACKAGE = "external_package"
    MODULE_ENTRY = "entry"
    MODULE_HAR = "har"
    MODULE_SHARE = "shared"
    MODULE_FEATURE = "feature"


class HvigorEdgeType(Enum):
    """
    Enum for Hvigor edge types.

    - deps: reliable dep relation inferred from build profile or source code imports
    - contains: contains relation extract from file structure
    """

    DEPENDS = "deps"
    CONTAINS = "contains"
