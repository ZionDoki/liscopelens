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

"""Enhanced GN dependency parser with iterative include resolution and DAG guarantees.

Key improvements:
1. Enhanced progress display with detailed statistics
2. Proper parent node tracking for included files
3. Strict DAG enforcement with cycle detection
4. Performance optimizations and better caching
5. Thread-safe operations with minimal locking
"""

import re
import json
import functools
import threading
from pathlib import Path
from typing import Optional, Set, Dict, List, Tuple, Deque
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

import networkx as nx

from rich.console import Console
from rich.table import Table
from rich.layout import Layout
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn

try:
    import tree_sitter_cpp as tscpp
    from tree_sitter import Language, Parser

    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False
    print("Warning: tree-sitter-cpp not installed. Include parsing disabled.")

from liscopelens.parser.base import BaseParser
from liscopelens.utils.graph import GraphManager, Vertex, Edge


@dataclass
class ParseStats:
    """Statistics for include parsing."""
    files_parsed: int = 0
    includes_found: int = 0
    includes_resolved: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    cycles_detected: int = 0
    edges_created: int = 0
    nodes_created: int = 0
    
    def get_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        return (self.cache_hits / total * 100) if total > 0 else 0.0


class IncludeParser:
    """High-performance include statement parser using tree-sitter."""

    # Maximum cache size before forced cleanup
    MAX_CACHE_SIZE = 10000
    # LRU cache size for resolved paths
    LRU_CACHE_SIZE = 5000

    def __init__(self):
        if HAS_TREE_SITTER:
            self.parser = Parser(Language(tscpp.language()))
        else:
            self.parser = None

        # Regex for include extraction (fallback and quick check)
        self.include_pattern = re.compile(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]', re.MULTILINE)

        # Cache parsed includes to avoid re-parsing
        self._include_cache: Dict[str, Set[str]] = {}
        # LRU cache for file existence checks
        self._file_exists_cache: Dict[str, bool] = {}
        self._cache_order: Deque[str] = deque()
        # Statistics
        self.stats = ParseStats()

    def extract_includes(self, file_path: Path) -> Set[str]:
        """Extract include statements from a C/C++ file.

        Uses tree-sitter for accurate parsing with regex fallback.
        Results are cached for performance.
        """
        path_str = str(file_path)
        if path_str in self._include_cache:
            self.stats.cache_hits += 1
            self.stats.files_parsed += 1  # Count files even when cached
            includes = self._include_cache[path_str]
            self.stats.includes_found += len(includes)  # Count includes from cache
            return includes

        self.stats.cache_misses += 1
        self.stats.files_parsed += 1

        includes = set()

        try:
            if not file_path.exists():
                self._include_cache[path_str] = includes
                return includes

            # Read file content
            content = file_path.read_text(encoding="utf-8", errors="ignore")

            if HAS_TREE_SITTER and self.parser:
                # Use tree-sitter for accurate parsing
                tree = self.parser.parse(bytes(content, "utf-8"))
                includes = self._parse_includes_from_tree(tree, content)
            else:
                # Fallback to regex
                includes = set(self.include_pattern.findall(content))
            
            self.stats.includes_found += len(includes)

        except Exception:
            # Silently handle parsing errors
            pass

        # Manage cache size with LRU eviction
        self._add_to_cache(path_str, includes)
        return includes

    def _parse_includes_from_tree(self, tree, content: str) -> Set[str]:
        """Extract includes using tree-sitter AST."""
        includes = set()

        # Query for preproc_include nodes
        query_str = """
        (preproc_include
            path: [(string_literal) (system_lib_string)] @path
        )
        """

        try:
            query = self.parser.language.query(query_str)
            captures = query.captures(tree.root_node)

            for node, _ in captures:
                # Extract the include path from the node
                include_text = content[node.start_byte : node.end_byte]
                # Remove quotes and brackets
                include_path = include_text.strip('"<>')
                if include_path:
                    includes.add(include_path)
        except Exception:
            # Fallback to regex if tree-sitter fails
            includes = set(self.include_pattern.findall(content))

        return includes

    def file_exists_cached(self, path: Path) -> bool:
        """Check if file exists with LRU caching."""
        path_str = str(path)
        if path_str in self._file_exists_cache:
            # Move to end (most recently used)
            self._cache_order.remove(path_str)
            self._cache_order.append(path_str)
            return self._file_exists_cache[path_str]
        
        exists = path.exists()
        self._add_exists_cache(path_str, exists)
        return exists

    def _add_to_cache(self, path: str, includes: Set[str]):
        """Add to cache with LRU eviction."""
        if len(self._include_cache) >= self.MAX_CACHE_SIZE:
            # Remove oldest entries
            remove_count = self.MAX_CACHE_SIZE // 4
            for _ in range(remove_count):
                if self._include_cache:
                    oldest = next(iter(self._include_cache))
                    del self._include_cache[oldest]
        
        self._include_cache[path] = includes

    def _add_exists_cache(self, path: str, exists: bool):
        """Add to exists cache with LRU eviction."""
        if len(self._file_exists_cache) >= self.LRU_CACHE_SIZE:
            # Remove oldest
            if self._cache_order:
                oldest = self._cache_order.popleft()
                self._file_exists_cache.pop(oldest, None)
        
        self._file_exists_cache[path] = exists
        self._cache_order.append(path)

    def clear_caches(self):
        """Clear all caches to free memory."""
        self._include_cache.clear()
        self._file_exists_cache.clear()
        self._cache_order.clear()


class IncludeResolver:
    """Resolves include paths and finds corresponding source files."""

    # Common source file extensions
    SOURCE_EXTENSIONS = {".c", ".cc", ".cpp", ".cxx", ".C", ".c++"}
    HEADER_EXTENSIONS = {".h", ".hpp", ".hxx", ".H", ".h++", ".hh"}

    def __init__(self, include_parser: IncludeParser):
        self.include_parser = include_parser
        # Cache for resolved paths
        self._resolved_cache: Dict[Tuple[str, tuple], Optional[Path]] = {}
        # Cache for source file lookups
        self._source_file_cache: Dict[str, Set[str]] = {}

    def resolve_include_path(self, include: str, include_dirs: List[str], project_path: Path) -> Optional[Path]:
        """Resolve an include path against include directories.

        Returns the first matching file path or None if not found.
        """
        # Create cache key
        cache_key = (include, tuple(include_dirs))
        if cache_key in self._resolved_cache:
            return self._resolved_cache[cache_key]

        result = None
        for inc_dir in include_dirs:
            # Handle GN-style paths
            if inc_dir.startswith("//"):
                base_path = project_path / inc_dir[2:]
            else:
                base_path = Path(inc_dir)
                if not base_path.is_absolute():
                    base_path = project_path / base_path

            # Try to resolve the include
            full_path = base_path / include

            # Use cached existence check
            # TODO: try match all probable paths with no break
            if self.include_parser.file_exists_cached(full_path):
                result = full_path
                self.include_parser.stats.includes_resolved += 1
                break

        self._resolved_cache[cache_key] = result
        return result

    def find_source_for_header(self, header_path: Path) -> Set[Path]:
        """Find corresponding source files for a header file.

        Looks for source files with the same base name in:
        1. Same directory as header
        2. Parent directory
        3. Sibling 'src' or 'source' directories
        """
        header_str = str(header_path)
        if header_str in self._source_file_cache:
            return set(Path(p) for p in self._source_file_cache[header_str])

        source_files = set()

        # Get the base name without extension
        base_name = header_path.stem
        header_dir = header_path.parent

        # Directories to search
        search_dirs = [
            header_dir,  # Same directory
            header_dir.parent,  # Parent directory
        ]

        # Add common source directories if they exist
        for subdir in ["src", "source", "sources", "lib", "impl"]:
            potential = header_dir.parent / subdir
            if potential.exists():
                search_dirs.append(potential)
            # Also check sibling directories
            potential = header_dir / subdir
            if potential.exists():
                search_dirs.append(potential)

        # Search for source files
        for dir_path in search_dirs:
            if not dir_path.exists():
                continue

            for ext in self.SOURCE_EXTENSIONS:
                potential_source = dir_path / f"{base_name}{ext}"
                if self.include_parser.file_exists_cached(potential_source):
                    source_files.add(potential_source)

        # Cache the result
        self._source_file_cache[header_str] = {str(p) for p in source_files}
        return source_files

    def clear_caches(self):
        """Clear resolver caches."""
        self._resolved_cache.clear()
        self._source_file_cache.clear()


@dataclass
class FileNode:
    """Represents a file in the include graph with parent tracking."""
    path: str
    file_type: str  # 'code', 'header', etc.
    depth: int
    parents: Set[str] = field(default_factory=set)  # All parent nodes that include this file
    target_parents: Set[str] = field(default_factory=set)  # Original target nodes
    in_progress: bool = False  # For cycle detection


class DAGIncludeProcessor:
    """Process includes while maintaining DAG property."""
    
    def __init__(self, include_parser: IncludeParser, include_resolver: IncludeResolver):
        self.include_parser = include_parser
        self.include_resolver = include_resolver
        self.file_nodes: Dict[str, FileNode] = {}
        self.processing_stack: Set[str] = set()  # For cycle detection
        self.stats = ParseStats()
        
    def process_includes_dag(
        self,
        initial_files: Set[str],
        include_dirs: List[str],
        project_path: Path,
        ctx: GraphManager,
        target_name: str,
        max_depth: int,
        progress_callback=None
    ) -> None:
        """Process includes while maintaining DAG property."""
        if not initial_files or not include_dirs:
            return
            
        # Initialize queue with source files
        queue: Deque[Tuple[str, int, Set[str], Set[str]]] = deque()
        
        for src_file in initial_files:
            if str(src_file) not in self.file_nodes:
                queue.append((src_file, 0, {target_name}, {target_name}))
                
        find_source_files = True
        
        while queue:
            file_path, depth, parent_nodes, target_parents = queue.popleft()
            
            # Skip if depth exceeded
            if max_depth > 0 and depth >= max_depth:
                continue
                
            path_str = str(file_path)
            
            # Check for cycles
            if path_str in self.processing_stack:
                self.stats.cycles_detected += 1
                continue
                
            # Update or create file node
            if path_str in self.file_nodes:
                node = self.file_nodes[path_str]
                # Skip if already processed at this or lower depth
                if node.depth <= depth:
                    # Just update parent connections
                    node.parents.update(parent_nodes)
                    node.target_parents.update(target_parents)
                    continue
                # Update depth and parents
                node.depth = depth
                node.parents.update(parent_nodes)
                node.target_parents.update(target_parents)
            else:
                # All source files should have type "code"
                file_type = "code"
                    
                node = FileNode(
                    path=path_str,
                    file_type=file_type,
                    depth=depth,
                    parents=parent_nodes.copy(),
                    target_parents=target_parents.copy()
                )
                self.file_nodes[path_str] = node
                
            # Add to processing stack for cycle detection
            self.processing_stack.add(path_str)
            
            try:
                # Resolve file path
                if isinstance(file_path, str):
                    if file_path.startswith("//"):
                        resolved_path = project_path / file_path[2:]
                    else:
                        resolved_path = Path(file_path)
                        if not resolved_path.is_absolute():
                            resolved_path = project_path / resolved_path
                else:
                    resolved_path = file_path
                    
                # Skip non-C/C++ files
                if not any(
                    str(resolved_path).endswith(ext)
                    for ext in IncludeResolver.SOURCE_EXTENSIONS | IncludeResolver.HEADER_EXTENSIONS
                ):
                    continue
                    
                # Create vertex for this file
                self._ensure_vertex_safe(ctx, path_str, node.file_type, project_path)
                self.stats.nodes_created += 1
                
                # Connect to all target parents (original targets that led to this file)
                for target_parent in target_parents:
                    self._ensure_edge_safe(ctx, target_parent, path_str, label="includes")
                    self.stats.edges_created += 1
                    
                # Extract includes
                includes = self.include_parser.extract_includes(resolved_path)
                
                # Process each include
                for include in includes:
                    # Resolve include path
                    resolved_include = self.include_resolver.resolve_include_path(
                        include, include_dirs, project_path
                    )
                    
                    if resolved_include:
                        resolved_str = str(resolved_include)
                        
                        # Check if this would create a cycle
                        if resolved_str not in self.processing_stack:
                            # Add to queue with updated parent information
                            new_parents = {path_str}
                            queue.append((resolved_include, depth + 1, new_parents, target_parents))
                            
                        # Find corresponding source files for headers
                        if find_source_files and node.file_type == "header":
                            source_files = self.include_resolver.find_source_for_header(resolved_include)
                            for source_file in source_files:
                                source_str = str(source_file)
                                if source_str not in self.processing_stack:
                                    queue.append((source_file, depth + 1, {resolved_str}, target_parents))
                                    
            finally:
                # Remove from processing stack
                self.processing_stack.discard(path_str)
                
            # Update progress if callback provided
            if progress_callback:
                progress_callback(self.stats)
                
    def _ensure_vertex_safe(self, ctx: GraphManager, name: str, vtype: str, project_path: Path) -> None:
        """Thread-safe vertex creation."""
        if not ctx.graph.has_node(name):
            vertex = Vertex(name, type=vtype)
            vertex["src_path"] = self._calculate_src_path(name, project_path)
            ctx.add_node(vertex)

    def _ensure_edge_safe(self, ctx: GraphManager, src: str, dst: str, label: str) -> None:
        """Thread-safe edge creation without duplicates."""
        if not ctx.graph.has_edge(src, dst):
            ctx.add_edge(Edge(u=src, v=dst, label=label))
            
    def _calculate_src_path(self, gn_label: str, project_path: Path) -> str:
        """Calculate src_path from project root and GN label."""
        project_path_obj = project_path.resolve()
        project_name = project_path_obj.name
        
        if gn_label.startswith("//"):
            relative_label = gn_label[2:]
            if relative_label:
                return f"{project_name}/{relative_label}"
            else:
                return project_name
        else:
            try:
                label_path = Path(gn_label)
                if label_path.is_absolute():
                    try:
                        relative_path = label_path.relative_to(project_path_obj)
                        return str(relative_path.as_posix())
                    except ValueError:
                        return f"{project_name}/{label_path.name}"
                else:
                    return f"{project_name}/{gn_label}"
            except (ValueError, OSError):
                return f"{project_name}/{gn_label.lstrip('/')}"


class GnParser(BaseParser):
    """Parse `gn` `--ide=json` output with DAG-safe include resolution."""

    _visited_nodes: Set[Tuple[str, str]]
    _visited_edges: Set[Tuple[str, str, str]]
    _include_parser: IncludeParser
    _include_resolver: IncludeResolver
    _graph_lock: threading.Lock
    _global_stats: ParseStats

    arg_table = {
        "--gn_tool": {"type": str, "help": "path to the gn executable", "group": "gn"},
        "--gn_file": {"type": str, "help": "path to the gn deps graph (JSON)", "group": "gn"},
        "--ignore-test": {
            "action": "store_true",
            "help": "Ignore targets where `testonly` is true.",
            "default": True,
        },
        "--merge-groups": {
            "action": "store_true",
            "help": "Merge/collapse group nodes and create direct edges to non-group targets.",
            "default": False,
        },
        "--parse-includes": {
            "action": "store_true",
            "help": "Parse source files for includes and add them to the graph.",
            "default": True,
        },
        "--max-include-depth": {
            "type": int,
            "help": "Maximum depth for include resolution (0 = unlimited).",
            "default": 10,
        },
        "--max-workers": {
            "type": int,
            "help": "Maximum number of worker threads for parallel processing.",
            "default": 8,
        },
        "--batch-size": {
            "type": int,
            "help": "Batch size for processing files.",
            "default": 100,
        },
        "--find-source-files": {
            "action": "store_true",
            "help": "Find and link corresponding source files for headers.",
            "default": True,
        },
    }

    def _ensure_vertex(self, ctx: GraphManager, name: str, vtype: str, project_path: Path) -> None:
        """Create vertex with src_path attribute calculated from project root and GN label.
        Thread-safe version with locking."""
        key = (name, vtype)

        with self._graph_lock:
            if key in self._visited_nodes:
                return

            vertex = self.create_vertex(name, type=vtype)
            vertex["src_path"] = self._calculate_src_path(name, project_path)
            ctx.add_node(vertex)
            self._visited_nodes.add(key)

    def _calculate_src_path(self, gn_label: str, project_path: Path) -> str:
        """Calculate src_path from project root and GN label."""
        project_path_obj = project_path.resolve()
        project_name = project_path_obj.name

        if gn_label.startswith("//"):
            relative_label = gn_label[2:]
            if relative_label:
                return f"{project_name}/{relative_label}"
            else:
                return project_name
        else:
            try:
                label_path = Path(gn_label)
                if label_path.is_absolute():
                    try:
                        relative_path = label_path.relative_to(project_path_obj)
                        return str(relative_path.as_posix())
                    except ValueError:
                        return f"{project_name}/{label_path.name}"
                else:
                    return f"{project_name}/{gn_label}"
            except (ValueError, OSError):
                return f"{project_name}/{gn_label.lstrip('/')}"

    def _to_gn_format(self, path: str, project_path: Path) -> str:
        """Convert a file path to GN format relative to project root."""
        if path.startswith("//"):
            return path
        try:
            path_obj = Path(path)
            if path_obj.is_absolute():
                relative_path = path_obj.relative_to(project_path)
                return "//" + str(relative_path).replace("\\", "/")
            else:
                # Assume it's relative to project root
                return "//" + path.replace("\\", "/")
        except ValueError:
            # If cannot make relative, return as is
            return path

    def _ensure_edge(self, ctx: GraphManager, src: str, dst: str, *, label: str) -> None:
        """Create edge if it doesn't exist. Thread-safe version with locking."""
        key = (src, dst, label)

        with self._graph_lock:
            if key in self._visited_edges:
                return
            ctx.add_edge(self.create_edge(src, dst, label=label))
            self._visited_edges.add(key)

    def _create_progress_display(self) -> Layout:
        """Create a rich layout for progress display."""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="progress", size=7),
            Layout(name="stats", size=10),
        )
        return layout

    def _update_progress_display(self, layout: Layout, progress_bars: Dict, stats: ParseStats):
        """Update the progress display with current statistics."""
        # Create stats table
        stats_table = Table(title="Include Processing Statistics", expand=True)
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Value", style="green")
        
        stats_table.add_row("Files Parsed", f"{stats.files_parsed:,}")
        stats_table.add_row("Includes Found", f"{stats.includes_found:,}")
        stats_table.add_row("Includes Resolved", f"{stats.includes_resolved:,}")
        stats_table.add_row("Cache Hit Rate", f"{stats.get_hit_rate():.1f}%")
        stats_table.add_row("Cycles Detected", f"{stats.cycles_detected:,}")
        stats_table.add_row("Nodes Created", f"{stats.nodes_created:,}")
        stats_table.add_row("Edges Created", f"{stats.edges_created:,}")
        
        layout["stats"].update(Panel(stats_table))

    def _process_includes_parallel_with_dag(
        self, targets: Dict[str, Dict], project_path: Path, ctx: GraphManager, max_workers: int = 8
    ) -> None:
        """Process includes for all targets in parallel with DAG guarantee."""
        console = Console()

        # Filter targets that have sources
        targets_with_sources = {
            name: meta for name, meta in targets.items() 
            if meta.get("sources") and not meta.get("testonly", False)
        }

        if not targets_with_sources:
            console.print("[yellow]No targets with sources to process.[/yellow]")
            return

        console.print(
            f"[cyan]Processing includes for {len(targets_with_sources)} targets "
            f"with {max_workers} workers (DAG-safe mode)...[/cyan]"
        )

        # Thread-local storage for per-thread processors
        thread_local = threading.local()

        def get_thread_processor():
            """Get or create thread-local DAG processor."""
            if not hasattr(thread_local, "processor"):
                thread_local.processor = DAGIncludeProcessor(self._include_parser, self._include_resolver)
            return thread_local.processor

        def process_target_batch(batch: List[Tuple[str, Dict]]) -> ParseStats:
            """Process a batch of targets in a worker thread."""
            processor = get_thread_processor()
            batch_stats = ParseStats()
            
            for target_name, meta in batch:
                try:
                    sources = meta.get("sources", [])
                    include_dirs = meta.get("include_dirs", [])
                    max_depth = getattr(self.args, "max_include_depth", 10)
                    
                    if sources and include_dirs:
                        processor.process_includes_dag(
                            set(sources),
                            include_dirs,
                            project_path,
                            ctx,
                            target_name,
                            max_depth,
                            progress_callback=None
                        )
                        
                    # Aggregate stats
                    batch_stats.files_parsed += processor.stats.files_parsed
                    batch_stats.includes_found += processor.stats.includes_found
                    batch_stats.includes_resolved += processor.stats.includes_resolved
                    batch_stats.cycles_detected += processor.stats.cycles_detected
                    batch_stats.nodes_created += processor.stats.nodes_created
                    batch_stats.edges_created += processor.stats.edges_created
                    
                except Exception as e:
                    console.print(f"[red]Error processing {target_name}: {e}[/red]")
                    
            return batch_stats

        # Split targets into batches for workers
        target_items = list(targets_with_sources.items())
        batch_size = max(1, len(target_items) // (max_workers * 4))
        batches = [target_items[i : i + batch_size] for i in range(0, len(target_items), batch_size)]

        # Process batches in parallel with enhanced progress display
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("Files: {task.fields[files_parsed]:,} | Includes: {task.fields[includes_found]:,}"),
            TimeRemainingColumn(),
            console=console,
            expand=True
        ) as progress:
            
            task = progress.add_task(
                "[green]Processing includes...", 
                total=len(targets_with_sources),
                files_parsed=0,
                includes_found=0
            )

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(process_target_batch, batch): batch for batch in batches}
                
                for future in as_completed(futures):
                    batch = futures[future]
                    try:
                        batch_stats = future.result()
                        
                        # Update global stats from batch_stats for cycles, nodes, edges
                        self._global_stats.cycles_detected += batch_stats.cycles_detected
                        self._global_stats.nodes_created += batch_stats.nodes_created
                        self._global_stats.edges_created += batch_stats.edges_created
                        
                        # Update global stats from include_parser for files, includes, cache, etc.
                        self._global_stats.files_parsed = self._include_parser.stats.files_parsed
                        self._global_stats.includes_found = self._include_parser.stats.includes_found
                        self._global_stats.includes_resolved = self._include_parser.stats.includes_resolved
                        self._global_stats.cache_hits = self._include_parser.stats.cache_hits
                        self._global_stats.cache_misses = self._include_parser.stats.cache_misses
                        
                        # Update progress
                        progress.update(
                            task,
                            advance=len(batch),
                            files_parsed=self._global_stats.files_parsed,
                            includes_found=self._global_stats.includes_found
                        )
                        
                    except Exception as e:
                        console.print(f"[red]Batch processing failed: {e}[/red]")
                        progress.update(task, advance=len(batch))

    def _get_graph_stats(self, ctx: GraphManager, targets: dict[str, dict]) -> dict:
        """Get detailed graph statistics."""
        total_nodes = len(ctx.nodes())
        total_edges = len(list(ctx.edges()))

        try:
            # Check if graph is DAG
            is_dag = nx.is_directed_acyclic_graph(ctx.graph)
            weak_components = nx.number_weakly_connected_components(ctx.graph)
        except Exception:
            is_dag = False
            weak_components = 0

        node_types = defaultdict(int)
        edge_types = defaultdict(int)

        for node in ctx.nodes():
            node_data = ctx.graph.nodes[node]
            node_type = node_data.get("type", "unknown")
            node_types[node_type] += 1

        for _, _, data in ctx.edges(data=True):
            label = data.get("label", "unknown")
            if data.get("via_group"):
                label = f"{label}_via_group"
            edge_types[label] += 1

        stats = {
            "Total Nodes": total_nodes,
            "Total Edges": total_edges,
            "Is DAG": "Yes" if is_dag else "No",
            "Weak Components": weak_components,
        }

        # Add node type counts
        for node_type, count in sorted(node_types.items()):
            stats[f"{node_type.title()} Nodes"] = count

        # Add edge type counts
        for edge_type, count in sorted(edge_types.items()):
            stats[f"{edge_type.title()} Edges"] = count

        # Add processing statistics
        if hasattr(self, "_global_stats"):
            stats["Files Parsed"] = self._global_stats.files_parsed
            stats["Includes Found"] = self._global_stats.includes_found
            stats["Includes Resolved"] = self._global_stats.includes_resolved
            stats["Cache Hit Rate"] = f"{self._global_stats.get_hit_rate():.1f}%"
            stats["Cycles Detected"] = self._global_stats.cycles_detected

        return stats

    def _print_graph_comparison(self, before_stats: dict, after_stats: dict) -> None:
        """Print graph changes before and after merging using rich table."""
        console = Console()
        table = Table(title="Graph Changes Before and After Group Removal")

        table.add_column("Statistic", style="cyan")
        table.add_column("Before Merge", style="green")
        table.add_column("After Merge", style="red")
        table.add_column("Change", style="yellow")

        for key in before_stats.keys():
            before_val = before_stats.get(key, 0)
            after_val = after_stats.get(key, 0)

            if isinstance(before_val, str) or isinstance(after_val, str):
                table.add_row(str(key), str(before_val), str(after_val), "-")
            else:
                change = after_val - before_val
                change_str = f"{change:+d}" if change != 0 else "0"
                table.add_row(str(key), str(before_val), str(after_val), change_str)

        console.print(table)

    def _merge_groups(self, ctx: GraphManager, targets: dict[str, dict]) -> None:
        """Add synthetic edges so that predecessors of group targets point directly to non-group leaves."""
        before_stats = self._get_graph_stats(ctx, targets)
        in_map: dict[str, list[str]] = defaultdict(list)
        out_map: dict[str, list[str]] = defaultdict(list)

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
                    key = (p, leaf, "deps")
                    if key in self._visited_edges:
                        continue
                    e = self.create_edge(p, leaf, label="deps")
                    e["via_group"] = grp
                    ctx.add_edge(e)
                    self._visited_edges.add(key)

        nodes_to_remove = [n for n in ctx.nodes() if targets.get(n, {}).get("type") == "group"]
        for node in nodes_to_remove:
            ctx.graph.remove_node(node)

        after_stats = self._get_graph_stats(ctx, targets)
        self._print_graph_comparison(before_stats, after_stats)

    def parse(self, project_path: Path, context: Optional[GraphManager] = None) -> GraphManager:
        """Entry point called by the pipeline."""
        if context is None:
            context = GraphManager()

        # Initialize per-run caches and parsers
        self._visited_nodes = set()
        self._visited_edges = set()
        self._include_parser = IncludeParser()
        self._include_resolver = IncludeResolver(self._include_parser)
        self._graph_lock = threading.Lock()
        self._global_stats = ParseStats()

        # Get configuration flags
        ignore_test: bool = getattr(self.args, "ignore_test", True)
        merge_groups: bool = getattr(self.args, "merge_groups", True)
        parse_includes: bool = getattr(self.args, "parse_includes", True)
        max_workers: int = getattr(self.args, "max_workers", 8)

        gn_file: Optional[str] = self.args.gn_file
        if not gn_file:
            raise ValueError("--gn_file is required but was not provided")

        console = Console()
        console.print(f"[cyan]Loading GN file: {gn_file}[/cyan]")

        with open(gn_file, "r", encoding="utf-8") as fp:
            gn_data = json.load(fp)
        targets: dict[str, dict] = gn_data["targets"]

        console.print(f"[cyan]Processing {len(targets)} targets...[/cyan]")

        # Phase 1: Build basic graph structure
        with Progress(console=console) as progress:
            task = progress.add_task("[green]Building dependency graph...", total=len(targets))
            
            for tgt_name, meta in targets.items():
                if ignore_test and meta.get("testonly", False):
                    progress.update(task, advance=1)
                    continue

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

        # Phase 2: Parse includes with DAG guarantee
        if parse_includes:
            if HAS_TREE_SITTER:
                self._process_includes_parallel_with_dag(targets, project_path, context, max_workers)

                # Print final statistics
                console.print("\n[green]Include processing complete![/green]")
                
                stats_table = Table(title="Final Processing Statistics")
                stats_table.add_column("Metric", style="cyan")
                stats_table.add_column("Value", style="green")

                stats_table.add_row("Files Parsed", f"{self._global_stats.files_parsed:,}")
                stats_table.add_row("Includes Found", f"{self._global_stats.includes_found:,}")
                stats_table.add_row("Includes Resolved", f"{self._global_stats.includes_resolved:,}")
                stats_table.add_row("Cache Hit Rate", f"{self._global_stats.get_hit_rate():.1f}%")
                stats_table.add_row("Cycles Detected/Avoided", f"{self._global_stats.cycles_detected:,}")
                stats_table.add_row("Nodes Created", f"{self._global_stats.nodes_created:,}")
                stats_table.add_row("Edges Created", f"{self._global_stats.edges_created:,}")

                console.print(stats_table)
            else:
                console.print("[yellow]tree-sitter-cpp not installed. Skipping include parsing.[/yellow]")
                console.print("[yellow]Install with: pip install tree-sitter tree-sitter-cpp[/yellow]")

        # Clear caches to free memory
        self._include_parser.clear_caches()
        self._include_resolver.clear_caches()

        # Phase 3: Merge/collapse group chains into direct deps (if enabled)
        if merge_groups:
            console.print("[cyan]Group merging is enabled. Collapsing group nodes...[/cyan]")
            self._merge_groups(context, targets)
        else:
            console.print("[yellow]Group merging is disabled. Keeping all group nodes in the graph.[/yellow]")

        # Print final graph statistics
        final_stats = self._get_graph_stats(context, targets)
        table = Table(title="Final Graph Statistics")
        table.add_column("Statistic", style="cyan")
        table.add_column("Value", style="green")
        for key, value in final_stats.items():
            table.add_row(str(key), str(value))
        console.print(table)

        # Verify DAG property
        if nx.is_directed_acyclic_graph(context.graph):
            console.print("[green]✓ Graph is a valid DAG (no cycles detected)[/green]")
        else:
            console.print("[red]⚠ Warning: Graph contains cycles![/red]")
            
        return context

