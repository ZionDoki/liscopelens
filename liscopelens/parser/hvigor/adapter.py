"""
Hvigor Adapter for Parsing Hvigor Projects"""

from pathlib import Path
from typing import Union, Dict, Set

from liscopelens.utils.graph import GraphManager, Vertex, Edge, Triple
from .models import Project, Module, CodeFile, HvigorEntity, HvigorEdge
from .constants import HvigorEdgeType


class HvigorAdapter:
    """
    Adapter for parsing Hvigor projects and building dependency graphs.

    This adapter follows a two-phase approach:
    1. Parse file structure and create 'contains' edges
    2. Parse configuration files and create 'deps' edges
    """

    def __init__(self, root_path: Union[str, Path]):
        self.root_path = Path(root_path)
        self.graph = GraphManager()
        self.entity_map: Dict[str, HvigorEntity] = {}  # name -> entity mapping

    def parse(self) -> GraphManager:
        """
        Parse the Hvigor project at the given root path.

        Returns:
            GraphManager: The graph representation of the Hvigor project or module.

        Raises:
            ValueError: If the root path is not a valid Hvigor project or module.
        """
        if Project.is_project(self.root_path):
            tgt_project = Project.from_path(self.root_path)
            self.handle_project(tgt_project)
            return self.build_graph(tgt_project)
        elif Module.is_module(self.root_path):
            # Check for multiple modules in the directory
            modules = Module.find_modules_in_directory(self.root_path)
            if modules:
                for module in modules:
                    self.handle_module(module)
                return self.build_graph(modules[0])  # Return graph for first module
            else:
                tgt_module = Module.from_path(self.root_path)
                self.handle_module(tgt_module)
                return self.build_graph(tgt_module)
        else:
            raise ValueError(f"Invalid Hvigor project or module path: {self.root_path}")

    def handle_project(self, project: Project) -> Project:
        """
        Handle the parsed Hvigor project.

        Args:
            project (Project): The parsed Hvigor project.

        Returns:
            Project: The processed Hvigor project.
        """
        self.entity_map[project.name] = project

        # Handle all discovered modules
        for module in project.discovered_modules:
            self.handle_module(module)

        return project

    def handle_module(self, module: Module) -> Module:
        """
        Handle the parsed Hvigor module.

        Args:
            module (Module): The parsed Hvigor module.

        Returns:
            Module: The processed Hvigor module.
        """
        self.entity_map[module.name] = module
        return module

    def build_graph(self, root_entity: Union[Project, Module]) -> GraphManager:
        """
        Build the graph representation of the Hvigor project or module.

        Phase 1: Add all entities and 'contains' edges
        Phase 2: Resolve dependencies and add 'deps' edges

        Args:
            root_entity (Union[Project, Module]): The root Hvigor project or module.

        Returns:
            GraphManager: The graph representation of the Hvigor project or module.
        """
        # Phase 1: Build contains relationships from file structure
        self._build_contains_graph(root_entity)

        # Phase 2: Build dependency relationships from configuration
        self._build_deps_graph(root_entity)

        return self.graph

    def _build_contains_graph(self, entity: HvigorEntity):
        """
        Recursively build the contains graph from entity structure.

        Args:
            entity (HvigorEntity): Entity to process
        """
        # Add the entity as a vertex
        vertex_type = self._get_vertex_type(entity)
        vertex = Vertex(
            label=entity.name,
            type=vertex_type,
            path=str(entity.root_path),
            is_native=getattr(entity, "is_native", False),
        )
        self.graph.add_node(vertex)

        # Add contains edges to dependencies
        for edge in entity.deps(HvigorEdgeType.CONTAINS):
            self._build_contains_graph(edge.dst)

            # Create graph edge
            graph_edge = Edge(u=entity.name, v=edge.dst.name, type=edge.edge_type.value)
            self.graph.add_edge(graph_edge)

    def _build_deps_graph(self, root_entity: Union[Project, Module]):
        """
        Build dependency relationships based on oh-package.json5 and build profiles.

        Args:
            root_entity (Union[Project, Module]): Root entity to start dependency resolution
        """
        if isinstance(root_entity, Project):
            # Handle project-level dependencies
            self._resolve_project_dependencies(root_entity)
        elif isinstance(root_entity, Module):
            # Handle module-level dependencies
            self._resolve_module_dependencies(root_entity)

    def _resolve_project_dependencies(self, project: Project):
        """
        Resolve dependencies for a project and its modules.

        Args:
            project (Project): Project to resolve dependencies for
        """
        # Resolve dependencies for each module in the project
        for module in project.discovered_modules:
            self._resolve_module_dependencies(module)

    def _resolve_module_dependencies(self, module: Module):
        """
        Resolve dependencies for a specific module.

        Args:
            module (Module): Module to resolve dependencies for
        """
        for dep in module.dependencies:
            if dep.is_local:
                # Local file dependency - try to find the target module
                target_entity = self._find_local_dependency(dep, module)
                if target_entity:
                    # Add dependency edge
                    dep_edge = Edge(
                        u=module.name, v=target_entity.name, type=HvigorEdgeType.DEPENDS.value, dependency_type="local"
                    )
                    self.graph.add_edge(dep_edge)
            else:
                # External ohpm dependency
                # Create a virtual node for external dependency
                ext_vertex = Vertex(label=dep.name, type="external_package", version=dep.version, is_external=True)
                self.graph.add_node(ext_vertex)

                dep_edge = Edge(
                    u=module.name, v=dep.name, type=HvigorEdgeType.DEPENDS.value, dependency_type="external"
                )
                self.graph.add_edge(dep_edge)

    def _find_local_dependency(self, dependency, source_module: Module):
        """
        Find the target entity for a local file dependency.

        Args:
            dependency: Dependency object
            source_module (Module): Module that declares the dependency

        Returns:
            HvigorEntity: Target entity if found, None otherwise
        """
        if not dependency.local_path or not dependency.local_path.exists():
            return None

        # Check if it's a module directory
        if Module.is_module(dependency.local_path):
            modules = Module.find_modules_in_directory(dependency.local_path)
            if modules:
                target_module = modules[0]  # Take first module
                if target_module.name not in self.entity_map:
                    self.handle_module(target_module)
                    self._build_contains_graph(target_module)
                return self.entity_map.get(target_module.name)

        return None

    def _get_vertex_type(self, entity: HvigorEntity) -> str:
        """
        Determine the vertex type for an entity.

        Args:
            entity (HvigorEntity): Entity to get type for

        Returns:
            str: Vertex type string
        """
        if isinstance(entity, Project):
            return "project"
        elif isinstance(entity, Module):
            if entity.is_native:
                return "native_module"
            else:
                module_type = entity.module_profile.get("module", {}).get("type", "unknown")
                return f"module_{module_type}"
        elif isinstance(entity, CodeFile):
            if entity.is_native_code:
                return "native_code"
            elif entity.is_arkts_code:
                return "arkts_code"
            elif entity.is_resource:
                return "resource"
            else:
                return "file"
        else:
            return "unknown"

    def get_modules_not_in_build(self, project: Project) -> Set[Module]:
        """
        Get modules that are not included in the build configuration.

        Args:
            project (Project): Project to analyze

        Returns:
            Set[Module]: Modules not participating in build
        """
        if not project.build_profile:
            # No build profile means all modules participate
            return set()

        configured_modules = set(project.module_configs.keys())
        all_modules = {module.name for module in project.discovered_modules}

        excluded_modules = all_modules - configured_modules
        return {module for module in project.discovered_modules if module.name in excluded_modules}

    def export_graph(self, output_path: Union[str, Path], format: str = "json"):
        """
        Export the graph to a file.

        Args:
            output_path (Union[str, Path]): Output file path
            format (str): Export format ("json", "gml", "graphml")
        """
        self.graph.save(str(output_path), save_format=format)
