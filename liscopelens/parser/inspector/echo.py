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
from pathlib import Path
from pprint import pformat
from typing import Optional
from argparse import Namespace

from rich.progress import Progress

from liscopelens.utils import set2list
from liscopelens.utils.structure import Config
from liscopelens.utils.graph import GraphManager

from liscopelens.parser.base import BaseParser


class EchoPaser(BaseParser):

    arg_table = {
        "--echo": {"action": "store_true", "help": "Echo the final result of compatibility checking", "default": False}
    }

    def __init__(self, args: Namespace, config: Config):
        super().__init__(args, config)

    def parse(self, project_path: Path, context: Optional[GraphManager] = None) -> GraphManager:

        need_echo = getattr(self.args, "echo", False)
        output = getattr(self.args, "output", "")

        if context is None:
            raise ValueError("Context is required for echo parser")

        if not need_echo:
            return context

        with Progress() as progress:
            total_nodes = len(context.graph.nodes)
            task = progress.add_task("[green]Output results...", total=total_nodes)
            results = {}
            for node, node_data in context.nodes(data=True):
                conflict_id = node_data.get("conflict_id", None)
                if conflict_id:
                    conflict_data = results.get(conflict_id, {})
                    conflict_data["files"] = conflict_data.get("files", set())
                    conflict_data["files"].add(node)
                    results[conflict_id] = conflict_data

                conflict = node_data.get("conflict", [])
                if conflict:
                    conflict_data = results.get(conflict["id"], {})
                    conflict_data["conflicts"] = conflict_data.get("conflicts", conflict["conflicts"])
                    results[conflict["id"]] = conflict_data

                progress.update(task, advance=1)

        if output:
            with open(output + "/results.json", "w", encoding="utf-8") as f:
                f.write(json.dumps(results, default=lambda x: set2list(x) if isinstance(x, set) else str(x)))
        else:
            print(pformat(results))

        return context
