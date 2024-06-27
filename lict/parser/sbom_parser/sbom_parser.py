#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# Copyright (c) 2024 Lanzhou University
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import argparse
import copy
import json

from lict.checker import Checker
from lict.utils.structure import Scope
from lict.utils.graph import GraphManager

from lict.parser.base import BaseParser


class GetPackage(object):
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


class ProcessSbom(object):
    """
    Class for processing license compatibility checks and generating conflicts.

    Args:
        license_dict (dict): Dictionary mapping packages to their licenses.
    """

    def __init__(self, license_dict, pollute_switch=True):
        self.conflicts = []
        self.license_dict = license_dict
        self.pollute_switch = pollute_switch

    def check_one(self, package_a, package_b, checker: Checker):
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

                re = checker.check_compatibility(
                    license_a=x["spdxId"], license_b=y["spdxId"], scope=Scope({"dynamic_linking": set()})
                ).name
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

    def check(self, my_data: dict, checker: Checker):
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
                    self.check_one(key, reliance, checker)

                for reliance in my_data[key]:
                    package_reliance_license = self.license_dict[reliance]
                    for i in package_reliance_license:
                        # 传染器开关
                        if checker.check_polluter(i["spdxId"]) and self.pollute_switch:
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


class SBOMParser(BaseParser):
    conflicts = []
    arg_table = {
        "--sbom_file": {"type": str, "help": "sbom_file_path", "group": "a"},
    }

    def parse(self, project_path: str, context: GraphManager):
        print(self.args.sbom_file)
        if self.args.sbom_file is not None:
            with open(file=self.args.sbom_file, mode="r", encoding="UTF-8") as file:
                sbom_data = json.load(file)
                file.close()
                get_package_one = GetPackage(sbom_data)
                license_dict = get_package_one.get_license()
                relationships = get_package_one.get_reliance()
                checker = Checker()
                for x in relationships:
                    get = GetPackage(sbom_data)
                    process = ProcessSbom(license_dict)
                    con = process.check(x, checker)
                    license_dict = get.get_license()
                    self.conflicts.extend(con)
                    unique_conflicts = [dict(s) for s in set(frozenset(d.items()) for d in self.conflicts)]
