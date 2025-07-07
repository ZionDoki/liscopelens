"""
Hvigor Analyzer Models
"""

import warnings
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Optional, Set, Iterable, List

import json5

from .constants import HvigorProfile, HvigorEdgeType, TS_EXTS, NATIVE_EXTS


def read_json5(json5_path: Path) -> Dict:
    """
    Read a JSON5 file and return its content as a dictionary.
    """
    try:
        with open(json5_path, "r", encoding="utf-8") as f:
            return json5.load(f)
    except (ValueError, FileNotFoundError):
        return {}


@dataclass
class Dependency:
    """Represents a dependency declaration from oh-package.json5

    Attributes:
        name (str): Package name
        version (str): Version specification
        is_local (bool): Whether this is a local file: dependency
        local_path (Optional[Path]): Local path if it's a file: dependency
    """

    name: str
    version: str
    is_local: bool = False
    local_path: Optional[Path] = None


@dataclass
class HvigorEdge:
    """Represents an edge in the Hvigor graph.

    Attributes:
        src (str): Source entity name.
        dst (str): Destination entity name.
        edge_type (HvigorEdgeType): Type of the edge.
    """

    src: "HvigorEntity"
    dst: "HvigorEntity"
    edge_type: HvigorEdgeType = HvigorEdgeType.CONTAINS

    def __hash__(self):
        return hash((self.src.name, self.dst.name, self.edge_type))


@dataclass
class HvigorEntity:
    """
    Base class for Hvigor entities.
    """

    root_path: Path
    parent: Set["HvigorEntity"] = field(default_factory=set)
    name: str = field(init=False)

    _deps: Set[HvigorEdge] = field(default_factory=set)

    def add_deps(self, dst: "HvigorEntity", edge_type: HvigorEdgeType) -> HvigorEdge:
        """
        Add a dependency edge from this entity to another entity.

        Args:
            dst (HvigorEntity): The destination entity.
            edge_type (HvigorEdgeType): The type of the edge.

        Returns:
            HvigorEdge: The created edge.
        """
        edge = HvigorEdge(src=self, dst=dst, edge_type=edge_type)
        self._deps.add(edge)
        return edge

    def deps(self, *edge_type: HvigorEdgeType) -> Set[HvigorEdge]:
        """
        Get the set of dependency edges for this entity.

        Returns:
            Set[HvigorEdge]: A set of dependency edges.
        """
        if not edge_type:
            return self._deps
        return {edge for edge in self._deps if edge.edge_type in edge_type}

    def _safe_rglob_files(self, base_path: Path) -> Iterable[Path]:
        base_path = base_path.resolve()
        for fp in base_path.rglob("*"):
            if not fp.is_file() or fp.is_symlink():
                continue
            try:
                fp.resolve().relative_to(base_path)
            except ValueError:
                continue
            yield fp

    @classmethod
    def from_path(cls, root_path: Path) -> "HvigorEntity":
        """
        Factory method to create an HvigorEntity from a given path.
        This method should be overridden by subclasses to provide specific behavior.

        Args:
            path (Path): The path to the entity.
            parents (Set[HvigorEntity]): The parent entities of this entity.

        Returns:
            HvigorEntity: An instance of the subclass.
        """
        raise NotImplementedError("Subclasses must implement this method.")


@dataclass
class CodeFile(HvigorEntity):
    """
    Represents a code file in a Hvigor module.

    Attributes:
        - is_arkts: Whether this file is an ArkTS code file
        - is_native: Whether this file is a native code file
    """

    is_native_code: bool = False
    is_arkts_code: bool = False
    is_resource: bool = False

    def __post_init__(self):
        """
        Set the name of the code file based on its path.
        """
        self.name = self.root_path.name
        self.is_arkts_code = self.root_path.suffix in TS_EXTS
        self.is_native_code = self.root_path.suffix in NATIVE_EXTS
        self.is_resource = "resource" in self.root_path.parts

    @classmethod
    def from_path(cls, root_path: Path) -> "CodeFile":
        """
        Factory method to create a CodeFile from a given path.

        Args:
            path (Path): The path to the code file.
            parents (Set[HvigorEntity]): The parent entities of this code file.

        Returns:
            CodeFile: An instance of CodeFile.
        """
        if not root_path.is_file():
            raise ValueError(f"Root path {root_path} is not a file.")

        cf = cls(root_path=root_path)
        return cf


@dataclass
class Module(HvigorEntity):
    """
    Represents a Hvigor module.

    Attributes:
        name: Module name
        root_path: Module root directory path
    """

    targets: Dict[str, str] = field(default_factory=dict)

    pkg_profile: Optional[Dict] = field(default_factory=dict)
    build_profile: Optional[Dict] = field(default_factory=dict)
    module_profile: Optional[Dict] = field(default_factory=dict)

    is_native: bool = False
    dependencies: List[Dependency] = field(default_factory=list)

    targets2path: Dict[str, Set[Path]] = field(default_factory=dict)

    def __post_init__(self):
        self.name = self.root_path.name
        self.is_native = self._is_native()
        self._parse_dependencies()

        targets = self.build_profile.get("targets", [])
        for target in targets:
            source = target.get("source", {})
            abilities = target.get("abilities", [])
            source_roots = source.get("sourceRoots", [])
            pages = source.get("pages", [])

            self.targets2path[target["name"]] = set(abilities + source_roots + pages)

    def _is_native(self) -> bool:
        """
        Check if the module is a native module based on its build profile.
        """
        cpp_flag = (self.root_path / "src/main/cpp").exists()
        profile_flag = self.build_profile.get("buildOption", {}).get("externalNativeOptions", {}) != {}

        if cpp_flag ^ profile_flag:
            warnings.warn(f"Detect native module but not confident on {self.root_path.as_posix()}.")

        return cpp_flag or profile_flag

    def _parse_dependencies(self):
        """Parse dependencies from oh-package.json5"""
        deps = self.pkg_profile.get("dependencies", {})
        for name, version in deps.items():
            is_local = version.startswith("file:")
            local_path = None
            if is_local:
                # Remove 'file:' prefix and resolve relative path
                relative_path = version[5:]  # Remove 'file:' prefix
                local_path = (self.root_path / relative_path).resolve()

            self.dependencies.append(Dependency(name=name, version=version, is_local=is_local, local_path=local_path))

    @classmethod
    def from_path(cls, root_path: Path, module_path: Optional[Path] = None) -> "Module":
        """
        Factory method to create a Module from a given path.

        Args:
            root_path (Path): The root path to the module directory.
            module_path (Path, optional): Specific path to module.json5, if different from src/main/module.json5

        Returns:
            Module: An instance of Module.
        """
        if not root_path.is_dir():
            raise ValueError(f"Path {root_path} is not a directory.")

        # Determine module.json5 location
        if module_path is None:
            module_path = root_path / "src/main/module.json5"

        module_profile = read_json5(module_path) if module_path.exists() else {}

        hm = cls(
            root_path=root_path,
            pkg_profile=read_json5(root_path / HvigorProfile.PACKAGE_PROFILE.value),
            build_profile=read_json5(root_path / HvigorProfile.BUILD_PROFILE.value),
            module_profile=module_profile,
        )

        # Set module name from module.json5 if available
        if module_profile.get("module", {}).get("name"):
            hm.name = module_profile["module"]["name"]

        # Add all files as contains edges
        for fp in hm._safe_rglob_files(root_path):
            cf = CodeFile.from_path(fp)
            hm.add_deps(cf, HvigorEdgeType.CONTAINS)

        return hm

    @classmethod
    def is_module(cls, root_path: Path) -> bool:
        """
        Check if the given path is a Hvigor module.

        Args:
            root_path (Path): The path to check.

        Returns:
            bool: True if the path is a Hvigor module, False otherwise.
        """
        pkg_profile = root_path / HvigorProfile.PACKAGE_PROFILE.value
        hvigor_config = root_path / HvigorProfile.HVIGOR_PROFILE.value
        return pkg_profile.is_file() and not hvigor_config.exists()

    @classmethod
    def find_modules_in_directory(cls, root_path: Path) -> List["Module"]:
        """
        Find all modules in a directory, supporting multiple modules per directory.

        Args:
            root_path (Path): Directory to search for modules

        Returns:
            List[Module]: List of discovered modules
        """
        modules = []

        # Look for src/*/module.json5 pattern
        src_dir = root_path / "src"
        if src_dir.exists():
            for module_dir in src_dir.iterdir():
                if module_dir.is_dir():
                    module_json = module_dir / "module.json5"
                    if module_json.exists():
                        module = cls.from_path(root_path, module_json)
                        modules.append(module)

        # If no modules found but has oh-package.json5, treat as single module
        if not modules and cls.is_module(root_path):
            modules.append(cls.from_path(root_path))

        return modules


@dataclass
class Project(HvigorEntity):
    """
    Represents a complete Hvigor project.

    Attributes:
        root_path (Path): The root path of the Hvigor project.
        products (Dict[str, Product]): A dictionary mapping product names to Product objects.
        build_profile (Optional[Dict]): The build profile of the project, if available.
        app_profile (Optional[Dict]): The application profile of the project, if available.
        pkg_profile (Optional[Dict]): The package profile of the project, if available.
        hvigor_profile (Optional[Dict]): The Hvigor profile of the project, if available.
    """

    build_profile: Optional[Dict] = field(default_factory=dict)
    app_profile: Optional[Dict] = field(default_factory=dict)
    pkg_profile: Optional[Dict] = field(default_factory=dict)
    hvigor_profile: Optional[Dict] = field(default_factory=dict)

    products2targets: Dict[str, Set[str]] = field(default_factory=dict)
    module_configs: Dict[str, Dict] = field(default_factory=dict)  # module name -> config from build-profile
    discovered_modules: List[Module] = field(default_factory=list)

    def __post_init__(self):
        """
        Set the name of the project based on its root path.
        """
        self.name = self.root_path.name

        # Parse products and targets from build profile
        products = self.build_profile.get("app", {}).get("products", [])
        for prod in products:
            self.products2targets[prod["name"]] = set(prod.get("targets", []))

        # Parse module configurations
        modules_config = self.build_profile.get("modules", [])
        for module_config in modules_config:
            module_name = module_config["name"]
            self.module_configs[module_name] = module_config

    @classmethod
    def is_project(cls, root_path: Path) -> bool:
        """
        Check if the given path is a Hvigor project.

        Args:
            root_path (Path): The path to check.

        Returns:
            bool: True if the path is a Hvigor project, False otherwise.
        """
        hvigor_config = root_path / HvigorProfile.HVIGOR_PROFILE.value
        return hvigor_config.is_file()

    @classmethod
    def from_path(cls, root_path: Path) -> "Project":
        """
        Factory method to create a Project from a given root_path path.

        Args:
            root_path (Path): The root_path path of the Hvigor project.
            parents (Set[HvigorEntity]): The parent entities of this project.

        Returns:
            Project: An instance of Project.
        """
        if not root_path.is_dir():
            raise ValueError(f"root_path path {root_path} is not a directory.")

        tgt_project = cls(
            root_path=root_path,
            hvigor_profile=read_json5(root_path / HvigorProfile.HVIGOR_PROFILE.value),
            build_profile=read_json5(root_path / HvigorProfile.BUILD_PROFILE.value),
            app_profile=read_json5(root_path / HvigorProfile.APP_PROFILE.value),
            pkg_profile=read_json5(root_path / HvigorProfile.PACKAGE_PROFILE.value),
        )

        # Discover modules
        tgt_project._discover_modules()

        return tgt_project

    def _discover_modules(self):
        """Discover all modules in the project"""
        # If build-profile.json5 exists, use it to guide module discovery
        if self.build_profile:
            modules_config = self.build_profile.get("modules", [])
            for module_config in modules_config:
                src_path = module_config.get("srcPath", f"./{module_config['name']}")
                module_dir = self.root_path / src_path.lstrip("./")

                if module_dir.exists():
                    modules = Module.find_modules_in_directory(module_dir)
                    for module in modules:
                        self.discovered_modules.append(module)
                        self.add_deps(module, HvigorEdgeType.CONTAINS)
        else:
            # If no build profile, scan all subdirectories
            for dp in self.root_path.iterdir():
                if dp.is_dir() and dp.name not in ["hvigor", "AppScope"]:
                    modules = Module.find_modules_in_directory(dp)
                    for module in modules:
                        self.discovered_modules.append(module)
                        self.add_deps(module, HvigorEdgeType.CONTAINS)

    def get_module_targets_for_product(self, product_name: str) -> Dict[str, Set[str]]:
        """
        Get mapping of module name to targets for a specific product.

        Args:
            product_name (str): Name of the product

        Returns:
            Dict[str, Set[str]]: Mapping of module name to set of target names
        """
        result = {}

        for module_name, module_config in self.module_configs.items():
            targets = module_config.get("targets", [])
            module_targets = set()

            for target in targets:
                apply_to_products = target.get("applyToProducts", [])
                # If no applyToProducts specified, applies to all products
                if not apply_to_products or product_name in apply_to_products:
                    module_targets.add(target["name"])

            if module_targets:
                result[module_name] = module_targets

        return result


if __name__ == "__main__":

    testdir = Path("D:\\MyProject\\testcase")
    for dp in testdir.iterdir():
        if dp.is_dir() and Module.is_module(dp):
            module = Module.from_path(dp)
            print(module.name, module.is_native, module.targets2path)
        elif dp.is_dir() and Project.is_project(dp):
            project = Project.from_path(dp)
            print(project.name, project.products2targets)
