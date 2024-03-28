from ..utils.graph import *

from typing import List, Callable
from abc import ABC, abstractmethod
from dataclasses import dataclass


class BaseParser(ABC):

    parser_name: str

    def __init__(self, graph: GraphManager):
        self.graph = graph

    @abstractmethod
    def parse(self, file_content: str):
        """
        parse the file content and save the file content to the graph.
        """
        raise NotImplementedError


class BaseScanner(ABC):

    parser_class = BaseParser
    parsers: list[BaseParser] = []

    def __init__(self):
        self.graph = GraphManager()
        self.register_default_parsers()

    def register_default_parsers(self) -> None:
        self.parsers = []
        for parser in self.parser_class.__subclasses__():
            self.register_parser(parser(self.graph))

    def register_parser(self, parser: BaseParser):
        self.parsers.append(parser)

    def parse(self, file_path: str):
        file_type = file_path.split(".")[-1]
        for parser in self.parsers:
            if file_type in parser.file_types:
                parser.parse(file_path, self.handle_parse_result)
                break

    @abstractmethod
    def walk(self, root_path: str):
        """
        walk through the root path and parse all files. when walking through the root path,
        it should save the file node and file structure to the graph. Also, it should call
        parse method to parse the file content and save the file content to the graph.

        Args:
            root_path: (str) project root path
        """
        raise NotImplementedError
