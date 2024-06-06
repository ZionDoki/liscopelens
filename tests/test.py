import os
import unittest
import argparse
from lict.infer import *
from lict.checker import *
from lict.utils.graph import *
from lict.utils.structure import *
from lict.parser import *


class TestLicenseTools(unittest.TestCase):
    """unit test for every model in license-tool"""

    def test_utils_licenses(self):

        schemas = load_schemas()

        # ! check emptyset negate in scope
        self.assertTrue(Scope().negate().is_universal, "Negate empty set should be universal")
        self.assertTrue(not Scope.universe().negate(), "Negate universe set should be empty")

        self.assertTrue(
            schemas,
            "Load schemas failed",
        )

        self.assertEqual(
            set(schemas.properties),
            set(["immutability", "compliance"]),
            "schemas properties need equal to ['immutability', 'compliance']",
        )

        test = ActionFeat("modify", "cannot", ["a"], ["b"])
        self.assertTrue(
            schemas.has_property(test, "immutability"),
            "Load schemas failed",
        )

        feat_a = ActionFeat("modify", "cannot", ["a"], ["b"])
        feat_b = ActionFeat("modify", "cannot", ["a"], ["b"])
        self.assertTrue(
            ActionFeatOperator.contains(feat_a, feat_b),
            "feat_a should contains feat_b",
        )

        self.assertTrue(
            ActionFeatOperator.contains(feat_a, feat_b),
            "feat_b should contains feat_a",
        )

        feat_a = ActionFeat("modify", "cannot", [], ["b"])
        feat_b = ActionFeat("modify", "cannot", ["a"], ["c"])

        self.assertTrue(
            ActionFeatOperator.contains(feat_a, feat_b),
            "feat_a should contains feat_b",
        )

        self.assertTrue(
            not ActionFeatOperator.contains(feat_b, feat_a),
            "feat_b should not contains feat_a",
        )

        feat_a = ActionFeat("modify", "cannot", [], ["b", "a"])
        feat_b = ActionFeat("modify", "cannot", ["a"], [])

        self.assertTrue(
            not ActionFeatOperator.contains(feat_a, feat_b),
            "feat_a should not contains feat_b",
        )

        self.assertTrue(
            not ActionFeatOperator.contains(feat_b, feat_a),
            "feat_b should not contains feat_a",
        )

        self.assertEqual(
            ActionFeatOperator.intersect(ActionFeat("a", "b", ["a"], ["b"]), ActionFeat("a", "b", ["a"], ["b"])),
            ActionFeat("a", "b", ["a"], ["b"]).scope,
            "ActionFeat intersect failed",
        )

        self.assertNotEqual(
            ActionFeatOperator.intersect(ActionFeat("a", "b", ["c"], ["d"]), ActionFeat("a", "b", ["a"], ["b"])),
            ActionFeat("a", "b", [], ["b", "d"]).scope,
            "Check pass empty list will make ActionFeat protect scope become Universal",
        )

        self.assertEqual(
            ActionFeatOperator.intersect(ActionFeat("a", "b", ["c"], ["d"]), ActionFeat("a", "b", ["a"], ["b"])),
            ActionFeat("a", "b", None, ["b", "d"]).scope,
            "ActionFeat intersect failed",
        )

        result = ActionFeatOperator.intersect(ActionFeat("a", "b", [], ["b"]), ActionFeat("a", "b", [], ["b"]))
        self.assertEqual(
            result,
            ActionFeat("a", "b", [], ["b"]).scope,
            "Check Universal intersect failed",
        )

    def test_infer(self):

        schemas = load_schemas()
        licenses = load_licenses()
        infer = CompatibleInfer(schemas=schemas)
        infer.check_compatibility(licenses)
        infer.save("./")

        result = toml.load("./tests/result.toml")
        for lic in result:
            for lic2 in result[lic]:
                edge_index = infer.compatible_graph.query_edge_by_label(lic, lic2)

                edge = infer.compatible_graph.get_edge_data(edge_index[0])
                self.assertEqual(
                    result[lic][lic2],
                    edge["compatibility"],
                    f"{lic} and {lic2} should be {CompatibleType(result[lic][lic2]).name}, but {CompatibleType(edge['compatibility']).name}",
                )

        generate_knowledge_graph(reinfer=True)

    def test_checker(self):
        checker = Checker()

        generate_knowledge_graph(reinfer=True)

        self.assertFalse(checker.check_license_exist("MITR"), "MITR should not exist in the license graph")

        self.assertTrue(checker.check_license_exist("MIT"), "MIT should exist in the license graph")

        self.assertAlmostEqual(
            checker.check_compatibility("LGPL-2.1-only", "Apache-2.0", scope=Scope({"dynamic_linking": set()})),
            CompatibleType.CONDITIONAL_COMPATIBLE,
            "LGPL-2.1-only and Apache-2.0 should be CONDITIONAL_COMPATIBLE",
        )


class TestParser(unittest.TestCase):

    def test_compatible_parser(self):

        import json
        from lict.parser.compatible import BaseCompatiblityParser
        from lict.parser.scancode import ScancodeParser

        ScancodeParser(argparse.Namespace(scancode_file="../lict_exp/test.json")).parse("test", GraphManager())


class TempTest(unittest.TestCase):

    def test(self):
        result = get_resource_path("test", resource_name="resources.exceptions")
        print(result.exists())

if __name__ == "__main__":
    unittest.main()
