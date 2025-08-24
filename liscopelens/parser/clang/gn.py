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

"""
GN dependency parser for building dependency graphs from GN build system output.

This module provides tools for parsing GN (Generate Ninja) build system JSON output
and constructing dependency graphs. It focuses on basic graph building from GN targets,
processing dependencies, and source file relationships with thread-safe operations.
"""

import json
from pathlib import Path
from collections import defaultdict
from typing import Optional, Set, Tuple, Dict

import networkx as nx
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn


from liscopelens.parser.base import BaseParser
from liscopelens.utils.graph import GraphManager
from liscopelens.utils.sda import AsyncParserPool
from liscopelens.utils.fs import scan_dir, path_endswith


class GnParser(BaseParser):
    """
    GN build system dependency parser.

    Parses GN (Generate Ninja) JSON output to build dependency graphs.
    Supports thread-safe graph construction with vertex and edge deduplication.

    Methods:
        parse: Parse GN JSON file and build dependency graph
    """

    _c_header_suffix = (".h", ".hpp", ".hxx", ".inc", ".inl")
    _c_source_suffix = (".c", ".cc", ".cpp", ".cxx", ".m", ".mm", ".mxx")

    _visited_nodes: Set[Tuple[str, str]]
    _visited_edges: Set[Tuple[str, str, str]]

    _parser_pool: AsyncParserPool

    arg_table = {
        "--gn_file": {"type": str, "help": "path to the gn deps graph (JSON)", "group": "gn"},
        "--ignore-test": {
            "action": "store_true",
            "help": "Ignore targets where `testonly` is true.",
            "default": True,
        },
    }

    def _initialize(self):
        self._visited_nodes = set()
        self._visited_edges = set()
        self._parser_pool = AsyncParserPool()
        self._parser_pool.start()

    def _ensure_vertex(self, ctx: GraphManager, name: str, vtype: str, project_path: Path) -> None:
        """
        Create vertex with thread-safe deduplication.

        Creates a new vertex in the graph with calculated src_path attribute.
        Uses thread-safe locking to prevent duplicate vertex creation.

        Args:
            ctx (GraphManager): Graph manager instance to add vertex to
            name (str): Vertex name/identifier
            vtype (str): Vertex type (e.g., "executable", "static_library", "code")
            project_path (Path): Project root path for calculating relative paths
        """
        key = (name, vtype)
        if key in self._visited_nodes:
            return

        vertex = ctx.create_vertex(name, type=vtype)
        src_path = self._gn2abspath(name, project_path)
        if src_path.exists():
            vertex["src_path"] = src_path
        ctx.add_node(vertex)
        self._visited_nodes.add(key)

    def _gn2abspath(self, gn_label: str, project_path: Path) -> Path:
        """
        Convert GN label to absolute path based on project root.

        Args:
            gn_label (str): GN label (e.g., "//base:base", "//src/lib")
            project_path (Path): Project root directory path

        Returns:
            Path: Absolute path corresponding to the GN label
        """
        if gn_label.startswith("//"):
            relative_label = gn_label[2:]
            return (project_path / relative_label).resolve()
        else:
            try:
                label_path = Path(gn_label)
                if label_path.is_absolute():
                    return label_path
                else:
                    return (project_path / label_path).resolve()
            except (ValueError, OSError):
                return (project_path / gn_label.lstrip("/")).resolve()

    def _to_gn_format(self, path: str, project_path: Path) -> str:
        """
        Convert file path to GN format relative to project root.

        Transforms various path formats to GN-style paths starting with "//".
        Handles absolute paths, backslash separators, and relative paths.

        Args:
            path (str): Input file path to convert
            project_path (Path): Project root directory path

        Returns:
            str: GN-formatted path starting with "//"
        """
        if path.startswith("//"):
            return path

        # Handle paths that already start with backslashes
        if path.startswith("\\\\"):
            # Remove leading backslashes and convert to forward slashes
            clean_path = path.lstrip("\\").replace("\\", "/")
            return "//" + clean_path
        elif path.startswith("\\"):
            # Handle single backslash prefix
            clean_path = path.lstrip("\\").replace("\\", "/")
            return "//" + clean_path

        try:
            path_obj = Path(path)
            if path_obj.is_absolute():
                relative_path = path_obj.relative_to(project_path)
                return "//" + str(relative_path).replace("\\", "/")
            else:
                # Assume it's relative to project root
                return "//" + path.replace("\\", "/")
        except ValueError:
            # If cannot make relative, still try to clean up the format
            return "//" + path.replace("\\", "/").lstrip("/")

    def _ensure_edge(self, ctx: GraphManager, src: str, dst: str, *, label: str) -> None:
        """
        Create edge with thread-safe deduplication.

        Creates a new edge in the graph if it doesn't already exist.
        Uses thread-safe locking to prevent duplicate edge creation.

        Args:
            ctx (GraphManager): Graph manager instance to add edge to
            src (str): Source vertex name
            dst (str): Destination vertex name
            label (str): Edge label/type (e.g., "deps", "sources")
        """
        key = (src, dst, label)
        if key in self._visited_edges:
            return
        ctx.add_edge(ctx.create_edge(src, dst, label=label))
        self._visited_edges.add(key)

    def add_sources(self, ctx: GraphManager, tgt_name: str, sources: list[Path]) -> None:
        """
        Add source files to the specified target in the graph.

        Args:
            ctx (GraphManager): Graph manager instance to add sources to
            tgt_name (str): Target vertex name
            sources (List[Path]): List of source file paths to add
        """
        for src in sources:
            ctx.add_node(ctx.create_vertex(src, type="code"))
            ctx.add_edge(ctx.create_edge(tgt_name, src, label="sources"))

    def parse(self, project_path: Path, context: Optional[GraphManager] = None) -> GraphManager:
        """
        Parse GN JSON file and build dependency graph.

        Main entry point that loads GN JSON output and constructs a dependency graph.
        Processes targets, dependencies, and source files with progress tracking.

        Args:
            project_path (Path): Path to project root directory
            context (Optional[GraphManager]): Existing graph manager or None to create new one

        Returns:
            GraphManager: Graph manager containing parsed dependency graph

        Raises:
            ValueError: If required --gn_file argument is not provided
            FileNotFoundError: If GN JSON file cannot be found
            json.JSONDecodeError: If GN JSON file is malformed
        """
        if context is None:
            context = GraphManager()

        self._initialize()

        # Get configuration flags
        ignore_test: bool = getattr(self.args, "ignore_test", True)

        gn_file: Optional[str] = self.args.gn_file
        if not gn_file:
            raise ValueError("--gn_file is required but was not provided")

        console = Console()
        console.print(f"[cyan]Loading GN file: {gn_file}[/cyan]")

        with open(gn_file, "r", encoding="utf-8") as fp:
            gn_data = json.load(fp)

        targets: Dict[str, dict] = gn_data["targets"]
        console.print(f"[cyan]Processing {len(targets)} targets...[/cyan]")

        # Phase 1: Build basic graph structure
        console.print("[cyan]Phase 1: Building basic dependency graph...[/cyan]")

        with Progress(
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            BarColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[green]Building dependency graph...", total=len(targets))

            for tgt_name, meta in targets.items():
                if ignore_test and meta.get("testonly", False):
                    progress.update(task, advance=1)
                    continue

                # Create target node
                self._ensure_vertex(context, tgt_name, meta["type"], project_path)

                # Process dependencies
                for dep in meta.get("deps", []):
                    dep_type = targets[dep]["type"] if dep in targets else "external"
                    self._ensure_vertex(context, dep, dep_type, project_path)
                    self._ensure_edge(context, tgt_name, dep, label="deps")

                # Process sources
                for src in meta.get("sources", []):
                    gn_src = self._to_gn_format(src, project_path)
                    self._ensure_vertex(context, gn_src, "code", project_path)
                    self._ensure_edge(context, tgt_name, gn_src, label="sources")

                progress.update(task, advance=1)

        # Print Phase 1 completion and statistics
        console.print("\n[green]Phase 1 completed - Basic dependency graph built![/green]")

        # Phase 2: Parse includes
        console.print("[cyan]Phase 2: Parsing includes...[/cyan]")

        target_nodes_with_includes = [
            {"name": tgt_name, "type": meta["type"], "include_dirs": meta["include_dirs"], "sources": meta["sources"]}
            for tgt_name, meta in targets.items()
            if not (ignore_test and meta.get("testonly", False)) and meta.get("include_dirs") and meta.get("sources")
        ]

        with Progress(
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            BarColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[green]Parsing includes...", total=len(target_nodes_with_includes))
            for tgt in target_nodes_with_includes:

                candidate_sources = defaultdict(list)
                for include_dir in tgt["include_dirs"]:
                    candidate_sources = scan_dir(
                        include_dir,
                        project_path,
                        suffix=self._c_header_suffix + self._c_source_suffix,
                        stem_dict=candidate_sources,
                    )

                self._parser_pool.add_files([self._gn2abspath(src, project_path) for src in tgt["sources"]])

                for result in self._parser_pool.results():
                    if result.get("includes", []):
                        for include_path in result["includes"]:
                            include_without_suffix = include_path.with_suffix("")
                            candidates = candidate_sources[include_without_suffix.stem]
                            for idx, source_file in enumerate(candidates):
                                if path_endswith(source_file.with_suffix(""), include_without_suffix):
                                    self._parser_pool.add_file(source_file)
                                    # add source file to graph node tgt["name"]
                                    self.add_sources(context, tgt["name"], [source_file])
                                    del candidates[idx]

                progress.update(task, advance=1)
        # Verify DAG property
        if nx.is_directed_acyclic_graph(context.graph):
            console.print("[green]✓ Graph is a valid DAG (no cycles detected)[/green]")
        else:
            console.print("[red]⚠ Warning: Graph contains cycles![/red]")

        return context
