import argparse
import warnings
from typing import Any, Dict, Tuple
from abc import ABC, abstractmethod
from lict.utils.graph import GraphManager, Vertex, Edge
from lict.utils.structure import Config


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

    def is_unk_license(self, spdx_id: str) -> bool:
        return spdx_id not in self.licenses

    def create_vertex(self, label: str, **kwargs: dict) -> Vertex:
        return Vertex(label, parser_name=self.__class__.__name__, **kwargs)

    def create_edge(self, u: str, v: str, **kwargs: dict) -> Edge:
        return Edge(u, v, parser_name=self.__class__.__name__, **kwargs)

    @abstractmethod
    def parse(self, project_path: str, context: GraphManager = None) -> GraphManager:
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

    parsers: Tuple[BaseParser] = ()
    entry_help: str = ""
    arg_parser: argparse.ArgumentParser = None

    def __init__(self, args: argparse.Namespace, config: Config):
        """
        when user input the command lict [entry_name] hit the enter key, the parser will be initialized.
        """
        if len(self.parsers) == 0:
            raise NotImplementedError("No parsers found")

        if self.entry_help == "":
            warnings.warn("No entry help provided")

        self.parsers = (p(args, config) for p in self.parsers)

    def parse(self, project_path: str, context: GraphManager = None, args: argparse.Namespace = None):
        """
        Parse the arguments and update the context

        Args:
            - project_path: The path of the project
            - context: The context (GraphManager) of the project
            - args: The parsed arguments, all parsers in the same entry will share the same arguments

        Returns:
            - None, but any return could add when inheriting this class.

            ! Attention: you should add the return type in the subclass. If there is output file or cli
            ! output, you should implement that logic in the subclass parse method.
        """

        if context is None:
            context = GraphManager()

        for p in self.parsers:
            context = p.parse(project_path, context)
