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

from .build_gn_parser import GnParser

from lict.parser.echo import EchoPaser
from lict.parser.scancode import ScancodeParser
from lict.parser.exception import BaseExceptionParser
from lict.parser.base import BaseParser, BaseParserEntry
from lict.parser.compatible import BaseCompatiblityParser


class CParserEntry(BaseParserEntry):
    parsers: tuple[BaseParser] = (
        GnParser,
        ScancodeParser,
        BaseExceptionParser,
        BaseCompatiblityParser,
        EchoPaser,
    )

    entry_name: str = "cParser"
    entry_help: str = (
        "This parser is used to parse the C/C++ repository and provide an include dependency graph for "
        "subsequent operations"
    )
