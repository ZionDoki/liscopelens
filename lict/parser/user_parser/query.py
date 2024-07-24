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


import os
import json

import networkx as nx
from textual.app import App, ComposeResult
from textual.widgets import Input, ListView, ListItem, Label

from argparse import Namespace
from typing import Optional
from lict.utils.structure import Config
from lict.utils.graph import GraphManager

from ..base import BaseParser


class GraphVisualizer(App):
    CSS_PATH = "styles/graph_visualizer.css"

    def __init__(self, graph):
        super().__init__()
        self.graph = graph
        self.current_node = ""
        self.predecessors = []
        self.successors = []
        self.conflict_uuid = ""

    def compose(self) -> ComposeResult:
        yield Label("Search for node: ")
        yield Input(placeholder="Enter node label to search...", id="search_input")
        yield Label("add conflict uuid: ")
        yield Input(placeholder="Enter conlict uuid to filter search...", id="filter_input")
        yield Label("Predecessors")
        yield ListView(id="predecessors")
        yield Label("Current Node: ", id="node_label")
        yield Label(id="node_data")  # 替换 Label 为 TextArea
        yield Label("Successors")
        yield ListView(id="successors")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        query = event.value

        if event.control.id == "search_input" and query:
            self.search_node(query)

        if event.control.id == "filter_input" and query:
            self.conflict_uuid = event.value

    def search_node(self, label):
        for node, data in self.graph.nodes(data=True):
            if node.lower() == label.lower():
                self.current_node: str = node
                self.update_ui()
                return

        current_node_widget = self.query_one("#node_data")
        if isinstance(current_node_widget, Label):
            current_node_widget.update("Node not found")

    def update_ui(self):
        current_node_data = self.graph.nodes(data=True)[self.current_node]
        current_node_json = json.dumps(current_node_data, indent=4)

        data_widget = self.query_one("#node_data")
        label_widget = self.query_one("#node_label")
        if isinstance(data_widget, Label):
            data_widget.update(current_node_json)
        if isinstance(label_widget, Label):
            label_widget.update("Current Node: " + self.current_node)

        if self.conflict_uuid == "":
            self.successors = list(self.graph.successors(self.current_node))
            self.predecessors = list(self.graph.predecessors(self.current_node))
        else:
            self.predecessors = list(
                item
                for item in self.graph.predecessors(self.current_node)
                if (cg := self.graph.nodes[item].get("conflict_group")) and self.conflict_uuid in cg
            )

            self.successors = list(
                item
                for item in self.graph.successors(self.current_node)
                if (cg := self.graph.nodes[item].get("conflict_group")) and self.conflict_uuid in cg
            )

        pred_list = self.query_one("#predecessors", ListView)
        pred_list.clear()
        for pred in self.predecessors:
            pred_list.append(ListItem(Label(self.graph.nodes[pred].get("label", str(pred)))))

        succ_list = self.query_one("#successors", ListView)
        succ_list.clear()
        for succ in self.successors:
            succ_list.append(ListItem(Label(self.graph.nodes[succ].get("label", str(succ)))))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        selected_item = event.item
        current_list = self.predecessors if event.control.id == "predecessors" else self.successors

        if isinstance(selected_item, ListItem):

            for child in selected_item.children:
                if isinstance(child, Label) and event.control.index != None:
                    self.search_node(current_list[event.control.index])


class QueryParser(BaseParser):

    arg_table = {
        "result-path": {
            "help": "The path of the results to be queried",
            "type": str,
        },
    }

    def __init__(self, args: Namespace, config: Config):
        super().__init__(args, config)

    def parse(self, project_path: str, context: Optional[GraphManager] = None) -> Optional[GraphManager]:
        result_dir = getattr(self.args, "result-path", None)
        if result_dir is None:
            raise ValueError("Result path is required for query parser")

        gml_path = os.path.join(result_dir, "compatible_checked.gml")
        print(f"Loading graph from {gml_path}...")
        graph = nx.read_gml(gml_path)

        app = GraphVisualizer(graph)
        app.run()

        return context
