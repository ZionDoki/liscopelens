from enum import StrEnum, IntEnum


class Config(StrEnum):
    """configurations of the project"""

    PACAKAGE_NAME = "lic_compatible_tool"
    RESOURCE_NAME = "resources"
    LICENSE_PROPERTY_GRAPH = "properties_graph.gml"
    LICENSE_COMPATIBLE_GRAPH = "compatible_graph.gml"
    LICENSE_FEATURE = "licenses_feature.json"

class CompatibleResult(IntEnum):
    """enum type of detection results"""

    UNKNOWN = -1
    NONEXIST = 0
    INCONSISTENT = 1
    CONSISTENT = 2
    CONDITION_CONSISTENT = 3
    COMPATIBLE = 4


class CompatibleLevel(IntEnum):
    """
    Enum type of compatibility rules level.

    - UNCONDITIONAL_COMPATIBLE: The licenses are compatible unconditionally.
    - CONDITIONAL_COMPATIBLE: The licenses are compatible conditionally.

    UNCONDITIONAL_COMPATIBLE and CONTIONAL_COMPATIBLE construct a compatibility
    graph with two layers. The first layer is UNCONDITIONAL_COMPATIBLE, and the
    second layer is CONDITIONAL_COMPATIBLE.

    The infer module will check the compatibility of licenses in the first layer
    first. If the licenses are conflict, the infer module will check the compatibility
    of licenses in the second layer. Otherwise, the infer module will return the
    compatibility result of the first layer.
    """

    UNCONDITIONAL_COMPATIBLE = 0
    CONDITIONAL_COMPATIBLE = 1
