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

from liscopelens.parser.scancode import ScancodeParser
from liscopelens.parser.exception import BaseExceptionParser
from liscopelens.parser.base import  BaseParserEntry
from liscopelens.parser.compatible import BaseCompatiblityParser
from liscopelens.parser.propagate import BasePropagateParser
from liscopelens.parser.inspector.echo import EchoPaser
from liscopelens.parser.clang.gn import GnParser
from liscopelens.parser.clang.inspect import ClangInspectParser

class CParserEntry(BaseParserEntry):
    parsers = (
        GnParser,
        ScancodeParser,
        BaseExceptionParser,
        BasePropagateParser,
        BaseCompatiblityParser,
        EchoPaser,
    )

    entry_name: str = "clang"
    entry_help: str = (
        "This parser is used to parse the C/C++ repository and provide an include dependency graph for "
        "subsequent operations"
    )

class CExportSubgraphEntry(BaseParserEntry):
    parsers = (
        ClangInspectParser,
    )

    entry_name: str = "subgraph"
    entry_help: str = "This parser is used to export the subgraph of the C/C++ repository"
