import sys
import unittest

from lic_compatible_tool.utils.graph import *
from lic_compatible_tool.checker.infer import *
from lic_compatible_tool.checker.compatible import *
from lic_compatible_tool.utils.licenses import *


class TestLicenseTools(unittest.TestCase):
    """unit test for every model in license-tool"""

    def test_graph(self):
        """test utils/graph.py"""

        gm = GraphManager()
        v1 = Vertex("a", a=1, b=2)
        v2 = Vertex("b", a=1, b=2)
        gm.add_node(v1)
        gm.add_node(v2)

        e = Edge("a", "b", c=3)
        gm.add_edge(e)

        triple = Triple(v1, v2, test=3)
        gm.add_triplet(triple)

        triple = Triple(v1, v2)
        gm.add_triplet(triple)

        e = Edge("a", "b", d=1)
        triple = Triple(v1, v2, e)
        gm.add_triplet(triple)

        v3 = Vertex("test")

    def test_licenses(self):
        generate_knowledge_graph(reinfer=True)

    def test_checker(self):
        pass


if __name__ == "__main__":
    unittest.main()
