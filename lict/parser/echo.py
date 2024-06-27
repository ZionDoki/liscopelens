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

import json
from pprint import pformat

from .base import BaseParser
from argparse import Namespace
from lict.utils.structure import Config
from lict.utils.graph import GraphManager


class EchoPaser(BaseParser):

    arg_table = {
        "--echo": {
            "action": "store_true",
            "help": "Echo the final result of compatibility checking",
            "default": False,
        },
        "--out-echo": {
            "type": str,
            "help": "The output path of the echo result",
            "default": "",
        },
    }

    def __init__(self, args: Namespace, config: Config):
        super().__init__(args, config)

    def parse(self, project_path: str, context: GraphManager = None) -> GraphManager:

        need_echo = getattr(self.args, "echo", False)
        out_echo = getattr(self.args, "out_echo", "")
        if not need_echo:
            return context

        results = []
        for edge_index, edge_data in context.filter_edges(type="compatible_result"):
            source, target, _ = edge_index

            results.append(
                {
                    "parents": set(context.predecessors(source)) & set(context.predecessors(target)),
                    "conflicts": edge_data["conflict"],
                    source: context.nodes[source],
                    target: context.nodes[target],
                    "results": "INCOMPATIBLE",
                }
            )

        if out_echo:
            with open(out_echo, "w") as f:
                f.write(json.dumps(results, default=str))
        else:
            print(pformat(results))

