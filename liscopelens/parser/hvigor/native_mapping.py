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
Hvigor Native mapping parser for stage three analysis.
This parser adds file nodes to existing Native module nodes for all Native modules.
"""

import os
import argparse
import warnings
from pathlib import Path
from typing import Optional, Dict, List, Any

from liscopelens.parser.base import BaseParser
from liscopelens.utils.graph import GraphManager
from liscopelens.utils.structure import Config


class HvigorNativeMappingParser(BaseParser):
    """
    Parser for Hvigor project Native file mapping (Stage Three).

    This parser implements stage three of the Hvigor project analysis:
    - Scan all files in Native modules
    - Create file nodes and establish module-to-file relationships
    - Extract file-level information for license analysis
    """

    arg_table = {
        "--hvigor-path": {
            "type": str,
            "help": "Path to the Hvigor project root directory",
            "default": ".",
        },
        "--output": {
            "type": str,
            "help": "Output directory to save the mapping results",
        },
    }

    def __init__(self, args: argparse.Namespace, config: Config):
        """
        Initialize the Hvigor Native mapping parser.

        Args:
            args: Command line arguments
            config: Parser configuration
        """
        super().__init__(args, config)
        self.project_root = None
        self.project_name = None

        # File extensions to scan for different file types in Native modules
        self.native_source_extensions = {".c", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".hxx", ".s", ".S"}
        self.build_config_extensions = {".txt", ".cmake", ".mk", ".json", ".json5", ".xml", ".yaml", ".yml"}
        self.resource_extensions = {".png", ".jpg", ".jpeg", ".svg", ".ico", ".bmp", ".gif"}
        self.archive_extensions = {".a", ".so", ".lib", ".dll"}

    def _normalize_path(self, path: str) -> str:
        """
        Normalize file path to use // prefix for hvigor nodes.

        Args:
            path: Original file path

        Returns:
            Normalized path with // prefix
        """
        # Convert to forward slashes and ensure it starts with //
        normalized = path.replace("\\", "/")
        if not normalized.startswith("//"):
            if normalized.startswith("/"):
                normalized = "/" + normalized
            else:
                normalized = "//" + normalized
        return normalized

    def _discover_project_info(self, project_path: str) -> bool:
        """
        Discover basic project information.

        Args:
            project_path: Path to the project root

        Returns:
            True if project info is successfully discovered
        """
        self.project_root = Path(project_path).resolve()
        self.project_name = self.project_root.name
        return True

    def _get_native_modules(self, context: GraphManager) -> List[Dict[str, Any]]:
        """
        Extract Native module nodes from the existing graph context.

        Args:
            context: Graph manager instance

        Returns:
            List of Native module node data dictionaries
        """
        module_nodes = []
        for node_id, node_data in context.nodes(data=True):
            # Native modules now have type "shared_library" or still have is_native flag
            if (node_data.get("type") == "shared_library" or
                (node_data.get("type") == "module" and node_data.get("is_native", False))):
                module_nodes.append({"id": node_id, "data": node_data})
        return module_nodes

    def _scan_module_files(self, module_path: Path, module_name: str) -> List[Dict[str, Any]]:
        """
        Scan all files in a Native module directory.

        Args:
            module_path: Path to the module directory
            module_name: Name of the module

        Returns:
            List of file information dictionaries
        """
        files = []

        # Define directories to scan for Native modules
        scan_dirs = [
            module_path / "src" / "main" / "cpp",  # C/C++ source files
            module_path / "src" / "main" / "c",    # C source files
            module_path / "src" / "main" / "ets",  # ArkTS source files in Native modules
            module_path / "src" / "main" / "js",   # JavaScript source files
            module_path / "src" / "main" / "resources",  # Resource files
            module_path / "src" / "main",          # Main directory
            module_path / "thirdparty",            # Third-party libraries
            module_path,                           # Module root for config files
        ]

        # Scan each directory
        for scan_dir in scan_dirs:
            if scan_dir.exists() and scan_dir.is_dir():
                files.extend(self._scan_directory_recursive(scan_dir, module_path, module_name))

        return files

    def _scan_directory_recursive(self, directory: Path, module_root: Path, module_name: str) -> List[Dict[str, Any]]:
        """
        Recursively scan a directory for all files.

        Args:
            directory: Directory to scan
            module_root: Root path of the module
            module_name: Name of the module

        Returns:
            List of file information dictionaries
        """
        files = []

        try:
            for item in directory.rglob("*"):
                if item.is_file() and self._should_include_file(item):
                    # Calculate relative path from module root
                    try:
                        rel_path = item.relative_to(module_root)
                        file_info = self._extract_file_info(item, rel_path, module_name)
                        if file_info:
                            files.append(file_info)
                    except ValueError:
                        # File is not under module root, skip
                        continue
        except (OSError, PermissionError) as e:
            warnings.warn(f"Failed to scan directory {directory}: {e}")

        return files

    def _should_include_file(self, file_path: Path) -> bool:
        """
        Determine if a file should be included in the analysis.

        Args:
            file_path: Path to the file

        Returns:
            True if file should be included
        """
        # Skip hidden files and directories
        if any(part.startswith(".") for part in file_path.parts):
            return False

        # Skip build output directories
        skip_dirs = {"build", "node_modules", "oh_modules", ".hvigor", "dist", "out", "target", ".git", ".svn"}
        if any(part in skip_dirs for part in file_path.parts):
            return False

        # Include all relevant file types for Native modules
        suffix = file_path.suffix.lower()
        return (
            suffix in self.native_source_extensions
            or suffix in self.build_config_extensions
            or suffix in self.resource_extensions
            or suffix in self.archive_extensions
            or file_path.name in {"CMakeLists.txt", "Makefile", "build.gradle", "hvigorfile.ts", 
                                  "module.json5", "oh-package.json5", "build-profile.json5"}
        )

    def _extract_file_info(self, file_path: Path, rel_path: Path, module_name: str) -> Optional[Dict[str, Any]]:
        """
        Extract information from a file.

        Args:
            file_path: Absolute path to the file
            rel_path: Relative path from module root
            module_name: Name of the containing module

        Returns:
            File information dictionary or None if extraction fails
        """
        try:
            file_stats = file_path.stat()
            suffix = file_path.suffix.lower()

            # Determine file type based on extension and location
            if suffix in self.native_source_extensions:
                file_type = "source"
            elif suffix in self.build_config_extensions:
                file_type = "config"
            elif suffix in self.resource_extensions:
                file_type = "resource"
            elif suffix in self.archive_extensions:
                file_type = "library"
            else:
                file_type = "other"

            # Determine programming language
            if suffix in {".c", ".h"}:
                language = "c"
            elif suffix in {".cpp", ".cc", ".cxx", ".hpp", ".hxx"}:
                language = "cpp"
            elif suffix in {".s", ".S"}:
                language = "assembly"
            elif suffix in {".ts", ".ets"}:
                language = "arkts"
            elif suffix == ".js":
                language = "javascript"
            elif suffix in {".json", ".json5"}:
                language = "json"
            elif suffix in {".xml"}:
                language = "xml"
            elif suffix in {".yaml", ".yml"}:
                language = "yaml"
            elif suffix == ".txt":
                language = "text"
            elif suffix in {".cmake"}:
                language = "cmake"
            elif suffix == ".mk":
                language = "makefile"
            else:
                language = "unknown"

            return {
                "name": file_path.name,
                "path": str(file_path),
                "relative_path": str(rel_path),
                "module_name": module_name,
                "file_type": file_type,
                "language": language,
                "extension": suffix,
                "size": file_stats.st_size,
                "modified_time": file_stats.st_mtime,
            }
        except (OSError, PermissionError) as e:
            warnings.warn(f"Failed to extract info from {file_path}: {e}")
            return None

    def _create_file_node(self, context: GraphManager, file_info: Dict[str, Any]) -> str:
        """
        Create a file node in the dependency graph.

        Args:
            context: Graph manager instance
            file_info: File information dictionary

        Returns:
            File node label
        """
        # Create normalized file label using project name
        file_label = self._normalize_path(
            f"{self.project_name}/{file_info['module_name']}/{file_info['relative_path']}"
        )

        # Determine node type based on file type and extension
        if file_info["file_type"] == "library":
            # For library files, determine static vs shared based on extension
            if file_info["extension"] in {".a", ".lib"}:
                node_type = "static_library"
            elif file_info["extension"] in {".so", ".dll"}:
                node_type = "shared_library"
            else:
                node_type = "shared_library"  # Default for libraries
        else:
            # All other files are code type
            node_type = "code"
        
        # Create file node
        file_node = self.create_vertex(
            file_label,
            type=node_type,
            name=file_info["name"],
            file_type=file_info["file_type"],
            language=file_info["language"],
            extension=file_info["extension"],
            path=file_info["path"],
            relative_path=file_info["relative_path"],
            module_name=file_info["module_name"],
            size=file_info["size"],
            parser_stage="stage_three",
        )

        context.add_node(file_node)
        return file_label

    def _create_module_file_edge(
        self, context: GraphManager, module_label: str, file_label: str, file_info: Dict[str, Any]
    ):
        """
        Create an edge from module to file.

        Args:
            context: Graph manager instance
            module_label: Module node label
            file_label: File node label
            file_info: File information dictionary
        """
        edge = self.create_edge(
            module_label,
            file_label,
            type="contains",
            relationship="module_file",
            file_type=file_info["file_type"],
            language=file_info["language"],
        )
        context.add_edge(edge)

    def parse(self, project_path: str, context: Optional[GraphManager] = None) -> GraphManager:
        """
        Parse the Hvigor project Native files and add file nodes (Stage Three).

        Args:
            project_path: Path to the Hvigor project root
            context: Existing graph context from previous stages

        Returns:
            Updated graph manager with Native file-level nodes
        """
        if context is None:
            raise ValueError("Stage Three requires existing graph context from previous stages")

        # Stage Three: Native File Mapping
        print("Starting Hvigor project analysis - Stage Three: Native File Mapping")

        # Discover project information
        if not self._discover_project_info(self.args.hvigor_path):
            raise ValueError(f"Failed to discover project info at {self.args.hvigor_path}")

        print(f"✓ Project root: {self.project_root}")

        # Get Native module nodes from existing context
        module_nodes = self._get_native_modules(context)
        print(f"✓ Found {len(module_nodes)} Native modules to process")

        total_files = 0

        # Process each Native module
        for module_info in module_nodes:
            module_id = module_info["id"]
            module_data = module_info["data"]
            module_name = module_data.get("name", "unknown")
            module_path = Path(module_data.get("path", ""))

            print(f"✓ Processing Native module: {module_name}")

            if not module_path.exists():
                warnings.warn(f"Module path does not exist: {module_path}")
                continue

            # Scan files in this Native module
            files = self._scan_module_files(module_path, module_name)
            print(f"  - Found {len(files)} files")

            # Create file nodes and edges
            for file_info in files:
                file_label = self._create_file_node(context, file_info)
                self._create_module_file_edge(context, module_id, file_label, file_info)

            total_files += len(files)

        # Save output to specified directory
        if output := getattr(self.args, "output", None):
            os.makedirs(output, exist_ok=True)
            context.save(output + "/hvigor_native_mapping.json")
            print(f"✓ Native mapping saved to: {output}/hvigor_native_mapping.json")

        print(f"✓ Stage Three completed. Total Native files added: {total_files}")
        print(f"✓ Final graph: {len(list(context.nodes()))} nodes, {len(list(context.edges()))} edges")

        return context