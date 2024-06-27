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

import argparse

from .infer import *
from .utils import load_config
from .parser import PARSER_ENTRIES


def cli():
    parser = argparse.ArgumentParser(description="部件兼容性分析工具")
    parser.add_argument("-c", "--config", type=str, default="", help="配置文件路径")

    subparsers = parser.add_subparsers(dest="command", required=True)
    for entry_name, parser_entry in PARSER_ENTRIES.items():
        sub_parser = subparsers.add_parser(entry_name, help=parser_entry.entry_help)
        arg_groups = {}
        for p in parser_entry.parsers:
            for args_name, args_setting in p.arg_table.items():

                if "group" in args_setting:
                    group_name = args_setting.pop("group")
                    if group_name not in arg_groups:
                        arg_groups[group_name] = sub_parser.add_mutually_exclusive_group(required=True)

                    arg_groups[group_name].add_argument(args_name, **args_setting)

                else:
                    sub_parser.add_argument(args_name, **args_setting)

    args = parser.parse_args()

    if args.config:
        config = load_config(args.config)
    else:
        config = load_config()

    PARSER_ENTRIES[args.command](args, config).parse("", None)

    # TODO: return or output the result
