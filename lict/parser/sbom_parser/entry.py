from .sbom_parser import SBOMParser
from lict.parser.base import BaseParser, BaseParserEntry


class SBOMParserEntry(BaseParserEntry):
    parsers: tuple[BaseParser] = (SBOMParser,)

    entry_help: str = "Software Bill of Materials (SBOM) parser, this parser only support for OH sbom format."
