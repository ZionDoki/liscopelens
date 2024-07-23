from .sbom_parser.entry import SBOMParserEntry
from .c_parser.entry import CParserEntry
from .Test_parser.entry import TestParserEntry
from .user_parser.entry import QueryEntry

PARSER_ENTRIES = {"sbom": SBOMParserEntry, "cpp": CParserEntry, "test": TestParserEntry, "query": QueryEntry}
