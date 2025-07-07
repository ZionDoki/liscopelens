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
Hvigor parser entry point.
"""

# import os
# import copy
# import argparse

# from liscopelens.utils.structure import Config
from liscopelens.parser.base import BaseParserEntry

# from liscopelens.parser.scancode import ScancodeParser
# from liscopelens.parser.exception import BaseExceptionParser
# from liscopelens.parser.compatible import BaseCompatiblityParser
# from liscopelens.parser.propagate import BasePropagateParser
# from liscopelens.parser.inspector.echo import EchoPaser


class HvigorParserEntry(BaseParserEntry):
    """
    The entry for Hvigor parser.
    This entry will be used when user input the command `liscopelens hvigor`.
    """

    parsers = (
        # HvigorModuleParser,
        # HvigorArkTSMappingParser,
        # HvigorNativeMappingParser,
        # ScancodeParser,
        # BaseExceptionParser,
        # BasePropagateParser,
        # BaseCompatiblityParser,
        # EchoPaser,
    )
    entry_help = "Parse Hvigor project dependency graph and perform license compatibility analysis."
    entry_name = "hvigor"
