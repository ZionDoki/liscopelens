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

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Set, Dict, Any

from liscopelens.parser.base import BaseParser
from liscopelens.utils.graph import GraphManager
from liscopelens.utils.structure import DualLicense
from rich.console import Console
from rich.table import Table
import networkx as nx


class ClangInspectParser(BaseParser):

    arg_table = {
        "--inspect-export": {
            "action": "store_true",
            "help": "Export conflict-marked subgraphs (per conflict_id) to nodes/edges JSON",
            "default": False,
        },
        "--output": {
            "type": str,
            "help": "Output directory for exported DAG JSON files (named by conflict id)",
            "default": "output",
        },
        "--include-unrelated": {
            "action": "store_true",
            "help": "Include unrelated deps-leaf nodes (without conflict) under each conflicted node",
            "default": False,
        },
    }

    def parse(self, project_path: Path, context: Optional[GraphManager] = None) -> GraphManager:
        need_export: bool = getattr(self.args, "inspect_export", False)
        if not need_export:
            return context if context is not None else GraphManager()

        output_dir: str = getattr(self.args, "output", "output")
        include_unrelated: bool = getattr(self.args, "include_unrelated", False)

        # When context is missing, load from project_path/compatible_checked.json
        if context is None:
            
            checked_graph = Path(project_path) / "compatible_checked.json"
            context = GraphManager(str(checked_graph))

        # 1) Collect all conflict ids from conflict_group on nodes
        conflict_ids: Set[str] = set()
        for _, data in context.nodes(data=True):
            group = data.get("conflict_group")
            if isinstance(group, (list, set, tuple)):
                for gid in group:
                    if gid:
                        conflict_ids.add(str(gid))
        # Fallback to results.json if still empty
        if not conflict_ids:
            results_path = Path(project_path) / "results.json"
            if results_path.exists():
                try:
                    with open(results_path, "r", encoding="utf-8") as rf:
                        results = json.load(rf)
                    conflict_ids.update(str(k) for k in results.keys())
                except (OSError, json.JSONDecodeError, UnicodeError):
                    conflict_ids.update(set())
        # Legacy fallback: conflict_id/conflict.id on nodes
        if not conflict_ids:
            for _, data in context.nodes(data=True):
                cid = data.get("conflict_id")
                if cid:
                    conflict_ids.add(str(cid))
                cobj = data.get("conflict")
                if isinstance(cobj, dict) and cobj.get("id"):
                    conflict_ids.add(str(cobj.get("id")))

        # If no conflicts, nothing to export
        if not conflict_ids:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            return context

        # Helper to get deps-only neighbours
        def deps_children(node: str) -> list[str]:
            return [v for _, v, d in context.graph.out_edges(node, data=True) if d.get("label") == "deps"]

        def deps_parents(node: str) -> list[str]:
            return [u for u, _, d in context.graph.in_edges(node, data=True) if d.get("label") == "deps"]

        out_dir_path = Path(output_dir)
        out_dir_path.mkdir(parents=True, exist_ok=True)

        # Prepare rich table for per-conflict stats
        console = Console()
        stats_table = Table(title="Conflict Subgraph Stats")
        stats_table.add_column("Conflict ID", style="cyan")
        stats_table.add_column("Weak Components", style="magenta", justify="right")
        stats_table.add_column("Nodes", style="green", justify="right")
        stats_table.add_column("Edges", style="yellow", justify="right")

        # Export one JSON per conflict id
        for cid in conflict_ids:
            # 2) Build subgraph nodes: nodes whose conflict_group includes this cid
            #    Only keep non-code nodes to avoid isolated file nodes (no deps edges)
            sub_nodes: Set[str] = set()
            for node, data in context.nodes(data=True):
                grp = data.get("conflict_group")
                if isinstance(grp, (list, set, tuple)) and str(cid) in {str(x) for x in grp}:
                    if data.get("type") != "code":
                        sub_nodes.add(node)
            # Fallback to legacy fields if nothing found
            if not sub_nodes:
                for node, data in context.nodes(data=True):
                    if str(data.get("conflict_id")) == str(cid) and data.get("type") != "code":
                        sub_nodes.add(node)
                    cobj = data.get("conflict")
                    if isinstance(cobj, dict) and str(cobj.get("id")) == str(cid) and data.get("type") != "code":
                        sub_nodes.add(node)

            # Always include sources files that are involved in conflicts for this conflict_id
            # Load results.json to get conflict-related source files
            results_path = Path(project_path) / "results.json"
            if results_path.exists():
                try:
                    with open(results_path, "r", encoding="utf-8") as rf:
                        results = json.load(rf)

                    conflict_data = results.get(str(cid), {})
                    # For each license in the conflict, collect the associated files
                    for license_key, file_list in conflict_data.items():
                        if license_key != "conflicts" and isinstance(file_list, list):
                            # Find nodes that correspond to these source files
                            for file_path in file_list:
                                # Look for nodes with matching path or src_path
                                for node, data in context.nodes(data=True):
                                    node_path = data.get("path") or data.get("src_path")
                                    if node_path and node_path == file_path:
                                        sub_nodes.add(node)
                                        break
                except (OSError, json.JSONDecodeError, UnicodeError):
                    pass

            # Optionally include all child nodes (deps/sources) of sampled nodes
            if include_unrelated:
                additional: Set[str] = set()
                # For each node in the current subgraph, include all its children that aren't already in sub_nodes
                for node in list(sub_nodes):
                    # Include all deps children
                    for child in deps_children(node):
                        if child not in sub_nodes:
                            child_data = context.get_node_data(child) or {}
                            if child_data.get("before_check"):  # Only include if before_check is not empty
                                additional.add(child)
                    # Include all sources children (outgoing edges to source files)
                    for _, v, d in context.graph.out_edges(node, data=True):
                        if d.get("label") == "sources" and v not in sub_nodes:
                            child_data = context.get_node_data(v) or {}
                            if child_data.get("before_check"):  # Only include if before_check is not empty
                                additional.add(v)
                sub_nodes.update(additional)
            else:
                # Even when not including unrelated nodes, we should include sources files
                # that are directly involved in conflicts
                additional_sources: Set[str] = set()
                for node in list(sub_nodes):
                    # Include sources children that have conflict_group containing this cid
                    for _, v, d in context.graph.out_edges(node, data=True):
                        if d.get("label") == "sources" and v not in sub_nodes:
                            child_data = context.get_node_data(v) or {}
                            child_grp = child_data.get("conflict_group")
                            if isinstance(child_grp, (list, set, tuple)) and str(cid) in {str(x) for x in child_grp}:
                                additional_sources.add(v)
                sub_nodes.update(additional_sources)

            # 4) Collect edges among sub_nodes (deps and sources)
            edges = []
            edge_id = 0
            for u, v, data in context.edges(data=True):
                if data.get("label") not in {"deps", "sources"}:
                    continue
                if u in sub_nodes and v in sub_nodes:
                    edges.append(
                        {
                            "id": f"edge_{edge_id}",
                            "source": u,
                            "target": v,
                            "label": data.get("label"),
                        }
                    )
                    edge_id += 1

            # 5) Build nodes array for this subgraph
            nodes = []
            for n in sub_nodes:
                ndata: Dict[str, Any] = context.get_node_data(n) or {}
                vtype = ndata.get("type")
                children = [succ for succ in deps_children(n) if succ in sub_nodes]
                parents = [pred for pred in deps_parents(n) if pred in sub_nodes]

                origin_data = {
                    "deps": children,
                    "metadata": {},
                    "type": vtype,
                }

                # Convert DualLicense to SPDX expression for before_check and outbound
                def to_expr(val: Any) -> Optional[str]:
                    if isinstance(val, DualLicense):
                        return val.to_spdx_expression()
                    if isinstance(val, list):
                        try:
                            dl = DualLicense.from_list(val)
                            return dl.to_spdx_expression()
                        except (TypeError, ValueError):
                            return None
                    return None

                license_expr = to_expr(ndata.get("before_check"))
                spread_expr = to_expr(ndata.get("outbound"))

                node_json = {
                    "id": n,
                    "name": n,
                    "vtype": vtype,
                    "project": None,
                    "license": license_expr,
                    "spread_license": spread_expr,
                    "score": 0,
                    "license_score": 0,
                    "origin_leaf": "yes" if context.is_leaf(n) else "no",
                    "origin_data": origin_data,
                    "label": "",
                    "reviewed": False,
                    "children": children,
                    "parents": parents,
                    "visible": False,
                    "expanded": False,
                }
                nodes.append(node_json)

            export_data = {"nodes": nodes, "edges": edges}

            # 6) Write output per conflict id
            out_path = out_dir_path / f"{cid}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(export_data, ensure_ascii=False, indent=2))

            # Build directed subgraph to compute weak connectivity stats
            dg = nx.DiGraph()
            dg.add_nodes_from(sub_nodes)
            for e in edges:
                dg.add_edge(e["source"], e["target"])  # deps/sources edges
            weak_components = nx.number_weakly_connected_components(dg) if dg.number_of_nodes() > 0 else 0
            stats_table.add_row(str(cid), str(weak_components), str(len(sub_nodes)), str(len(edges)))

        # Print stats once after processing all conflicts
        console.print(stats_table)
        return context
