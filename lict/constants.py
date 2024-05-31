from enum import StrEnum, IntEnum


class Settings(StrEnum):
    """configurations of the project."""

    PACAKAGE_NAME = "lict"
    RESOURCE_NAME = "resources"
    LICENSE_PROPERTY_GRAPH = "properties_graph.gml"
    LICENSE_COMPATIBLE_GRAPH = "compatible_graph.gml"
    LICENSE_FEATURE = "licenses_feature.json"


class CompatibleType(IntEnum):
    """
    Enum type of compatibility graph edges.

    - UNCONDITIONAL_COMPATIBLE: The licenses are compatible unconditionally.
    - CONDITIONAL_COMPATIBLE: The licenses are compatible conditionally.
    - INCOMPATIBLE: The licenses are incompatible.
    - UNKNOWN: The compatibility of the licenses is unknown, this will cause the warning.

    The compatibility graph is a directed graph, and the edge from license A to license B
    means the compatibility of license A to license B.

    Direction in CONDITIONAL_COMPATIBLE edge means from License A could find a way that
    TODO: ...
    """

    UNCONDITIONAL_COMPATIBLE = 0
    CONDITIONAL_COMPATIBLE = 1
    PARTIAL_INCOMPATIBLE = 2
    INCOMPATIBLE = 3
    UNKNOWN = 4


class FeatureType(StrEnum):
    """enum type of feature type."""

    CAN = "can"
    CANNOT = "cannot"
    MUST = "must"
    SPECIAL = "special"


class FeatureProperty(StrEnum):
    """enum type of feature property."""

    COMPLIANCE = "compliance"


class ScopeToken(StrEnum):
    """enum type of scope token."""

    UNIVERSE = "UNIVERSAL"


class ScopeElement(StrEnum):
    """
    enum type of scope element.

    ! The value must be consistent with the member variable.
    """

    COMPILE = "COMPILE"
    DYNAMIC_LINKING = "DYNAMIC_LINKING"
    STATIC_LINKING = "STATIC_LINKING"
    EXECUTABLE = "EXECUTABLE"
