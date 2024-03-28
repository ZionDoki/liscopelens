import os
from enum import IntEnum
from abc import ABC, abstractmethod

from ..utils.graph import *
from ..utils.scaffold import *
from ..utils.licenses import License, Licenses
from ..constants import Config

"""
Checker and Rules for license itself compatible inference
Inferring compatibility based on structured information
"""


def generate_knowledge_graph(reinfer: bool = False):
    """
    Infer license compatibility and properties based on structured information,
    generate knowledge graph for further usage.

    Args:
        reinfer (bool): whether to re-infer the compatibility and properties
    Returns:
        None, but save the knowledge graph to the data directory.

    ?: whether to return status of generation.
    """

    if (
        reinfer
        or not is_file_in_resources(f"{Config.LICENSE_PROPERTY_GRAPH}")
        or not is_file_in_resources(f"{Config.LICENSE_COMPATIBLE_GRAPH}")
    ):
        
        infer = CompatibleInfer()

        licenses = Licenses()

        for level in CompatibleLevel:
            for license_a, license_b in licenses.get_product():
                infer.check_compatibility(license_a, license_b, level)

        for license in licenses:
            infer.check_license_property(license)
            
        infer.save()


class CompatibleLevel(IntEnum):
    """
    enum type of compatibility level
    
    ! will deprecated in the future
    """
    CONSISTENT = 0
    CONDITION_CONSISTENT = 1
    COMPATIBLE = 2


class CompatibleRule(ABC):
    def __init__(self, level=CompatibleLevel.CONSISTENT, priority=0):
        self.level = level
        self.priority = priority

    @property
    def level_priority(self):
        return f"{CompatibleLevel.CONSISTENT}_{self.priority}"

    @abstractmethod
    def __call__(self, license_a: License, license_b: License, graph: GraphManager):
        pass

    @abstractmethod
    def callback(self, graph: GraphManager, license_a: License, license_b: License):
        pass


class ExemptListRule(CompatibleRule):
    def __init__(self, level=CompatibleLevel.CONSISTENT, priority=0):
        super().__init__(level, priority)

    def __call__(self, license_a: License, license_b: License, graph: GraphManager):
        ret_a, ret_b = False, False
        if license_b.virality:
            ret_a = license_a in license_b.virality["compatible_license"]
        if license_a.virality:
            ret_b = license_b in license_a.virality["compatible_license"]

        return ret_a or ret_b

    def callback(self, graph: GraphManager, license_a: license, license_b: license):
        edge = Edge(license_a, license_b, name=self.level.name)
        graph.add_edge(edge)


class NoViralityRule(CompatibleRule):
    def __init__(self, level=CompatibleLevel.CONSISTENT, priority=1):
        super().__init__(level, priority)

    def __call__(self, license_a: License, license_b: License, graph: GraphManager):
        if not (license_a.virality or license_b.virality):
            return True
        return False

    def callback(self, graph: GraphManager, license_a: license, license_b: license):
        to_edge = Edge(license_a, license_b, name=self.level.name)
        from_edge = Edge(license_b, license_a, name=self.level.name)
        graph.add_edge(to_edge)
        graph.add_edge(from_edge)


class OneViralityConflictRule(CompatibleRule):
    def __init__(self, level=CompatibleLevel.CONSISTENT, priority=2):
        super().__init__(level, priority)

    def __call__(self, license_a: License, license_b: License, graph: GraphManager):
        if bool(license_a.virality) ^ bool(license_b.virality):
            license_a_can = set([can["name"] for can in license_a.can_tags])
            license_b_can = set([can["name"] for can in license_b.can_tags])

            license_a_cannot = set([can["name"] for can in license_a.cannot_tags])
            license_b_cannot = set([can["name"] for can in license_b.cannot_tags])

            return not (license_a_can & license_b_cannot or license_a_cannot & license_b_can)

        return False

    def callback(self, graph: GraphManager, license_a: license, license_b: license):
        edge = Edge(license_a, license_b, name=self.level.name)
        graph.add_edge(edge)


class ConditionConsitentRule(CompatibleRule):
    def __init__(self, level=CompatibleLevel.CONDITION_CONSISTENT, priority=0):
        super().__init__(level, priority)

    def __call__(self, license_a: License, license_b: License, graph: GraphManager):
        if graph.get_edge(Edge(license_a, license_b, name=CompatibleLevel.CONSISTENT.name)):
            return False

        if license_b.virality and license_b.virality["type"] == "condition_virality":
            return True

        return False

    def callback(self, graph: GraphManager, license_a: License, license_b: License):
        edge = Edge(
            license_a,
            license_b,
            name=self.level.name,
            exempt_condition=license_b.virality["exempt_condition"],
        )
        graph.add_edge(edge)


class CompatibleInfer:
    def __init__(self):
        self.properties_graph = GraphManager()
        self.compatible_graph = GraphManager()
        self.rules = {}
        self.register_default_rules()

    def level_priorities(self):
        return [rule.level_priority for rule in self.rules.values()]

    def register_rule(self, rule: CompatibleRule):
        if not self.rules.get(rule.level):
            self.rules[rule.level] = []
        if rule.priority in [rule.priority for rule in self.rules[rule.level]]:
            raise ValueError(f"{rule.level.name} {rule.priority} rule already exists.")
        self.rules[rule.level].append(rule)

    def register_default_rules(self):
        for rule in CompatibleRule.__subclasses__():
            self.register_rule(rule())

        for key in self.rules.keys():
            self.rules[key] = list(sorted(self.rules[key], key=lambda rule: rule.priority))

    def check_license_property(self, license_a: License):
        license_vertex = Vertex(label=str(license_a))
        for can_tag in license_a.can_tags:
            edge = Triple(license_vertex, Vertex(can_tag["name"]), name="CAN")
            self.properties_graph.add_triplet(edge)

        for cannot_tag in license_a.cannot_tags:
            edge = Triple(license_vertex, Vertex(cannot_tag["name"]), name="CANNOT")
            self.properties_graph.add_triplet(edge)

        for must_tag in license_a.must_tags:
            if not must_tag["name"].lower().startswith("same license"):
                edge = Triple(license_vertex, Vertex(must_tag["name"]), name="CANNOT")
                self.properties_graph.add_triplet(edge)
                continue

            if not license_a.virality:
                raise ValueError("Virality not found.")

            name = "condition virality" if license_a.virality["type"] == "condition_virality" else "full virality"
            edge = Triple(
                license_vertex, Vertex(name), name="MUST", exempt_condition=license_a.virality["exempt_condition"]
            )
            self.properties_graph.add_triplet(edge)

    def check_compatibility(
        self,
        license_a: License,
        license_b: License,
        level: CompatibleLevel = CompatibleLevel.CONSISTENT,
    ):
        if not self.rules.get(level):
            return
        for rule in self.rules[level]:
            if rule(license_a, license_b, self.compatible_graph):
                rule.callback(self.compatible_graph, license_a, license_b)
                return

    def save(self, dir_path: str = None):
        if dir_path:
            self.properties_graph.save(f"{dir_path}/{Config.LICENSE_PROPERTY_GRAPH}")
            self.compatible_graph.save(f"{dir_path}/{Config.LICENSE_COMPATIBLE_GRAPH}")
        else:
            destination = get_resource_path()
            self.properties_graph.save(destination.joinpath(Config.LICENSE_PROPERTY_GRAPH))
            self.compatible_graph.save(destination.joinpath(Config.LICENSE_COMPATIBLE_GRAPH))
