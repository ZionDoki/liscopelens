from typing import Callable

from ..utils.graph import GraphManager
from .parser import BaseParser, BaseScanner


class CParser(BaseParser):

    parser_name = "c_parser"
    file_types = ["c", "h"]


class IncludeParser(CParser):

    parser_name = "include_parser"
    file_types = ["c", "h"]

    def __init__(self, graph: GraphManager):
        super().__init__(graph)

    def parse(self, file_content: str, callback: Callable):
        pass


class CScanner(BaseScanner):

    parser_class = CParser

    def __init__(self):
        super().__init__()

    def walk(self, root_path: str):
        pass