from .sbom_parser.entry import SBOMParserEntry
from .c_parser.entry import CParserEntry

PARSER_ENTRIES = {"sbom": SBOMParserEntry, "cpp": CParserEntry}
