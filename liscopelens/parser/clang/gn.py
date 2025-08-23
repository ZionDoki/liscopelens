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
from enum import Enum

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

match_set = set()

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


class FileProcessingState(Enum):
    """File processing states for tracking."""
    UNPROCESSED = "unprocessed"
    QUEUED = "queued"
    PROCESSING = "processing"
    PROCESSED = "processed"


@dataclass
class ProcessingTask:
    """Represents a file processing task in the queue."""
    file_path: Path
    depth: int
    parent_nodes: Set[str]
    target_parents: Set[str]
    is_header: bool = False
    source_of_header: Optional[str] = None  # If this is a source file found for a header


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
            # Don't count cached files as "parsed" - they were already parsed before
            includes = self._include_cache[path_str]
            # Still count includes found for statistics
            return includes

        self.stats.cache_misses += 1
        

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
        self.stats.files_parsed += 1  # Only count actual parsing, not cache hits
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
        self._resolved_cache: Dict[Tuple[str, tuple], Set[Path]] = {}
        # Cache for source file lookups
        self._source_file_cache: Dict[str, Set[str]] = {}
        # Cache directory contents for fast lookups
        self._dir_contents_cache: Dict[str, Dict[str, Path]] = {}
        # Track resolved includes locally
        self.local_includes_resolved = 0

    def _get_directory_contents(self, directory: Path, max_depth: int = 3) -> Dict[str, Path]:
        """Get all files in directory with caching and depth limit."""
        dir_str = str(directory)
        if dir_str in self._dir_contents_cache:
            return self._dir_contents_cache[dir_str]
        
        contents = {}
        try:
            # Use iterative BFS with depth limit instead of recursive walk
            queue = deque([(directory, 0)])
            visited = set()
            
            while queue:
                current_dir, depth = queue.popleft()
                
                if depth > max_depth or str(current_dir) in visited:
                    continue
                    
                visited.add(str(current_dir))
                
                try:
                    for entry in current_dir.iterdir():
                        if entry.is_file():
                            contents[entry.name] = entry
                        elif entry.is_dir() and depth < max_depth:
                            queue.append((entry, depth + 1))
                except (OSError, PermissionError):
                    continue
                    
        except Exception:
            pass
        
        self._dir_contents_cache[dir_str] = contents
        return contents

    def resolve_include_path(
        self, 
        include: str, 
        include_dirs: List[str], 
        project_path: Path, 
        base_file_path: Optional[Path] = None
    ) -> Set[Path]:
        """Resolve an include path against include directories.
        
        Priority order:
        1. Directory of the including file (if base_file_path provided)
        2. Include directories in order
        """
        cache_key = (
            include,
            tuple(include_dirs),
            str(base_file_path) if base_file_path else ""
        )
        
        if cache_key in self._resolved_cache:
            cached_result = self._resolved_cache[cache_key]
            if cached_result:
                self.local_includes_resolved += len(cached_result)
            return cached_result

        matched_files = set()
        
        # Check if include has path components
        has_path = "/" in include or "\\" in include
        include_path = Path(include)
        include_name = include_path.name
        
        # Priority 1: Directory of the including file (for local includes)
        if base_file_path and base_file_path.parent.exists():
            base_dir = base_file_path.parent
            
            if has_path:
                # Try direct path resolution
                full_path = base_dir / include
                if self.include_parser.file_exists_cached(full_path):
                    matched_files.add(full_path)
            else:
                # Check directory contents
                contents = self._get_directory_contents(base_dir, max_depth=10)
                if include_name in contents:
                    matched_files.add(contents[include_name])
            
            # If found locally, return immediately (common case optimization)
            if matched_files:
                self._resolved_cache[cache_key] = matched_files
                self.local_includes_resolved += len(matched_files)
                return matched_files
        
        # Priority 2: Include directories
        for inc_dir in include_dirs:
            if inc_dir.startswith("//"):
                base_path = project_path / inc_dir[2:]
            else:
                base_path = Path(inc_dir)
                if not base_path.is_absolute():
                    base_path = project_path / base_path
            
            if not base_path.exists():
                continue
            
            if has_path:
                # Try direct path resolution
                full_path = base_path / include
                if self.include_parser.file_exists_cached(full_path):
                    matched_files.add(full_path)
            else:
                # Search in directory contents
                contents = self._get_directory_contents(base_path, max_depth=10)
                if include_name in contents:
                    matched_files.add(contents[include_name])
            
            # Early exit if we found something
            if matched_files:
                break
        
        # Cache and return
        self._resolved_cache[cache_key] = matched_files
        
        if matched_files:
            self.local_includes_resolved += len(matched_files)

        match_set.update(matched_files)
        
        return matched_files

    def find_source_for_header(
        self, 
        header_path: Path, 
        include_dirs: List[str] = None, 
        project_path: Path = None
    ) -> Set[Path]:
        """Find corresponding source files for a header file.
        
        Searches all potential locations and collects all matching source files
        to avoid missing any possible matches. Allows some redundancy to ensure
        completeness.
        """
        header_str = str(header_path)
        if header_str in self._source_file_cache:
            return set(Path(p) for p in self._source_file_cache[header_str])

        if include_dirs is None:
            include_dirs = []
        if project_path is None:
            project_path = Path.cwd()

        base_name = header_path.stem
        source_files = set()
        
        # Collect all potential search directories
        search_paths = []
        
        # Add header's directory
        header_dir = header_path.parent
        if header_dir.exists():
            search_paths.append((header_dir, 0))  # (path, max_depth)
        
        # Add header's parent directory 
        if header_dir.parent.exists():
            parent_dir = header_dir.parent
            search_paths.append((parent_dir, 10))
        
        # Add all include directories
        for inc_dir in include_dirs:
            if inc_dir.startswith("//"):
                base_path = project_path / inc_dir[2:]
            else:
                base_path = Path(inc_dir)
                if not base_path.is_absolute():
                    base_path = project_path / base_path
            
            if base_path.exists():
                search_paths.append((base_path, 2))
        
        # Search all paths and collect all matching source files
        for search_path, max_depth in search_paths:
            contents = self._get_directory_contents(search_path, max_depth=max_depth)
            for _, filepath in contents.items():
                if filepath.stem == base_name and filepath.suffix in self.SOURCE_EXTENSIONS:
                    source_files.add(filepath)
        
        # Cache the result
        self._source_file_cache[header_str] = {str(p) for p in source_files}
        return source_files

    def clear_caches(self):
        """Clear resolver caches."""
        self._resolved_cache.clear()
        self._source_file_cache.clear()
        self._dir_contents_cache.clear()


@dataclass
class FileNode:
    """Represents a file in the include graph with parent tracking."""
    path: str
    file_type: str  # 'code', 'header', etc.
    depth: int
    parents: Set[str] = field(default_factory=set)  # All parent nodes that include this file
    target_parents: Set[str] = field(default_factory=set)  # Original target nodes
    processing_state: FileProcessingState = FileProcessingState.UNPROCESSED


class DAGIncludeProcessor:
    """Process includes while maintaining DAG property."""
    
    def __init__(self, include_parser: IncludeParser, include_resolver: IncludeResolver):
        self.include_parser = include_parser
        self.include_resolver = include_resolver
        self.file_nodes: Dict[str, FileNode] = {}
        self.processing_queue: Deque[ProcessingTask] = deque()
        self.processed_files: Set[str] = set()  # Files that have been fully processed
        self.queued_files: Set[str] = set()  # Files currently in queue
        self.stats = ParseStats()
        # Local stats tracking
        self.local_files_parsed = 0
        self.local_includes_found = 0
        
    def process_includes_dag(
        self,
        initial_files: Set[str],
        include_dirs: List[str],
        project_path: Path,
        ctx: GraphManager,
        target_name: str,
        max_depth: int,
        find_source_files: bool = True,
        progress_callback=None
    ) -> None:
        """Process includes while maintaining DAG property with proper task queue management."""
        if not initial_files or not include_dirs:
            return
        
        # Reset local counters for this target
        self.local_files_parsed = 0
        self.local_includes_found = 0
        
        # Initialize queue with source files
        for src_file in initial_files:
            # Resolve file path to check if it's a header
            if src_file.startswith("//"):
                file_path = project_path / src_file[2:]
            else:
                print(src_file)
                file_path = Path(src_file)
                if not file_path.is_absolute():
                    file_path = project_path / file_path
            
            # If initial file is a header, find corresponding source files
            if find_source_files and file_path.suffix in IncludeResolver.HEADER_EXTENSIONS:
                source_files = self.include_resolver.find_source_for_header(
                    file_path, include_dirs, project_path
                )
                
                # Enqueue source files
                for source_file in source_files:
                    self._enqueue_file(
                        file_path=source_file,
                        depth=0,
                        parent_nodes={target_name},
                        target_parents={target_name},
                        is_header=False,
                        source_of_header=str(file_path)
                    )
            # Always enqueue the file itself (remove the has_node check)
            self._enqueue_file(
                file_path=file_path,
                depth=0,
                parent_nodes={target_name},
                target_parents={target_name},
                is_header=file_path.suffix in IncludeResolver.HEADER_EXTENSIONS
            )
        
        # Process queue
        while self.processing_queue:
            task = self.processing_queue.popleft()
            
            # Skip if depth exceeded
            if max_depth > 0 and task.depth >= max_depth:
                continue
            
            path_str = str(task.file_path)
            
            # Remove from queued set as we're processing it now
            self.queued_files.discard(path_str)
            
            # Skip if already fully processed
            if path_str in self.processed_files:
                # Just update parent connections if needed
                if path_str in self.file_nodes:
                    node = self.file_nodes[path_str]
                    node.parents.update(task.parent_nodes)
                    node.target_parents.update(task.target_parents)
                continue
            
            # Process the file
            self._process_single_file(
                task=task,
                include_dirs=include_dirs,
                project_path=project_path,
                ctx=ctx,
                find_source_files=find_source_files
            )
            
            # Mark as processed
            self.processed_files.add(path_str)
            
            # Only count files that were discovered through includes (depth > 0)
            if task.depth > 0:
                self.local_files_parsed += 1
            
            # Update progress if callback provided
            if progress_callback:
                progress_callback(self.stats)
        
        # Update total stats
        self.stats.files_parsed = self.local_files_parsed
        self.stats.includes_found = self.local_includes_found
    
    def _to_gn_format(self, path: str, project_path: Path) -> str:
        """Convert a file path to GN format relative to project root."""
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
                return "//" + path.replace("\\", "/")
        except ValueError:
            # If cannot make relative, still try to clean up the format
            return "//" + path.replace("\\", "/").lstrip("/")
    
    def _enqueue_file(
        self,
        file_path,
        depth: int,
        parent_nodes: Set[str],
        target_parents: Set[str],
        is_header: bool = False,
        source_of_header: Optional[str] = None
    ) -> None:
        """Add a file to the processing queue if not already queued or processed."""
        path_str = str(file_path)
        
        # Skip if already processed or queued
        if path_str in self.processed_files or path_str in self.queued_files:
            # Update parent relationships if file exists
            if path_str in self.file_nodes:
                node = self.file_nodes[path_str]
                node.parents.update(parent_nodes)
                node.target_parents.update(target_parents)
            return
        
        # Create task and add to queue
        task = ProcessingTask(
            file_path=file_path if isinstance(file_path, Path) else Path(file_path),
            depth=depth,
            parent_nodes=parent_nodes.copy(),
            target_parents=target_parents.copy(),
            is_header=is_header,
            source_of_header=source_of_header
        )
        
        self.processing_queue.append(task)
        self.queued_files.add(path_str)
    
    def _process_single_file(
        self,
        task: ProcessingTask,
        include_dirs: List[str],
        project_path: Path,
        ctx: GraphManager,
        find_source_files: bool
    ) -> None:
        """Process a single file from the task queue."""
        # Resolve file path first
        if isinstance(task.file_path, str):
            if task.file_path.startswith("//"):
                resolved_path = project_path / task.file_path[2:]
            else:
                resolved_path = Path(task.file_path)
                if not resolved_path.is_absolute():
                    resolved_path = project_path / resolved_path
        else:
            resolved_path = task.file_path
        
        # Skip non-C/C++ files
        if not any(
            str(resolved_path).endswith(ext)
            for ext in IncludeResolver.SOURCE_EXTENSIONS | IncludeResolver.HEADER_EXTENSIONS
        ):
            return
        
        # Convert to GN format for consistency
        gn_path_str = self._to_gn_format(str(resolved_path), project_path)
        
        # Update or create file node
        if gn_path_str in self.file_nodes:
            node = self.file_nodes[gn_path_str]
            node.depth = min(node.depth, task.depth)
            node.parents.update(task.parent_nodes)
            node.target_parents.update(task.target_parents)
        else:
            # Determine file type
            if task.file_path.suffix in IncludeResolver.HEADER_EXTENSIONS:
                file_type = "header"
            else:
                file_type = "code"
            
            node = FileNode(
                path=gn_path_str,
                file_type=file_type,
                depth=task.depth,
                parents=task.parent_nodes.copy(),
                target_parents=task.target_parents.copy(),
                processing_state=FileProcessingState.PROCESSING
            )
            self.file_nodes[gn_path_str] = node
        
        # Only create vertex if it doesn't exist (avoid duplicates from Phase 1)
        if not ctx.graph.has_node(gn_path_str):
            self._ensure_vertex_safe(ctx, gn_path_str, node.file_type, project_path)
            self.stats.nodes_created += 1
        
        # Create edges for ALL files to their target parents (GN task nodes)
        # This ensures all files discovered through includes are connected to the GN task
        for target_parent in task.target_parents:
            if not ctx.graph.has_edge(target_parent, gn_path_str):
                self._ensure_edge_safe(ctx, target_parent, gn_path_str, label="sources")
                self.stats.edges_created += 1
        
        # Extract includes from this file
        includes = self.include_parser.extract_includes(resolved_path)
        self.local_includes_found += len(includes)
        
        # Process each include
        for include in includes:
            # Resolve include path
            resolved_includes = self.include_resolver.resolve_include_path(
                include, include_dirs, project_path, base_file_path=resolved_path
            )
            
            # Process all resolved includes
            for resolved_include in resolved_includes:
                resolved_str = str(resolved_include)
                
                # Check for circular dependency
                if resolved_str not in task.parent_nodes:
                    # If this is a header file, find corresponding source files first
                    if find_source_files and resolved_include.suffix in IncludeResolver.HEADER_EXTENSIONS:
                        # Find source files for this header
                        source_files = self.include_resolver.find_source_for_header(
                            resolved_include, include_dirs, project_path
                        )
                        
                        # Enqueue source files first
                        for source_file in source_files:
                            source_str = str(source_file)
                            if source_str not in task.parent_nodes:
                                self._enqueue_file(
                                    file_path=source_file,
                                    depth=task.depth + 1,
                                    parent_nodes={gn_path_str},
                                    target_parents=task.target_parents,
                                    is_header=False,
                                    source_of_header=resolved_str
                                )
                    
                    # Then enqueue the header file itself
                    self._enqueue_file(
                        file_path=resolved_include,
                        depth=task.depth + 1,
                        parent_nodes={gn_path_str},
                        target_parents=task.target_parents,
                        is_header=resolved_include.suffix in IncludeResolver.HEADER_EXTENSIONS
                    )
                else:
                    self.stats.cycles_detected += 1
        
        # Mark as processed
        node.processing_state = FileProcessingState.PROCESSED
    
    def _ensure_vertex_safe(self, ctx: GraphManager, name: str, vtype: str, project_path: Path) -> None:
        """Thread-safe vertex creation."""
        # Name should already be in GN format when passed to this method
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
            "default": 15,
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

    def _update_progress_display(self, layout: Layout, stats: ParseStats):
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
            """Get or create thread-local DAG processor with its own parser/resolver."""
            if not hasattr(thread_local, "processor"):
                # Create thread-local instances to avoid shared state issues
                thread_parser = IncludeParser()
                thread_resolver = IncludeResolver(thread_parser)
                thread_local.processor = DAGIncludeProcessor(thread_parser, thread_resolver)
            return thread_local.processor

        def process_target_batch(batch: List[Tuple[str, Dict]]) -> ParseStats:
            """Process a batch of targets in a worker thread."""
            processor = get_thread_processor()
            batch_stats = ParseStats()
            
            for target_name, meta in batch:
                # CRITICAL: Reset processor state for each target
                processor.processed_files.clear()
                processor.queued_files.clear()
                processor.file_nodes.clear()
                processor.processing_queue.clear()

                try:
                    sources = meta.get("sources", [])
                    include_dirs = meta.get("include_dirs", [])
                    max_depth = getattr(self.args, "max_include_depth", 15)
                    find_source_files = getattr(self.args, "find_source_files", True)

                    if sources and include_dirs:
                        # Process this target
                        processor.process_includes_dag(
                            set(sources),
                            include_dirs,
                            project_path,
                            ctx,
                            target_name,
                            max_depth,
                            find_source_files=find_source_files,
                            progress_callback=None
                        )
                    
                except Exception as e:
                    console.print(f"[red]Error processing {target_name}: {e}[/red]")
            
            # Return aggregated stats from this thread's processor
            batch_stats.files_parsed = processor.include_parser.stats.files_parsed
            batch_stats.includes_found = processor.include_parser.stats.includes_found
            batch_stats.includes_resolved = processor.include_resolver.local_includes_resolved
            batch_stats.cache_hits = processor.include_parser.stats.cache_hits
            batch_stats.cache_misses = processor.include_parser.stats.cache_misses
            batch_stats.cycles_detected = processor.stats.cycles_detected
            batch_stats.nodes_created = processor.stats.nodes_created
            batch_stats.edges_created = processor.stats.edges_created
                    
            return batch_stats

        # Split targets into batches for workers
        target_items = list(targets_with_sources.items())
        # Smaller batch size for better progress granularity
        batch_size = max(1, len(target_items) // (max_workers * 10))
        batches = [target_items[i : i + batch_size] for i in range(0, len(target_items), batch_size)]

        # Reset global stats
        self._global_stats = ParseStats()
        completed_targets = 0

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
                        
                        # Aggregate stats from this batch
                        self._global_stats.files_parsed += batch_stats.files_parsed
                        self._global_stats.includes_found += batch_stats.includes_found
                        self._global_stats.includes_resolved += batch_stats.includes_resolved
                        self._global_stats.cycles_detected += batch_stats.cycles_detected
                        self._global_stats.nodes_created += batch_stats.nodes_created
                        self._global_stats.edges_created += batch_stats.edges_created
                        self._global_stats.cache_hits += batch_stats.cache_hits
                        self._global_stats.cache_misses += batch_stats.cache_misses
                        
                        # Update completed targets
                        completed_targets += len(batch)
                        
                        # Update progress
                        progress.update(
                            task,
                            advance=len(batch),
                            files_parsed=self._global_stats.files_parsed,
                            includes_found=self._global_stats.includes_found
                        )
                        
                    except Exception as e:
                        console.print(f"[red]Batch processing failed: {e}[/red]")
                        completed_targets += len(batch)
                        progress.update(
                            task, 
                            advance=len(batch)
                        )

    def _print_stats_table(self, stats: dict, title: str) -> None:
        """Print statistics in a 6-column format (3 stats per row)."""
        console = Console()
        table = Table(title=title, expand=True)
        
        # Add 6 columns: 3 pairs of (Statistic, Value)
        table.add_column("Statistic 1", style="cyan", width=20)
        table.add_column("Value 1", style="green", width=8)
        table.add_column("Statistic 2", style="cyan", width=20)
        table.add_column("Value 2", style="green", width=8)
        table.add_column("Statistic 3", style="cyan", width=20)
        table.add_column("Value 3", style="green", width=8)
        
        stats_items = list(stats.items())
        
        # Group stats into rows of 3
        for i in range(0, len(stats_items), 3):
            row_items = stats_items[i:i+3]
            
            # Pad the row if needed
            while len(row_items) < 3:
                row_items.append(("", ""))
            
            # Create the row
            row = []
            for stat, value in row_items:
                row.extend([str(stat), str(value)])
            
            table.add_row(*row)
        
        console.print(table)

    def _get_graph_stats(self, ctx: GraphManager, targets: dict[str, dict] = None) -> dict:
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

        table.add_column("Statistic", style="cyan", width=25)
        table.add_column("Before", style="green", width=10)
        table.add_column("After", style="red", width=10)
        table.add_column("Change", style="yellow", width=10)

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

        # Print Phase 1 statistics
        console.print("\n[green]Phase 1 completed - Basic dependency graph built![/green]")
        phase1_stats = self._get_graph_stats(context, targets)
        self._print_stats_table(phase1_stats, "Phase 1 Graph Statistics")

        # Phase 2: Parse includes with DAG guarantee
        if parse_includes:
            if HAS_TREE_SITTER:
                self._process_includes_parallel_with_dag(targets, project_path, context, max_workers)

                # Print final statistics
                console.print("\n[green]Include processing complete![/green]")
                
                include_stats = {
                    "Files Parsed": f"{self._global_stats.files_parsed:,}",
                    "Includes Found": f"{self._global_stats.includes_found:,}",
                    "Includes Resolved": f"{self._global_stats.includes_resolved:,}",
                    "Cache Hit Rate": f"{self._global_stats.get_hit_rate():.1f}%",
                    "Cycles Detected/Avoided": f"{self._global_stats.cycles_detected:,}",
                    "Nodes Created": f"{self._global_stats.nodes_created:,}",
                    "Edges Created": f"{self._global_stats.edges_created:,}"
                }
                
                self._print_stats_table(include_stats, "Include Processing Statistics")
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
        self._print_stats_table(final_stats, "Final Graph Statistics")

        # Verify DAG property
        if nx.is_directed_acyclic_graph(context.graph):
            console.print("[green]✓ Graph is a valid DAG (no cycles detected)[/green]")
        else:
            console.print("[red]⚠ Warning: Graph contains cycles![/red]")

        return context
