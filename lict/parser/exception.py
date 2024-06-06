# coding=utf-8
# Author: Zion
# Date: 2024/06/06
# Contact: liuza20@lzu.edu.cn

from .base import BaseParser
from argparse import Namespace
from lict.checker import Checker
from lict.utils.graph import GraphManager
from lict.utils.structure import Config, load_licenses, load_exceptions


class BaseExceptionParser(BaseParser):

    arg_table = {
        "--save-kg": {"action": "store_true", "help": "Save new knowledge graph after infer parse", "default": False}
    }

    def __init__(self, args: Namespace, config: Config):
        super().__init__(args, config)
        self.checker = Checker()

        self.all_licenes = load_licenses()
        self.all_exceptions = load_exceptions()

    def parse(self, project_path: str, context: GraphManager = None) -> GraphManager:
        save_kg = getattr(self.args, "save_kg", False)

        visited_licenses, new_for_infer = set(), {}

        for node_label, node_data in context.nodes(data=True):
            dual_license = node_data.get("licenses")
            if not dual_license:
                continue

            for group in dual_license:
                for unit in group:
                    for exception in unit["exceptions"]:
                        spdx_id = unit["spdx_id"] + "-with-" + exception

                        if spdx_id in visited_licenses:
                            continue

                        visited_licenses.add(spdx_id)

                        if self.checker.is_license_exist(spdx_id):
                            continue

                        if exception not in self.all_exceptions:
                            continue

                        if unit["spdx_id"] not in self.all_licenes:
                            continue

                        new_feat = self.all_licenes[unit["spdx_id"]].cover_from(self.all_exceptions[exception])
                        new_for_infer[new_feat.spdx_id] = new_feat

        self.checker.infer.check_compatibility({**self.all_licenes, **new_for_infer})
        if save_kg:
            self.checker.infer.save()

        return context
