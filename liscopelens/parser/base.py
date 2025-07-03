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
The base classes of Parsers.
"""
import argparse
import warnings
from typing import Any, Dict, Tuple, Optional, Type

from abc import ABC, abstractmethod
from liscopelens.utils.graph import GraphManager, Vertex, Edge
from liscopelens.utils.structure import Config


class BaseParser(ABC):
    """
    Properties:
        - arg_table: A dictionary that contains the arguments for the parser. The key is the argument name,
            and the value is a dictionary that contains the following keys:
                - type: the type of the argument
                - help: the help message of the argument
                - group: the group name of the argument (add to a mutually exclusive group if not None)
        - args: The parsed arguments. When Entry is initialized, the args will be passed to the parser.
        - config: The configuration of the parser. The configuration will be passed to the parser when Entry is initialized.
    """

    arg_table: Dict[str, Dict[str, Any]]

    def __init__(self, args: argparse.Namespace, config: Config):
        self.args = args
        self.config = config

    def create_vertex(self, label: str, **kwargs: Any) -> Vertex:
        """Create a vertex"""
        return Vertex(label, parser_name=self.__class__.__name__, **kwargs)

    def create_edge(self, u: str, v: str, **kwargs: Any) -> Edge:
        """Create an edge between two vertices"""
        return Edge(u, v, parser_name=self.__class__.__name__, **kwargs)

    @abstractmethod
    def parse(self, project_path: str, context: Optional[GraphManager] = None) -> GraphManager:
        """
        Parse the arguments and update the context

        Args:
            - project_path: The path of the project
            - context: The context (GraphManager) of the project

        Returns:
            - The updated context
        """
        raise NotImplementedError


class BaseParserEntry:
    """
    Properties:
        - parsers: A tuple of the parsers that will be used in this entry
        - entry_help: The help message of this entry
        - arg_parser: The argument parser of this entry
    """

    parsers: Tuple[Type[BaseParser], ...]
    entry_help: str = ""
    arg_parser: argparse.ArgumentParser | None = None

    def __init__(self, args: argparse.Namespace, config: Config):
        """
        when user input the command liscopelens [entry_name] hit the enter key, the parser will be initialized.
        """
        if self.parsers is None:
            raise NotImplementedError("No parsers found")

        if self.entry_help == "":
            warnings.warn("No entry help provided")

        self._parsers = (p(args, config) for p in self.parsers)

    def parse(self, project_path: str, context: Optional[GraphManager] = None):
        """
        Parse the arguments and update the context

        Args:
            - project_path: The path of the project
            - context: The context (GraphManager) of the project

        Returns:
            - None, but any return could add when inheriting this class.

            ! Attention: you should add the return type in the subclass. If there is output file or cli
            ! output, you should implement that logic in the subclass parse method.
        """

        if context is None:
            context = GraphManager()

        for p in self._parsers:
            context = p.parse(project_path, context)
        # Add arguments to arg_parser here if needed
