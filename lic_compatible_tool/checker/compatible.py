# coding=utf-8
# Author: Zion, Zihao Zhang
# Date: 2023/12/18
# Contact: liuza20@lzu.edu.cn, zhzihao2023@lzu.edu.cn

import copy
from typing import Any

from enum import IntEnum
from loguru import logger
from abc import ABC, abstractmethod

from ..utils.scaffold import *
from ..utils.graph import GraphManager
from ..constants import Config, CompatibleResult


class CompatibleRule(ABC):
    """Compatibility check rule abstract class.
    Methods:
        __init__: initialize the priority  of the rule.
        __call__: the logic of compatibility check."""

    def __init__(self, priority=0):
        self.priority = priority

    @abstractmethod
    def __call__(self, graph: GraphManager, license_a: str, license_b: str, trigger: str = None) -> bool:
        pass


class ExsistRule(CompatibleRule):
    """Check if the license exists in the database"""

    def __init__(self, priority=0):
        self.priority = priority

    def __call__(self, graph: GraphManager, license_a: str, license_b: str, trigger: str = None) -> Any:
        if license_a == license_b:
            return CompatibleResult.CONSISTENT

        result = graph.query_node_by_label(license_a) != None and graph.query_node_by_label(license_b) != None

        if not result:
            return CompatibleResult.NONEXIST
        return CompatibleResult.UNKNOWN


class ConsistentRule(CompatibleRule):
    """Check if the license is consistent with each other"""

    def __init__(self, priority=1):
        super().__init__(priority)

    def __call__(self, graph: GraphManager, license_a: str, license_b: str, trigger: str = None) -> bool:
        result = graph.query_edge_by_label(license_a, license_b, name="CONSISTENT")

        if len(result) != 0:
            return CompatibleResult.CONSISTENT
        return CompatibleResult.UNKNOWN


class ConditionRule(CompatibleRule):
    """Check if the license is consistent with each other under the trigger condition"""

    def __init__(self, priority=2):
        super().__init__(priority)

    def __call__(self, graph: GraphManager, license_a: str, license_b: str, trigger: str = None) -> bool:
        if trigger == None:
            return CompatibleResult.UNKNOWN

        result = graph.query_edge_by_label(license_a, license_b, name="CONDITION_CONSISTENT")
        if len(result) == 0:
            return CompatibleResult.UNKNOWN
        
        compatible_property = graph.get_edge_data(result[0])

        if trigger in compatible_property["exempt_condition"]:
            return CompatibleResult.CONSISTENT
        return CompatibleResult.UNKNOWN


class CompatibleChecker:
    """Compatibility checker class"""

    def __init__(self):

        destination = get_resource_path()
        self.properties_graph = GraphManager(destination.joinpath(Config.LICENSE_PROPERTY_GRAPH))
        self.compatible_graph = GraphManager(destination.joinpath(Config.LICENSE_COMPATIBLE_GRAPH))

        self.rules = []
        self.register_default_rules()

    @property
    def priorities(self) -> list[int]:
        return [rule.priority for rule in self.rules]

    def register_rule(self, rule: CompatibleRule) -> None:
        if rule.priority in self.priorities:
            raise ValueError(f"{rule.priority} rule already exists.")
        self.rules.append(rule)

    def register_default_rules(self) -> None:
        for rule in CompatibleRule.__subclasses__():
            self.register_rule(rule())

        self.rules: list[CompatibleRule] = list(sorted(self.rules, key=lambda rule: rule.priority))

    @property
    def polluters(self) -> set:
        full_viralities = set(map(lambda x: x[0], self.properties_graph.graph.in_edges("full virality")))
        condition_viralities = set(map(lambda x: x[0], self.properties_graph.graph.in_edges("condition virality")))
        return list(full_viralities | condition_viralities)

    def check_polluter(self, license_id: str):
        return license_id in self.polluters

    def check_compatibility(
        self,
        license_a: str,
        license_b: str,
        trigger: str = None,
    ) -> CompatibleResult:
        for rule in self.rules:
            result = rule(self.compatible_graph, license_a, license_b, trigger)
            if result != CompatibleResult.UNKNOWN:
                return result

        # * return inconsistent when check all rule still unkonwn
        return CompatibleResult.INCONSISTENT


class Get:
    """
    Class for retrieving license information, dependencies, and reliance.

    Args:
        data (dict): The input data containing package and relationship information.
    """

    def __init__(self, data):
        self.data = copy.deepcopy(data)
        self.relationships = []
        self.dependencies = {}
        self.visited = set()

    def get_license(self):
        my_dict = {}
        for my_package in self.data["packages"]:
            my_dict[my_package["spdxId"]] = my_package["licenses"]
        return my_dict

    def get_dependencies(self, my_package):
        if my_package in self.dependencies or my_package in self.visited:
            return
        else:
            self.visited.add(my_package)
        self.dependencies[my_package] = []
        for relation in self.data["relationships"]:
            if relation["spdxElementId"] == my_package:
                depends_on = relation["relatedSpdxElement"]
                self.dependencies[my_package].append(depends_on)
                self.get_dependencies(depends_on)

    def get_reliance(self):
        for package in self.data["packages"]:
            spdxId = package["spdxId"]
            self.dependencies = {}
            self.visited = set()
            self.get_dependencies(spdxId)
            self.relationships.append(self.dependencies)
        return self.relationships


class Process:
    """
    Class for processing license compatibility checks and generating conflicts.

    Args:
        license_dict (dict): Dictionary mapping packages to their licenses.
    """

    def __init__(self, license_dict):
        self.conflicts = []
        self.license_dict = license_dict

    def check_one(self, package_a, package_b, checker: CompatibleChecker):
        """
        Performs a compatibility check between two packages.

        Args:
            package_a (str): SPDX ID of the first package.
            package_b (str): SPDX ID of the second package.
            checker (CompatibleChecker): Checker object for compatibility checks.

        """
        package_a_license = self.license_dict[package_a]
        package_b_license = self.license_dict[package_b]
        if len(package_a_license) == 0 or len(package_b_license) == 0:
            return

        for x in package_a_license:
            for y in package_b_license:
                if x["spdxId"] == y["spdxId"]:
                    continue

                logger.debug(f"{'|':>9} {x['spdxId']} 和 {y['spdxId']}")
                re = checker.check_compatibility(x["spdxId"], y["spdxId"], trigger="").name
                if (re == "INCONSISTENT") and ("polluter" in y):
                    an = {
                        "licenseA": {
                            "name": x["spdxId"],
                            "spdxId": x["spdxId"],
                            "from": package_a,
                            "polluter": None,
                        },
                        "licenseB": {
                            "name": y["spdxId"],
                            "spdxId": y["spdxId"],
                            "from": package_b,
                            "polluter": y["polluter"],
                        },
                    }
                    self.conflicts.append(an)
                elif (re == "INCONSISTENT") and ("polluter" not in y):
                    if checker.check_polluter(y["spdxId"]):
                        an = {
                            "licenseA": {
                                "name": x["spdxId"],
                                "spdxId": x["spdxId"],
                                "from": package_a,
                                "polluter": None,
                            },
                            "licenseB": {
                                "name": y["spdxId"],
                                "spdxId": y["spdxId"],
                                "from": package_b,
                                "polluter": package_b,
                            },
                        }
                        self.conflicts.append(an)
                else:
                    continue

    def check(self, my_data: dict, checker: CompatibleChecker):
        """
        Performs license compatibility checks for the given data.

        Args:
            my_data (dict): Dictionary containing package reliance information.
            checker (CompatibleChecker): Checker object for compatibility checks.

        Returns:
            list: List of conflicts found during the checks.
        """
        for key in reversed(my_data):
            if len(my_data[key]) != 0:
                for reliance in my_data[key]:
                    logger.debug(f"检查依赖路径：{key} -> {reliance}")
                    self.check_one(key, reliance, checker)

                for reliance in my_data[key]:
                    package_reliance_license = self.license_dict[reliance]
                    for i in package_reliance_license:
                        if checker.check_polluter(i["spdxId"]):
                            if "polluter" not in i:
                                li = {"spdxId": i["spdxId"], "polluter": reliance}
                            else:
                                li = {"spdxId": i["spdxId"], "polluter": i["polluter"]}
                            self.license_dict[key].append(li)

            ready = key
            ready_license = self.license_dict[ready]

            if len(ready_license) <= 1:
                continue

            for i in range(len(ready_license)):
                for j in range(i + 1, len(ready_license)):
                    check_flag = (
                        ("polluter" in ready_license[i])
                        and ("polluter" in ready_license[j])
                        or (("polluter" not in ready_license[i]) and ("polluter" not in ready_license[j]))
                    )

                    if not check_flag:
                        continue

                    if ready_license[i]["spdxId"] == ready_license[j]["spdxId"]:
                        continue

                    res = checker.check_compatibility(
                        ready_license[i]["spdxId"],
                        ready_license[j]["spdxId"],
                        trigger="",
                    ).name

                    if (
                        (res == "INCONSISTENT")
                        and ("polluter" not in ready_license[i])
                        and ("polluter" not in ready_license[j])
                    ):
                        an = {
                            "licenseA": {
                                "name": ready_license[i]["spdxId"],
                                "spdxId": ready_license[i]["spdxId"],
                                "from": ready,
                                "polluter": None,
                            },
                            "licenseB": {
                                "name": ready_license[j]["spdxId"],
                                "spdxId": ready_license[j]["spdxId"],
                                "from": ready,
                                "polluter": None,
                            },
                        }
                        self.conflicts.append(an)
                    elif (
                        (res == "INCONSISTENT")
                        and ("polluter" in ready_license[i])
                        and ("polluter" in ready_license[j])
                    ):
                        an = {
                            "licenseA": {
                                "name": ready_license[i]["spdxId"],
                                "spdxId": ready_license[i]["spdxId"],
                                "from": ready,
                                "polluter": ready_license[i]["polluter"],
                            },
                            "licenseB": {
                                "name": ready_license[j]["spdxId"],
                                "spdxId": ready_license[j]["spdxId"],
                                "from": ready,
                                "polluter": ready_license[j]["polluter"],
                            },
                        }
                        self.conflicts.append(an)
        return self.conflicts
