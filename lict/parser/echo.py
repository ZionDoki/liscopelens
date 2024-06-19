# coding=utf-8
# Author: Zion
# Date: 2024/06/06
# Contact: liuza20@lzu.edu.cn
import json
from pprint import pformat

from .base import BaseParser
from argparse import Namespace
from lict.utils.structure import Config
from lict.utils.graph import GraphManager


class EchoPaser(BaseParser):

    arg_table = {
        "--echo": {
            "action": "store_true",
            "help": "Echo the final result of compatibility checking",
            "default": False,
        },
        "--out-echo": {
            "type": str,
            "help": "The output path of the echo result",
            "default": "",
        },
    }

    def __init__(self, args: Namespace, config: Config):
        super().__init__(args, config)

    def parse(self, project_path: str, context: GraphManager = None) -> GraphManager:

        need_echo = getattr(self.args, "echo", False)
        out_echo = getattr(self.args, "out_echo", "")
        if not need_echo:
            return context

        results = []
        for edge_index, edge_data in context.filter_edges(type="compatible_result"):
            source, target, _ = edge_index

            results.append(
                {
                    "parents": set(context.predecessors(source)) & set(context.predecessors(target)),
                    "conflicts": edge_data["conflict"],
                    source: context.nodes[source],
                    target: context.nodes[target],
                    "results": "INCOMPATIBLE",
                }
            )

        if out_echo:
            with open(out_echo, "w") as f:
                f.write(json.dumps(results, default=str))
        else:
            print(pformat(results))

