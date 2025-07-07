"""
Hvigor Parser for Parsing Hvigor Projects"""

from pathlib import Path
from typing import Union, Dict, Set, Any, Optional

from liscopelens.utils.graph import GraphManager
from liscopelens.parser.base import BaseParser

from .entity import Project, Module, CodeFile, HvigorEntity
from .constants import HvigorEdgeType, HvigorVertexType


class HvigorParser(BaseParser):
    """
    Parser for parsing Hvigor projects and building dependency graphs.

    This parser follows a two-phase approach:
    1. Parse file structure and create 'contains' edges
    2. Parse configuration files and create 'deps' edges
    """

    arg_table: Dict[str, Dict[str, Any]] = {
        "--output": {
            "help": "Output file path for the dependency graph",
            "type": str,
            "default": None,
        }
    }

    def __init__(self, args, config):
        super().__init__(args, config)
        self.graph: Optional[GraphManager] = None
        self.project_root: Optional[Path] = None
        self.entity_map: Dict[str, HvigorEntity] = {}

    def parse(self, project_path: Path, context: Optional[GraphManager] = None) -> GraphManager:
        """
        Parse the Hvigor project at the given project path.

        Args:
            project_path (Path): The path of the project to parse
            context (Optional[GraphManager]): The context (GraphManager) of the project

        Returns:
            GraphManager: The graph representation of the Hvigor project or module.

        Raises:
            ValueError: If the project path is not a valid Hvigor project or module.
        """
        if context is None:
            context = GraphManager()

        self.graph = context
        self.project_root = project_path.resolve()  # Store project root for src_path calculation

        if Project.is_project(project_path):
            tgt_project = Project.from_path(project_path)
            self.handle_project(tgt_project)
            self.build_graph(tgt_project)
        elif Module.is_module(project_path):
            # Check for multiple modules in the directory
            modules = Module.find_modules_in_directory(project_path)
            if modules:
                for module in modules:
                    self.handle_module(module)
                self.build_graph(modules[0])  # Build graph for first module
            else:
                tgt_module = Module.from_path(project_path)
                self.handle_module(tgt_module)
                self.build_graph(tgt_module)
        else:
            raise ValueError(f"Invalid Hvigor project or module path: {project_path}")

        # Export graph if output path is specified
        if hasattr(self.args, "output") and self.args.output:
            output_format = getattr(self.args, "format", "json")
            self.export_graph(self.args.output, output_format)

        return self.graph

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

    def build_graph(self, root_entity: Union[Project, Module]):
        """
        Build the graph representation of the Hvigor project or module.

        Phase 1: Add all entities and 'contains' edges
        Phase 2: Resolve dependencies and add 'deps' edges

        Args:
            root_entity (Union[Project, Module]): The root Hvigor project or module.
        """
        # Phase 1: Build contains relationships from file structure
        self._build_contains_graph(root_entity)

        # Phase 2: Build dependency relationships from configuration
        self._build_deps_graph(root_entity)

    def _build_contains_graph(self, entity: HvigorEntity):
        """
        Recursively build the contains graph from entity structure.

        Args:
            entity (HvigorEntity): Entity to process
        """
        # Add the entity as a vertex using base parser method
        vertex_type = self._get_vertex_type(entity)

        # Calculate src_path relative to project root
        src_path = self._calculate_src_path(entity.src_path)

        # Use src_path as unique label to avoid ID conflicts for files with same name
        unique_label = src_path if hasattr(entity, 'src_path') and entity.src_path.is_file() else entity.name

        vertex = self.create_vertex(
            label=unique_label,
            type=vertex_type,
            path=str(entity.src_path),
            src_path=src_path,
            is_native=getattr(entity, "is_native", False),
            # Store original name for display purposes
            file_name=entity.name,
        )
        self.graph.add_node(vertex)

        # Add contains edges to dependencies
        for edge in entity.deps(HvigorEdgeType.CONTAINS):
            self._build_contains_graph(edge.dst)

            # Calculate unique labels for edge endpoints
            src_unique_label = src_path if hasattr(entity, 'src_path') and entity.src_path.is_file() else entity.name
            dst_src_path = self._calculate_src_path(edge.dst.src_path)
            dst_unique_label = dst_src_path if hasattr(edge.dst, 'src_path') and edge.dst.src_path.is_file() else edge.dst.name

            # Create graph edge using unique labels
            graph_edge = self.create_edge(u=src_unique_label, v=dst_unique_label, type=edge.edge_type.value)
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
                target_entity = self._find_local_dependency(dep)
                if target_entity:
                    # Calculate unique labels for dependency edge
                    module_src_path = self._calculate_src_path(module.src_path)
                    module_unique_label = module_src_path if hasattr(module, 'src_path') and module.src_path.is_file() else module.name
                    target_src_path = self._calculate_src_path(target_entity.src_path)
                    target_unique_label = target_src_path if hasattr(target_entity, 'src_path') and target_entity.src_path.is_file() else target_entity.name
                    
                    # Add dependency edge using base parser method
                    dep_edge = self.create_edge(
                        u=module_unique_label, v=target_unique_label, type=HvigorEdgeType.DEPENDS.value, dependency_type="local"
                    )
                    self.graph.add_edge(dep_edge)
            else:
                # External ohpm dependency
                # Create a virtual node for external dependency using base parser method
                ext_vertex = self.create_vertex(
                    label=dep.name,
                    type=HvigorVertexType.EXTERNAL_PACKAGE.value,
                    version=dep.version,
                    is_external=True,
                    src_path=f"external/{dep.name}",  # Virtual src_path for external dependencies
                )
                self.graph.add_node(ext_vertex)

                # Calculate unique label for module
                module_src_path = self._calculate_src_path(module.src_path)
                module_unique_label = module_src_path if hasattr(module, 'src_path') and module.src_path.is_file() else module.name
                
                dep_edge = self.create_edge(
                    u=module_unique_label, v=dep.name, type=HvigorEdgeType.DEPENDS.value, dependency_type="external"
                )
                self.graph.add_edge(dep_edge)

    def _find_local_dependency(self, dependency):
        """
        Find the target entity for a local file dependency.

        Args:
            dependency: Dependency object

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
            return HvigorVertexType.PROJECT.value

        if isinstance(entity, Module):
            if entity.is_native:
                return HvigorVertexType.NATIVE_MODULE.value
            # Use the module type from ModuleProfile.ModuleConfig.type field
            module_type = entity.get_module_type()
            if module_type == "entry":
                return HvigorVertexType.MODULE_ENTRY.value
            elif module_type == "feature":
                return HvigorVertexType.MODULE_FEATURE.value
            elif module_type == "har":
                return HvigorVertexType.MODULE_HAR.value
            elif module_type == "shared":
                return HvigorVertexType.MODULE_SHARE.value
            else:
                return HvigorVertexType.MODULE.value

        if isinstance(entity, CodeFile):
            if entity.is_native_code:
                return HvigorVertexType.NATIVE_CODE.value
            if entity.is_arkts_code:
                return HvigorVertexType.ARKTS_CODE.value
            if entity.is_resource:
                return HvigorVertexType.RESOURCE.value
            return HvigorVertexType.FILE.value

        return HvigorVertexType.UNKNOWN.value

    def get_modules_not_in_build(self, project: Project) -> Set[Module]:
        """
        Get modules that are not included in the build configuration.

        Args:
            project (Project): Project to analyze

        Returns:
            Set[Module]: Modules not participating in build
        """
        # Use model if available, otherwise fall back to dict
        if project.build_profile_model and project.build_profile_model.modules:
            configured_modules = {module.name for module in project.build_profile_model.modules}
        elif project.build_profile:
            configured_modules = set(project.module_configs.keys())
        else:
            # No build profile means all modules participate
            return set()

        all_modules = {module.name for module in project.discovered_modules}
        excluded_modules = all_modules - configured_modules
        return {module for module in project.discovered_modules if module.name in excluded_modules}

    def export_graph(self, output_path: Union[str, Path], save_format: str = "json"):
        """
        Export the graph to a file.

        Args:
            output_path (Union[str, Path]): Output file path
            save_format (str): Export format ("json", "gml", "graphml")
        """
        self.graph.save(str(Path(output_path) / "hvigor_graph.json"), save_format=save_format)

    def _calculate_src_path(self, entity_path: Path) -> str:
        """
        Calculate the src_path attribute for an entity relative to project root.

        Args:
            entity_path (Path): The absolute path of the entity

        Returns:
            str: The relative path from project root in POSIX format
        """
        try:
            entity_path_resolved = Path(entity_path).resolve()
            relative_path = entity_path_resolved.relative_to(self.project_root)
            return relative_path.as_posix()
        except ValueError:
            # If entity is not under project root, return the path as-is
            return str(entity_path)
