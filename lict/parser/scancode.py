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

import os
import re
import json
import argparse
from rich.progress import track

from .base import BaseParser
from lict.checker import Checker
from lict.utils.graph import GraphManager
from lict.utils.structure import DualLicense, SPDXParser, Config


class ScancodeParser(BaseParser):

    arg_table = {
        "--scancode-file": {
            "type": str,
            "help": "The path of the scancode's output in json format file",
            "group": "scancode",
        },
        "--scancode-dir": {
            "type": str,
            "help": "The path of the directory that contain json files",
            "group": "scancode",
        },
        "--shadow-license": {
            "type": str,
            "help": "The file path which storage (node-license) pair. Shadow licenses to certain nodes in advance",
            "default": None,
        },
        "--rm-ref-lang": {
            "action": "store_true",
            "help": "Automatically remove scancode ref prefix and language suffix from spdx ids",
            "default": False,
        },
    }

    def __init__(self, args: argparse.Namespace, config: Config):
        super().__init__(args, config)
        self.checker = Checker()
        self.spdx_parser = SPDXParser()
        self.count = set()

    def add_license(self, context: GraphManager, file_path: str, spdx_results: DualLicense, test):
        parent_label = "//" + file_path.replace("\\", "/")

        context_node = context.nodes.get(parent_label, None)

        if context_node and spdx_results:
            context_node["licenses"] = spdx_results
            context_node["test"] = test
            self.count.add(parent_label)

    def parse_shadow(self, json_path: str, context: GraphManager):
        """
        Parse the shadow license file and add the license to the context.

        Usage:
            ```python

            parser = ScancodeParser(args, config)
            context = parser.parse_shadow("shadow.json", context)
            ```
        """
        if context is None:
            raise ValueError(f"Context can not be None in {self.__class__.__name__}.")
        with open(json_path, "r") as f:
            scancode_results = json.load(f)
        spdx = SPDXParser()
        for key, values in scancode_results.items():
            license = spdx(values)
            context.modify_node_attribute(key, "licenses", license)
        return context

    def remove_ref_lang(self, spdx_id: str) -> str:

        if not self.checker.is_license_exist(spdx_id):
            new_spdx_id = re.sub(r"LicenseRef-scancode-", "", spdx_id)
            if self.checker.is_license_exist(new_spdx_id):
                return new_spdx_id
            new_spdx_id = re.sub(r"-(en|cn)$", "", new_spdx_id)
            if self.checker.is_license_exist(new_spdx_id):
                return new_spdx_id
            return spdx_id

        return spdx_id

    def parse_json(self, json_path: str, context: GraphManager):

        if context is None:
            raise ValueError(f"Context can not be None in {self.__class__.__name__}.")

        if root_path := getattr(self.args, "scancode_dir", None):
            rel_path = os.path.relpath(os.path.dirname(json_path), root_path)
        else:
            rel_path = None

        with open(json_path, "r") as f:
            scancode_results = json.load(f)

            for detects in scancode_results["license_detections"]:
                for match in detects["reference_matches"]:
                    if rel_path:
                        file_path = os.path.join(rel_path, match["from_file"])
                    else:
                        file_path = os.path.relpath(match["from_file"], match["from_file"].split(os.sep)[0])

                    spdx_results = self.spdx_parser(
                        match["license_expression_spdx"],
                        file_path,
                        proprocessor=self.remove_ref_lang if self.args.rm_ref_lang else None,
                    )

                    if spdx_results:
                        self.add_license(context, file_path, spdx_results, match["license_expression_spdx"] + "_m")

            for file in scancode_results["files"]:
                if rel_path:
                    file_path = os.path.join(rel_path, file["path"])
                else:
                    file_path = os.path.relpath(file["path"], file["path"].split(os.sep)[0])
                if file["detected_license_expression_spdx"]:

                    spdx_results = self.spdx_parser(file["detected_license_expression_spdx"], file_path)

                    self.add_license(context, file_path, spdx_results, file["detected_license_expression_spdx"] + "_f")

    def parse(self, project_path: str, context: GraphManager) -> GraphManager:
        """
        The path of the scancode's output is relative path, whatever you pass absolute path or relative path.

        Usage:
        ```shell
        scancode --json-pp license.json .
        # or
        scancode --json-pp license.json /path/to/your/project

        # the path of the scancode's output is relative path
        ```
        """

        if getattr(self.args, "scancode_file", None):
            if not os.path.exists(self.args.scancode_file):
                raise FileNotFoundError(f"File not found: {self.args.scancode_file}")
            self.parse_json(self.args.scancode_file, context)
        elif getattr(self.args, "scancode_dir", None):
            if not os.path.exists(self.args.scancode_dir):
                raise FileNotFoundError(f"Directory not found: {self.args.scancode_dir}")
            for root, _, files in track(os.walk(self.args.scancode_dir), "Parsing scancode's output..."):
                for file in files:
                    if file.endswith(".json"):
                        self.parse_json(os.path.join(root, file), context)

            json.dump(
                list(
                    set(node[0] for node in context.nodes(data=True) if node[1].get("type", None) == "code")
                    - self.count
                ),
                open("scancode.json", "w"),
            )
        else:
            raise ValueError("The path of the scancode's output is not provided.")

        if getattr(self.args, "shadow_license", None):
            print("Parsing shadow license...")
            self.parse_shadow(self.args.shadow_license, context)

        if output := getattr(self.args, "output", None):
            os.makedirs(output, exist_ok=True)
            context.save(output + "/origin.gml")

        return context
