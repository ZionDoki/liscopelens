from .build_gn_parser_wasted import GnParser

from lict.parser.scancode import ScancodeParser
from lict.parser.base import BaseParser, BaseParserEntry
from lict.parser.compatible import BaseCompatiblityParser


class CParserEntry(BaseParserEntry):
    parsers: tuple[BaseParser] = (
        GnParser,
        ScancodeParser,
        BaseCompatiblityParser,
    )

    entry_name: str = "cParser"
    entry_help: str = (
        "This parser is used to parse the C/C++ repository and provide an include dependency graph for "
        "subsequent operations"
    )
