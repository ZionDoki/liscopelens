# coding=utf-8
# Author: Zion
# Date: 2024/05/21
# Contact: liuza20@lzu.edu.cn

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

    def add_license(self, context: GraphManager, file_path: str, spdx_results: DualLicense):
        parent_label = "//" + file_path.replace("\\", "/")

        context_node = context.nodes.get(parent_label, None)

        if not context_node:
            return

        if spdx_results:
            context_node["licenses"] = spdx_results

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

    def parse_json(self, json_path: str, context: GraphManager) -> GraphManager:

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
                        expand=True,
                        proprocessor=self.remove_ref_lang if self.args.rm_ref_lang else None,
                    )

                    self.add_license(context, file_path, spdx_results)

            for file in scancode_results["files"]:
                if rel_path:
                    file_path = os.path.join(rel_path, file["path"])
                else:
                    file_path = os.path.relpath(file["path"], file["path"].split(os.sep)[0])
                if file["detected_license_expression_spdx"]:
                    spdx_results = self.spdx_parser(file["detected_license_expression_spdx"], file_path, expand=True)

                    self.add_license(context, file_path, spdx_results)

    def parse(self, project_path: str, context: GraphManager) -> GraphManager:
        """
        The path of the scancode's output is relative path, whatever you pass absolute path or relative path.

        eg.
        ```shell
        scancode --json-pp license.json .
        # or
        scanode --json-pp license.json /path/to/your/project

        # the path of the scancode's output is relative path
        ```
        """

        if getattr(self.args, "scancode_file", None):
            if not os.path.exists(self.args.scancode_file):
                raise FileNotFoundError(f"File not found: {self.args.scancode_file}")
            self.parse_json(self.args.scancode_file, context)
            return context
        elif getattr(self.args, "scancode_dir", None):
            if not os.path.exists(self.args.scancode_dir):
                raise FileNotFoundError(f"Directory not found: {self.args.scancode_dir}")
            for root, _, files in track(os.walk(self.args.scancode_dir), "Parsing scancode's output..."):
                for file in files:
                    if file.endswith(".json"):
                        self.parse_json(os.path.join(root, file), context)
            return context
        else:
            raise ValueError("The path of the scancode's output is not provided.")
