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

import copy
from pathlib import Path

# from liscopelens.utils.structure import Config
from liscopelens.parser.base import BaseParserEntry

from liscopelens.parser.scancode import ScancodeParser
from liscopelens.parser.exception import BaseExceptionParser
from liscopelens.parser.compatible import BaseCompatiblityParser
from liscopelens.parser.propagate import BasePropagateParser
from liscopelens.parser.inspector.echo import EchoPaser

from .base import HvigorParser


class HvigorParserEntry(BaseParserEntry):
    """
    The entry for Hvigor parser.
    This entry will be used when user input the command `liscopelens hvigor`.
    """

    parsers = (
        HvigorParser,
        ScancodeParser,
        BaseExceptionParser,
        BasePropagateParser,
        BaseCompatiblityParser,
        EchoPaser,
    )
    entry_help = "Parse Hvigor project dependency graph and perform license compatibility analysis."
    entry_name = "hvigor"


class BatchHvigorParserEntry(HvigorParserEntry):
    """
    The entry for batch Hvigor parser.
    This entry will be used when user input the command `liscopelens hvigor-batch`.
    It will parse multiple Hvigor projects in a specified directory.
    """

    entry_help = "批量解析 Hvigor 项目依赖图并执行许可证兼容性分析。"
    entry_name = "hvigor-batch"

    def parse(self, project_path, context=None):
        """
        parse multiple Hvigor projects in a specified directory.

        Args:
            project_path (str or Path): The path to the directory containing Hvigor projects.
            context (optional): Additional context for parsing, if needed.

        Raises:
            ValueError: If the provided project path does not exist or is not a directory.
        """

        project_path = Path(project_path)
        if not project_path.exists() or not project_path.is_dir():
            raise ValueError(f"Invalid batch detection path: {project_path}")

        processed_projects = []

        for first_level in project_path.iterdir():
            if not first_level.is_dir():
                continue  # Skip files

            try:
                # Create a copy of the current project's args
                project_args = copy.deepcopy(self.args)

                # Rewrite output parameter
                if hasattr(project_args, "output") and project_args.output:
                    original_output = Path(project_args.output)
                    project_name = first_level.name
                    new_output = original_output / project_name
                    project_args.output = str(new_output)

                    # Ensure output directory exists
                    new_output.mkdir(parents=True, exist_ok=True)

                # Create a new parser instance for the current project
                batch_entry = HvigorParserEntry(project_args, self.config)

                # Perform basic entry detection
                print(f"Detecting project: {first_level}")
                batch_entry.parse(first_level, context)

                processed_projects.append(first_level.name)

            except (OSError, AttributeError, ValueError) as e:
                print(f"Error detecting project {first_level}: {e}")
                continue

        if processed_projects:
            print(f"Batch detection complete. Processed {len(processed_projects)} projects:")
            for project in processed_projects:
                print(f"  - {project}")
        else:
            print("No valid Hvigor projects found for batch detection.")
