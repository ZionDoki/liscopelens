import os
from tkinter import NO
import unittest
import argparse
from lict.infer import *
from lict.checker import *
from lict.utils.graph import *
from lict.utils.structure import *
from lict.parser import *


class TestLicense(unittest.TestCase):
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
            set(["conflicts", "immutability", "compliance"]),
            f"schemas properties need equal to ['immutability', 'compliance'] but {set(schemas.properties)}",
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

        self.assertFalse(
            None in Scope.universe(),
            "None should not in universe",
        )

        self.assertFalse(
            None in Scope({ScopeToken.UNIVERSE: set("test")}),
            "None should not in non-strict universe",
        )

        self.assertTrue(
            None in Scope(),
            "None should in empty scope",
        )

        self.assertTrue(
            Scope() in Scope.universe(),
            "Empty set should in universe",
        )

        self.assertFalse(
            Scope({}) in Scope({"test": set()}),
            "Empty set should not in scope that has not Universal protect scope",
        )

        self.assertTrue(
            Scope({"test": {"a"}}) in Scope({"test": set()}),
            "Empty set should in scope that has Universal protect scope",
        )

        self.assertFalse(
            Scope({"test": set()}) in Scope({"test": {"b"}}),
            "Scope should not in different scope",
        )

        result = ActionFeatOperator.intersect(ActionFeat("a", "b", [], ["b"]), ActionFeat("a", "b", [], ["b"]))
        self.assertEqual(
            result,
            ActionFeat("a", "b", [], ["b"]).scope,
            "Check Universal intersect failed",
        )

    def test_checker(self):
        checker = Checker()

        generate_knowledge_graph(reinfer=True)

        self.assertFalse(checker.is_license_exist("MITR"), "MITR should not exist in the license graph")

        self.assertTrue(checker.is_license_exist("MIT"), "MIT should exist in the license graph")

        self.assertEqual(
            checker.check_compatibility("LGPL-2.1-only", "Apache-2.0", scope=Scope({"dynamic_linking": set()})),
            CompatibleType.CONDITIONAL_COMPATIBLE,
            "LGPL-2.1-only and Apache-2.0 should be CONDITIONAL_COMPATIBLE",
        )

    def test_structure(self):
        # load licenses

        checker = Checker()

        licenses = load_licenses()

        self.assertTrue(
            licenses,
            "Load licenses failed",
        )

        feat_a = DualUnit("MIT")
        feat_b = DualUnit("GPL-2.0-only")

        feat_c = DualUnit("Apache-2.0")

    def test_graph(self):
        checker = Checker()

        print(checker.get_modal_features("MIT", "can"))

        self.assertFalse(
            checker.is_copyleft("MIT"),
            "MIT should not be copyleft",
        )

        self.assertFalse(
            checker.is_copyleft("Apache-2.0"),
            "Apache-2.0 should not be copyleft",
        )

        self.assertTrue(
            checker.is_copyleft("GPL-2.0-only"),
            "GPL-2.0-only should be copyleft",
        )


class TestInfer(unittest.TestCase):

    def test_infer(self):
        generate_knowledge_graph(reinfer=True)
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


class TestParser(unittest.TestCase):

    def test_compatible_parser(self):
        import json
        from lict.parser.compatible import BaseCompatiblityParser
        from lict.parser.scancode import ScancodeParser

        ScancodeParser(argparse.Namespace(scancode_file="../lict_exp/test.json"), config=load_config()).parse(
            "test", GraphManager()
        )


class TestTest(unittest.TestCase):
    import warnings
    warnings.filterwarnings("ignore")

    def test_Test_parser(self):
        from lict.parser.Test_parser.Test_parser import TestParser

        # TestParser(argparse.Namespace(scancode_file="../lict_exp/test.json")).parse("test", GraphManager())
        config = Config.from_toml(path="lict/config/default.toml")
        context = TestParser(
            argparse.Namespace(user_config_file="lict/config/user_config.toml", init_file="lict/resources/test_template.gml", results="results"),
            config=config).parse("test", GraphManager())

        # from lict.parser.compatible import BaseCompatiblityParser
        # context = BaseCompatiblityParser(argparse.Namespace(),config=config).parse("test",context)
        # context.save("answer.gml")


class TempTest(unittest.TestCase):

    def test(self):
        exceptions = load_exceptions()
        licenses = load_licenses()

        graph = GraphManager("lict/resources/compatible_graph.gml")
        edge = graph.query_edge_by_label("GPL-2.0-only", "GPL-3.0-or-later-with-Bison-exception-2.2")
        print(edge)
        print(graph.get_edge_data(edge[0]))
        edge = graph.query_edge_by_label("GPL-3.0-or-later-with-Bison-exception-2.2", "GPL-2.0-only")
        print(edge)
        edge = graph.get_edge_data(edge[0])
        scope = Scope.from_str(edge["scope"])
        scope["UNIVERSAL"] = set(["a", "b"])
        print(scope)
        print(Scope({"a": set()}))
        print(Scope({"COMPILE": set()}) in scope)


if __name__ == "__main__":
    unittest.main()
