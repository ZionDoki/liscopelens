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

"""Enhanced GN dependency parser that performs two-phase graph construction:
1.  First pass – build the raw graph exactly as GN describes (groups remain explicit).
2.  Second pass – collapse/merge all `group` targets so that every upstream target
    obtains direct edges to the terminal (non-group) targets it really depends on.

This avoids the "many tiny connected components" problem caused by group chains
(A -> B(group) -> C(group) -> D(object)…).

The implementation is self-contained; no external flatten-in-advance logic is
required. After parsing a GN graph file you will get a `GraphManager` where:
  • All original targets and edges are preserved.
  • Additional synthetic edges (label="deps", attr `via_group=<group name>`)
    directly connect each predecessor of a group to that group's non-group
    leaf nodes.
  • Each node has a `src_path` attribute calculated from project root + GN label.
You may safely ignore or delete the original group nodes when performing reach-
ability or connected-component analysis."""

import json
import functools
from pathlib import Path
from typing import Optional
from collections import defaultdict

from rich.progress import track
from rich.console import Console
from rich.table import Table

from liscopelens.parser.base import BaseParser
from liscopelens.utils.graph import GraphManager


class GnParser(BaseParser):
    """Parse `gn` `--ide=json` output and build a dependency graph."""

    _visited_nodes: set[tuple[str, str]]
    _visited_edges: set[tuple[str, str, str]]

    arg_table = {
        "--gn_tool": {"type": str, "help": "path to the gn executable", "group": "gn"},
        "--gn_file": {"type": str, "help": "path to the gn deps graph (JSON)", "group": "gn"},
        "--ignore-test": {
            "action": "store_true",
            "help": "Ignore targets where `testonly` is true.",
            "default": True,
            "group": "gn",
        },
        "--merge-groups": {
            "action": "store_true",
            "help": "Merge/collapse group nodes and create direct edges to non-group targets.",
            "default": False,
            "group": "gn",
        },
    }

    def _ensure_vertex(self, ctx: GraphManager, name: str, vtype: str, project_path: Path) -> None:
        """Create vertex with src_path attribute calculated from project root and GN label."""
        key = (name, vtype)
        if key in self._visited_nodes:
            return
        
        vertex = self.create_vertex(name, type=vtype)
        
        # Calculate src_path attribute
        vertex["src_path"] = self._calculate_src_path(name, project_path)
        
        ctx.add_node(vertex)
        self._visited_nodes.add(key)

    def _calculate_src_path(self, gn_label: str, project_path: Path) -> str:
        """Calculate src_path from project root and GN label.
        
        Args:
            gn_label: GN label (e.g., "//d/e/f/g" or "/path/to/file.c")
            project_path: Project root path (e.g., "/a/b/c")
            
        Returns:
            Combined path (e.g., "c/d/e/f/g")
        """
        # Use Path for proper path handling
        project_path_obj = project_path.resolve()
        project_name = project_path_obj.name
        
        if gn_label.startswith("//"):
            # GN target label: remove "//" prefix and combine with project name
            relative_label = gn_label[2:]  # Remove "//"
            if relative_label:
                return f"{project_name}/{relative_label}"
            else:
                return project_name
        else:
            # File path: calculate relative to project if absolute, otherwise use as-is
            try:
                label_path = Path(gn_label)
                if label_path.is_absolute():
                    # Try to make it relative to project root
                    try:
                        relative_path = label_path.relative_to(project_path_obj)
                        return str(relative_path.as_posix())
                    except ValueError:
                        # If not under project root, use project name + relative path
                        return f"{project_name}/{label_path.name}"
                else:
                    # Relative path: combine with project name
                    return f"{project_name}/{gn_label}"
            except (ValueError, OSError):
                # Fallback: use project name + label
                return f"{project_name}/{gn_label.lstrip('/')}"

    def _ensure_edge(self, ctx: GraphManager, src: str, dst: str, *, label: str) -> None:
        key = (src, dst, label)
        if key in self._visited_edges:
            return
        ctx.add_edge(self.create_edge(src, dst, label=label))
        self._visited_edges.add(key)

    def _get_graph_stats(self, ctx: GraphManager, targets: dict[str, dict]) -> dict:
        """Get graph statistics"""
        total_nodes = len(ctx.nodes())
        total_edges = len(list(ctx.edges()))

        group_nodes = 0
        non_group_nodes = 0
        for node in ctx.nodes():
            if targets.get(node, {}).get("type") == "group":
                group_nodes += 1
            else:
                non_group_nodes += 1

        deps_edges = 0
        sources_edges = 0
        via_group_edges = 0
        for _, _, data in ctx.edges(data=True):
            if data.get("label") == "deps":
                if data.get("via_group"):
                    via_group_edges += 1
                else:
                    deps_edges += 1
            elif data.get("label") == "sources":
                sources_edges += 1

        return {
            "Total Nodes": total_nodes,
            "Total Edges": total_edges,
            "Group Nodes": group_nodes,
            "Non-Group Nodes": non_group_nodes,
            "Deps Edges": deps_edges,
            "Sources Edges": sources_edges,
            "Via Group Edges": via_group_edges,
        }

    def _print_graph_comparison(self, before_stats: dict, after_stats: dict) -> None:
        """Print graph changes before and after merging using rich table"""
        console = Console()
        table = Table(title="Graph Changes Before and After Group Removal")

        table.add_column("Statistic", style="cyan")
        table.add_column("Before Merge", style="green")
        table.add_column("After Merge", style="red")
        table.add_column("Change", style="yellow")

        for key in before_stats.keys():
            before_val = before_stats[key]
            after_val = after_stats[key]
            change = after_val - before_val
            change_str = f"{change:+d}" if change != 0 else "0"

            table.add_row(str(key), str(before_val), str(after_val), change_str)

        console.print(table)

    def _merge_groups(self, ctx: GraphManager, targets: dict[str, dict]) -> None:
        """Add synthetic edges so that predecessors of group targets point directly to non-group leaves."""
        # Get statistics before merging
        before_stats = self._get_graph_stats(ctx, targets)
        in_map: dict[str, list[str]] = defaultdict(list)  # dst (group) → [src…]
        out_map: dict[str, list[str]] = defaultdict(list)  # src (group) → [dst…]

        for src, dst, data in ctx.edges(data=True):
            label = data.get("label")
            if label != "deps":
                continue
            if targets.get(dst, {}).get("type") == "group":
                in_map[dst].append(src)
            if targets.get(src, {}).get("type") == "group":
                out_map[src].append(dst)

        @functools.lru_cache(maxsize=None)
        def _terminals(g: str) -> list[str]:
            leaves: list[str] = []
            for nxt in out_map.get(g, []):
                if targets.get(nxt, {}).get("type") == "group":
                    leaves.extend(_terminals(nxt))
                else:
                    leaves.append(nxt)
            return leaves

        for grp, preds in in_map.items():
            leaves = _terminals(grp)
            for p in preds:
                for leaf in leaves:
                    # avoid duplicate synthetic edge
                    key = (p, leaf, "deps")
                    if key in self._visited_edges:
                        continue
                    e = self.create_edge(p, leaf, label="deps")
                    e["via_group"] = grp  # keep traceability
                    ctx.add_edge(e)
                    self._visited_edges.add(key)

        nodes_to_remove = [n for n in ctx.nodes() if targets.get(n, {}).get("type") == "group"]
        for node in nodes_to_remove:
            ctx.graph.remove_node(node)

        # Get statistics after merging and print comparison
        after_stats = self._get_graph_stats(ctx, targets)
        self._print_graph_comparison(before_stats, after_stats)

    def parse(self, project_path: Path, context: Optional[GraphManager] = None) -> GraphManager:
        """Entry point called by the pipeline."""
        if context is None:
            context = GraphManager()

        # init per‑run caches
        self._visited_nodes = set()
        self._visited_edges = set()

        ignore_test: bool = getattr(self.args, "ignore_test", True)
        merge_groups: bool = getattr(self.args, "merge_groups", True)

        gn_file: Optional[str] = self.args.gn_file
        if not gn_file:
            raise ValueError("--gn_file is required but was not provided")

        with open(gn_file, "r", encoding="utf‑8") as fp:
            gn_data = json.load(fp)
        targets: dict[str, dict] = gn_data["targets"]

        for tgt_name, meta in track(targets.items(), description="Parsing GN file…"):
            if ignore_test and meta.get("testonly", False):
                continue
            self._ensure_vertex(context, tgt_name, meta["type"], project_path)

            for dep in meta.get("deps", []):
                dep_type = targets[dep]["type"] if dep in targets else "external"
                self._ensure_vertex(context, dep, dep_type, project_path)
                self._ensure_edge(context, tgt_name, dep, label="deps")

            for src in meta.get("sources", []):
                self._ensure_vertex(context, src, "code", project_path)
                self._ensure_edge(context, tgt_name, src, label="sources")

        # Phase 2: merge/collapse group chains into direct deps (if enabled)
        if merge_groups:
            console = Console()
            console.print("[cyan]Group merging is enabled. Collapsing group nodes...[/cyan]")
            self._merge_groups(context, targets)
        else:
            console = Console()
            console.print("[yellow]Group merging is disabled. Keeping all group nodes in the graph.[/yellow]")
            # Print current graph statistics
            stats = self._get_graph_stats(context, targets)
            table = Table(title="Graph Statistics (Without Merging)")
            table.add_column("Statistic", style="cyan")
            table.add_column("Value", style="green")
            for key, value in stats.items():
                table.add_row(str(key), str(value))
            console.print(table)

        return context
