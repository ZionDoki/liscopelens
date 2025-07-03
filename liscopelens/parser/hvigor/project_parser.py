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
Hvigor project parser for dependency graph analysis.
"""

import os
import json
import argparse
import warnings
from pathlib import Path
from typing import Optional, Dict, List, Any

from liscopelens.parser.base import BaseParser
from liscopelens.utils.graph import GraphManager
from liscopelens.utils.structure import Config


class HvigorProjectParser(BaseParser):
    """
    Parser for Hvigor projects to build dependency graphs.
    
    This parser implements stage one of the Hvigor project analysis:
    - Project discovery and validation
    - Module identification and basic information extraction
    - Configuration file parsing
    """

    arg_table = {
        "--hvigor-path": {
            "type": str,
            "help": "Path to the Hvigor project root directory",
            "default": ".",
        },
        "--output": {
            "type": str,
            "help": "Output directory for the generated graph files",
        },
    }

    def __init__(self, args: argparse.Namespace, config: Config):
        """
        Initialize the Hvigor project parser.
        
        Args:
            args: Command line arguments
            config: Parser configuration
        """
        super().__init__(args, config)
        self.project_root = None
        self.modules = {}
        self.project_info = {}

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

    def _read_json5_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """
        Read and parse a JSON5 configuration file.
        
        Args:
            file_path: Path to the JSON5 file
            
        Returns:
            Parsed JSON data or None if file doesn't exist or parsing fails
        """
        if not file_path.exists():
            return None
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Simple JSON5 to JSON conversion
                lines = []
                for line in content.split('\n'):
                    # Remove single-line comments
                    if '//' in line:
                        line = line[:line.index('//')]
                    lines.append(line)
                
                # Join lines and clean up
                content = '\n'.join(lines)
                
                # Remove trailing commas more aggressively
                import re
                # Remove trailing commas before } or ]
                content = re.sub(r',(\s*[}\]])', r'\1', content)
                
                return json.loads(content)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            warnings.warn(f"Failed to parse {file_path}: {e}")
            return None

    def _discover_project_structure(self, project_path: str) -> bool:
        """
        Discover and validate the Hvigor project structure.
        
        Args:
            project_path: Path to the project root
            
        Returns:
            True if valid Hvigor project structure is found
        """
        self.project_root = Path(project_path).resolve()
        
        # Check for essential Hvigor project files - hvigor-config.json5 is the primary indicator
        hvigor_config = self.project_root / "hvigor" / "hvigor-config.json5"
        build_profile = self.project_root / "build-profile.json5"
        oh_package = self.project_root / "oh-package.json5"
        app_scope = self.project_root / "AppScope" / "app.json5"
        
        # Primary check: hvigor-config.json5 must exist for a valid Hvigor project
        if not hvigor_config.exists():
            warnings.warn(f"hvigor/hvigor-config.json5 not found in {self.project_root}")
            return False
        
        # Secondary check: build-profile.json5 should also exist
        if not build_profile.exists():
            warnings.warn(f"build-profile.json5 not found in {self.project_root}")
            return False
            
        # Read project-level configuration files
        self.project_info['hvigor_config'] = self._read_json5_file(hvigor_config)
        self.project_info['build_profile'] = self._read_json5_file(build_profile)
        self.project_info['oh_package'] = self._read_json5_file(oh_package)
        self.project_info['app_config'] = self._read_json5_file(app_scope)
        
        return True

    def _extract_modules_from_build_profile(self) -> List[str]:
        """
        Extract module list from build-profile.json5.
        
        Returns:
            List of module names
        """
        build_profile = self.project_info.get('build_profile')
        modules = []
        
        if build_profile and isinstance(build_profile, dict):
            modules = build_profile.get('modules', [])
        
        if not modules:
            # Fallback: scan for directories with module.json5
            modules = []
            for item in self.project_root.iterdir():
                if item.is_dir() and item.name != "AppScope":
                    module_config = item / "src" / "main" / "module.json5"
                    if module_config.exists():
                        modules.append({"name": item.name, "srcPath": str(item.relative_to(self.project_root))})
        
        return modules

    def _analyze_module(self, module_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a single module and extract its configuration.
        
        Args:
            module_info: Module information from build-profile.json5
            
        Returns:
            Module analysis results
        """
        module_name = module_info.get('name', '')
        module_path = self.project_root / module_info.get('srcPath', module_name)
        
        module_data = {
            'name': module_name,
            'path': module_path,
            'relative_path': module_path.relative_to(self.project_root),
            'is_native': False,
            'dependencies': {},
            'dev_dependencies': {},
            'module_type': 'library',  # default
        }
        
        # Read module configuration files
        oh_package_path = module_path / "oh-package.json5"
        module_config_path = module_path / "src" / "main" / "module.json5"
        build_profile_path = module_path / "build-profile.json5"
        
        # Parse oh-package.json5 for dependencies
        oh_package = self._read_json5_file(oh_package_path)
        if oh_package:
            module_data['dependencies'] = oh_package.get('dependencies', {})
            module_data['dev_dependencies'] = oh_package.get('devDependencies', {})
            module_data['oh_package'] = oh_package
        
        # Parse module.json5 for module type and capabilities
        module_config = self._read_json5_file(module_config_path)
        if module_config:
            module_info_section = module_config.get('module', {})
            module_data['module_type'] = module_info_section.get('type', 'library')
            module_data['module_config'] = module_config
        
        # Check for Native module indicators
        build_profile = self._read_json5_file(build_profile_path)
        if build_profile:
            module_data['build_profile'] = build_profile
            # Check for Native indicators
            build_options = build_profile.get('buildOption', {})
            build_option_set = build_profile.get('buildOptionSet', [])
            
            # Check for externalNativeOptions or nativeLib
            if build_options.get('externalNativeOptions') or any(
                opt.get('externalNativeOptions') or opt.get('nativeLib') 
                for opt in build_option_set
            ):
                module_data['is_native'] = True
        
        # Check for C/C++ source directory
        cpp_dir = module_path / "src" / "main" / "cpp"
        if cpp_dir.exists():
            module_data['is_native'] = True
            module_data['cpp_dir'] = cpp_dir
            
            # Look for CMakeLists.txt
            cmake_file = cpp_dir / "CMakeLists.txt"
            if cmake_file.exists():
                module_data['cmake_file'] = cmake_file
        
        return module_data

    def _create_project_node(self, context: GraphManager) -> str:
        """
        Create the project root node in the dependency graph.
        
        Args:
            context: Graph manager instance
            
        Returns:
            Project node label
        """
        app_config = self.project_info.get('app_config', {})
        app_info = app_config.get('app', {}) if app_config else {}
        
        # Use project directory name as the main identifier
        project_dir_name = self.project_root.name
        project_label = self._normalize_path(project_dir_name)
        
        # Create node with original config fields preserved with prefixes
        project_node = self.create_vertex(
            project_label,
            type="compile",
            name=project_dir_name,
            path=str(self.project_root),
            parser_stage="stage_one"
        )
        
        # Add app config fields with app_ prefix
        if app_info:
            if 'bundleName' in app_info:
                project_node['app_bundle_name'] = app_info['bundleName']
            if 'versionName' in app_info:
                project_node['app_version_name'] = app_info['versionName']
            if 'versionCode' in app_info:
                project_node['app_version_code'] = app_info['versionCode']
        
        context.add_node(project_node)
        return project_label

    def _create_module_node(self, context: GraphManager, module_data: Dict[str, Any], project_label: str) -> str:
        """
        Create a module node in the dependency graph.
        
        Args:
            context: Graph manager instance
            module_data: Module analysis data
            project_label: Parent project node label
            
        Returns:
            Module node label
        """
        module_name = module_data['name']
        module_label = self._normalize_path(f"{self.project_root.name}/{module_name}")
        
        # Determine module type based on whether it's native
        if module_data['is_native']:
            module_type = "shared_library"
        else:
            module_type = "compile"
        
        module_node = self.create_vertex(
            module_label,
            type=module_type,
            name=module_name,
            is_native=module_data['is_native'],
            path=str(module_data['path']),
            relative_path=str(module_data['relative_path']),
            parser_stage="stage_one"
        )
        
        # Add module config fields with module_ prefix
        if 'module_type' in module_data:
            module_node['module_type'] = module_data['module_type']
        
        # Add oh-package config fields with oh_package_ prefix
        if 'oh_package' in module_data:
            oh_package = module_data['oh_package']
            if 'name' in oh_package:
                module_node['oh_package_name'] = oh_package['name']
            if 'version' in oh_package:
                module_node['oh_package_version'] = oh_package['version']
            if 'license' in oh_package:
                module_node['oh_package_license'] = oh_package['license']
        
        # Add module.json5 config fields with module_config_ prefix
        if 'module_config' in module_data:
            module_config = module_data['module_config']
            module_info = module_config.get('module', {})
            if 'type' in module_info:
                module_node['module_config_type'] = module_info['type']
            if 'abilities' in module_info:
                module_node['module_config_abilities'] = module_info['abilities']
        
        context.add_node(module_node)
        
        # Create edge from project to module
        project_to_module_edge = self.create_edge(
            project_label,
            module_label,
            type="contains",
            relationship="project_module"
        )
        context.add_edge(project_to_module_edge)
        
        return module_label

    def _create_dependency_edges(self, context: GraphManager, module_label: str, module_data: Dict[str, Any]):
        """
        Create dependency edges for a module.
        
        Args:
            context: Graph manager instance
            module_label: Source module label
            module_data: Module analysis data
        """
        # Process runtime dependencies
        for dep_name, dep_version in module_data['dependencies'].items():
            if dep_version.startswith('file:'):
                # Local module dependency - resolve relative path
                dep_path = dep_version[5:]  # Remove 'file:' prefix
                if dep_path.startswith('../'):
                    # Relative path like '../ffmpeg' -> 'ffmpeg'
                    target_module_name = dep_path[3:]  # Remove '../'
                else:
                    target_module_name = Path(dep_path).name
                
                target_label = self._normalize_path(f"{self.project_root.name}/{target_module_name}")
                
                dependency_edge = self.create_edge(
                    module_label,
                    target_label,
                    type="dependency",
                    dependency_type="runtime",
                    oh_package_name=dep_name,
                    oh_package_version=dep_version,
                    linkage_type="dynamic" if module_data['is_native'] else "compile"
                )
                context.add_edge(dependency_edge)
            else:
                # External dependency - create external node
                external_label = self._normalize_path(f"external/{dep_name}")
                external_node = self.create_vertex(
                    external_label,
                    type="shared_library",
                    name=dep_name,
                    oh_package_version=dep_version,
                    source="external"
                )
                context.add_node(external_node)
                
                dependency_edge = self.create_edge(
                    module_label,
                    external_label,
                    type="dependency",
                    dependency_type="runtime",
                    oh_package_name=dep_name,
                    oh_package_version=dep_version
                )
                context.add_edge(dependency_edge)
        
        # Process development dependencies
        for dep_name, dep_version in module_data['dev_dependencies'].items():
            if dep_version.startswith('file:'):
                # Local dev dependency
                dep_path = dep_version[5:]  # Remove 'file:' prefix
                if dep_path.startswith('../'):
                    target_module_name = dep_path[3:]  # Remove '../'
                else:
                    target_module_name = Path(dep_path).name
                
                target_label = self._normalize_path(f"{self.project_root.name}/{target_module_name}")
                
                dependency_edge = self.create_edge(
                    module_label,
                    target_label,
                    type="dependency",
                    dependency_type="development",
                    oh_package_name=dep_name,
                    oh_package_version=dep_version,
                    linkage_type="dynamic" if module_data['is_native'] else "compile"
                )
                context.add_edge(dependency_edge)
            else:
                # External dev dependency
                external_label = self._normalize_path(f"external/{dep_name}")
                external_node = self.create_vertex(
                    external_label,
                    type="shared_library",
                    name=dep_name,
                    oh_package_version=dep_version,
                    source="external"
                )
                context.add_node(external_node)
                
                dependency_edge = self.create_edge(
                    module_label,
                    external_label,
                    type="dependency",
                    dependency_type="development",
                    oh_package_name=dep_name,
                    oh_package_version=dep_version
                )
                context.add_edge(dependency_edge)

    def parse(self, project_path: str, context: Optional[GraphManager] = None) -> GraphManager:
        """
        Parse the Hvigor project and build dependency graph (Stage One).
        
        Args:
            project_path: Path to the Hvigor project root
            context: Existing graph context (optional)
            
        Returns:
            Updated graph manager with project structure
        """
        if context is None:
            context = GraphManager()
        
        # Stage One: Project Discovery
        print("Starting Hvigor project analysis - Stage One: Project Discovery")
        
        # Discover project structure
        if not self._discover_project_structure(self.args.hvigor_path):
            raise ValueError(f"Invalid Hvigor project structure at {project_path}")
        
        print(f"✓ Project root discovered: {self.project_root}")
        
        # Extract modules from build-profile.json5
        modules_info = self._extract_modules_from_build_profile()
        print(f"✓ Found {len(modules_info)} modules")
        
        # Create project root node
        project_label = self._create_project_node(context)
        print(f"✓ Created project node: {project_label}")
        
        # Analyze each module
        for module_info in modules_info:
            module_data = self._analyze_module(module_info)
            self.modules[module_data['name']] = module_data
            
            # Create module node
            module_label = self._create_module_node(context, module_data, project_label)
            print(f"✓ Created module node: {module_label} (Native: {module_data['is_native']})")
            
            # Create dependency edges
            self._create_dependency_edges(context, module_label, module_data)
        
        print(f"✓ Stage One completed. Total nodes: {len(list(context.nodes()))}, Total edges: {len(list(context.edges()))}")
        
        # Save output to specified directory
        if output := getattr(self.args, "output", None):
            os.makedirs(output, exist_ok=True)
            context.save(output + "/hvigor_graph.json")
        
        return context
