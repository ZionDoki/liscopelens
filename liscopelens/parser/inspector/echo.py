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
from liscopelens.utils.structure import DualLicense

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
                # Maintain legacy output unchanged using licenses-based filtering
                conflict = node_data.get("conflict", [])
                if conflict:
                    conflict_data = results.get(conflict["id"], {})
                    conflict_data["conflicts"] = conflict_data.get("conflicts", conflict["conflicts"])
                    results[conflict["id"]] = conflict_data

                # New: also support conflict_group without changing previous schema
                conflict_group = node_data.get("conflict_group")
                if isinstance(conflict_group, (set, list, tuple)):
                    for gid in conflict_group:
                        if not gid:
                            continue
                        # Use licenses filter to include only nodes genuinely implicated
                        current_licenses = node_data.get("licenses")
                        outbound = node_data.get("outbound")
                        # Convert serialized lists to DualLicense if needed
                        if isinstance(current_licenses, list):
                            try:
                                current_licenses = DualLicense.from_list(current_licenses)
                            except Exception:
                                current_licenses = None
                        if isinstance(outbound, list):
                            try:
                                outbound = DualLicense.from_list(outbound)
                            except Exception:
                                outbound = None
                        if not current_licenses or not outbound:
                            continue

                        # Only add when a conflicting license actually appears in both sets
                        conflicts = context.graph.graph.get("conflicts_table", {}).get(gid)
                        # Fallback: infer from node's own conflict if present
                        if conflicts is None and conflict:
                            conflicts = conflict.get("conflicts")
                        if not conflicts:
                            continue

                        implicated = False
                        flat_conf = set()
                        for pair in conflicts:
                            for lic in pair:
                                flat_conf.add(lic)
                        for lic in flat_conf:
                            if current_licenses.has_license(lic) and outbound.has_license(lic):
                                implicated = True
                                break
                        if not implicated:
                            continue

                        conflict_data = results.get(gid, {})
                        conflict_data["conflicts"] = conflict_data.get("conflicts", conflicts)
                        conflict_data["files"] = conflict_data.get("files", set())
                        conflict_data["files"].add(node)
                        results[gid] = conflict_data

                progress.update(task, advance=1)

        if output:
            with open(output + "/results.json", "w", encoding="utf-8") as f:
                f.write(json.dumps(results, default=lambda x: set2list(x) if isinstance(x, set) else str(x)))
        else:
            print(pformat(results))

        return context
