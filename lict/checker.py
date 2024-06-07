import warnings

from lict.infer import generate_knowledge_graph
from lict.constants import Settings, CompatibleType
from lict.utils.structure import LicenseFeat, Scope
from lict.utils import GraphManager, get_resource_path


class Checker:
    """Compatibility checker class"""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):

        if Checker._initialized:
            return

        self.infer = generate_knowledge_graph()
        Checker._initialized = True

    @property
    def properties_graph(self):
        return self.infer.properties_graph

    @property
    def compatible_graph(self):
        return self.infer.compatible_graph

    def is_license_exist(self, license_name: str) -> bool:
        """
        Check if the license exists in the properties graph

        Args:
            - license_name: The name of the license

        Returns:
            - True if the license exists, False otherwise
        """
        # * because the node may return {}, only return is None we can sure the node is not exist

        return self.properties_graph.nodes.get(license_name) is not None

    def check_compatibility(
        self, license_a: str | LicenseFeat, license_b: str | LicenseFeat, scope: Scope = None
    ) -> CompatibleType:
        """
        Check the compatibility between two licenses

        Args:
            - license_a: The name of the first license
            - license_b: The name of the second license
            - scope: (Optional) The scope of the scenes to be used in project

        Returns:
            - The compatibility type of the two licenses
        """

        if scope and not isinstance(scope, Scope):
            raise ValueError("scope should be a Scope object")

        if isinstance(license_a, str):
            license_a_id = license_a
        elif isinstance(license_a, LicenseFeat):
            license_a_id = license_a.spdx_id
        else:
            raise ValueError("license_a should be either a string or a LicenseFeat object")

        if isinstance(license_b, str):
            license_b_id = license_b
        elif isinstance(license_b, LicenseFeat):
            license_b_id = license_b.spdx_id
        else:
            raise ValueError("license_b should be either a string or a LicenseFeat object")

        edge_index = self.compatible_graph.query_edge_by_label(license_a_id, license_b_id)
        if edge_index:
            edge = self.compatible_graph.get_edge_data(edge_index[0])
            if edge["compatibility"] == CompatibleType.CONDITIONAL_COMPATIBLE:

                if not scope:
                    scope = Scope()

                compatible_scope = Scope.from_str(edge["scope"])

                if scope in compatible_scope:
                    return CompatibleType.CONDITIONAL_COMPATIBLE

                return CompatibleType.INCOMPATIBLE

            return CompatibleType(edge["compatibility"])
        else:
            warnings.warn(f"The compatibility of the licenses {license_a_id}->{license_b_id} is unknown")
            return CompatibleType.UNKNOWN
