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
The basic parser for the exception licenses.
"""

import copy
import warnings
from argparse import Namespace

from typing import Optional

from lict.checker import Checker
from lict.utils.graph import GraphManager, Edge
from lict.utils.structure import Config, load_licenses, load_exceptions

from .base import BaseParser


class BaseExceptionParser(BaseParser):
    """
    Base class for the exception parser.

    Usage:
        ```
        class OtherParser(BaseExceptionParser):

            ... # implement the parse method

        parser = OtherParser(args, config)
        parser.parse(project_path, context)
        ```

    """

    arg_table = {
        "--ignore-unk": {"action": "store_true", "help": "Ignore unknown licenses", "default": False},
        "--save-kg": {"action": "store_true", "help": "Save new knowledge graph after infer parse", "default": False},
    }

    def __init__(self, args: Namespace, config: Config):
        super().__init__(args, config)
        self.checker = Checker()

        self.all_licenes = load_licenses()
        self.all_exceptions = load_exceptions()

    def parse(self, project_path: str, context: Optional[GraphManager] = None) -> GraphManager:

        if context is None:
            raise ValueError("The context is required for the exception parser.")

        save_kg = getattr(self.args, "save_kg", False)
        ignore_unk = getattr(self.args, "ignore_unk", False)
        blacklist = getattr(self.config, "blacklist", [])

        visited_licenses, new_for_infer = set(), {}

        for _, node_data in context.nodes(data=True):
            dual_license = node_data.get("licenses")
            if not dual_license:
                continue

            for group in dual_license:
                for unit in group:

                    if unit["spdx_id"] not in self.all_licenes:
                        if not ignore_unk:
                            warnings.warn(f"Unknown license: {unit['spdx_id']}")
                        continue

                    new_feat = self.all_licenes[unit["spdx_id"]]
                    for exception in unit["exceptions"]:
                        if exception not in self.all_exceptions:
                            if not ignore_unk:
                                raise ValueError(f"Unknown exception: {exception}")
                            continue

                        new_feat = new_feat.cover_from(self.all_exceptions[exception])

                    if new_feat == self.all_licenes[unit["spdx_id"]]:
                        continue

                    if self.checker.is_license_exist(new_feat.spdx_id):
                        continue

                    if new_feat.spdx_id in visited_licenses:
                        continue
                    visited_licenses.add(new_feat.spdx_id)
                    new_for_infer[new_feat.spdx_id] = new_feat

        self.checker.infer.check_compatibility({**self.all_licenes, **new_for_infer})
        if save_kg:
            self.checker.infer.save()

        print("Remove or-later compatible edges involving blacklist.")
        for spdx_id in blacklist:
            for edge_index, _ in tuple(self.checker.compatible_graph.filter_edges(path=spdx_id)):
                src_node, dst_node = edge_index[0], edge_index[1]

                if "or-later" in src_node:
                    src_license, dst_license = src_node.replace("-or-later", "-only"), dst_node
                else:
                    src_license, dst_license = src_node, dst_node.replace("-or-later", "-only")

                edges = self.checker.compatible_graph.query_edge_by_label(src_license, dst_license)
                for edge in edges:
                    edge_data = self.checker.compatible_graph.get_edge_data(edge)
                    self.checker.compatible_graph.add_edge(Edge(src_node, dst_node, **copy.deepcopy(edge_data)))

                self.checker.compatible_graph.remove_edge(edge_index)

        return context
