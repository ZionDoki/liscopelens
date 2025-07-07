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

import os
import re
import json
import argparse
import fnmatch
import platform
import subprocess
import zipfile
import tarfile
from pathlib import Path

from typing import Optional
from collections import defaultdict

import requests
import platformdirs
from rich.progress import track

from liscopelens.checker import Checker
from liscopelens.utils.graph import GraphManager
from liscopelens.utils.structure import DualLicense, SPDXParser, Config


from liscopelens.parser.base import BaseParser
from liscopelens.parser.base import BaseParserEntry


class ScancodeParser(BaseParser):
    """Parser for Scancode output files."""

    arg_table = {
        "--scancode-file": {
            "type": str,
            "help": "The path of the scancode's output in json format file",
            "group": "scancode",
        },
        "--scancode-dir": {
            "type": str,
            "help": "The path of the directory that contain json files",
            "group": "scancode",
        },
        "--shadow-license": {
            "type": str,
            "help": "The file path which storage (node-license) pair. Shadow licenses to certain nodes in advance",
            "default": None,
        },
        "--rm-ref-lang": {
            "action": "store_true",
            "help": "Automatically remove scancode ref prefix and language suffix from spdx ids",
            "default": False,
        },
        "--scancode-ver": {
            "type": str,
            "help": "Specify scancode version to use",
            "default": "32.4.0",
            "group": "scancode",
        },
        "--python-ver": {
            "type": str,
            "help": "Specify python version for scancode (e.g., 3.13, 3.12)",
            "default": "3.13",
            "group": "scancode",
        },
        "--scancode-scan": {
            "type": str,
            "help": "Execute scancode scan on the specified target path",
            "group": "scancode",
        },
        "--scancode-process": {
            "type": int,
            "help": "Number of processes to use for scancode scanning",
            "default": 1,
            "group": "scancode",
        },
        "--output": {
            "type": str,
            "help": "The directory to save scancode's output json file",
            "group": "scancode",
        },
    }

    def __init__(self, args: argparse.Namespace, config: Config):
        super().__init__(args, config)
        self.checker = Checker()
        self.spdx_parser = SPDXParser()
        self.count = set()

        # Normalize python version (remove patch version)
        if hasattr(args, "python_ver") and args.python_ver:
            parts = args.python_ver.split(".")
            if len(parts) >= 2:
                args.python_ver = f"{parts[0]}.{parts[1]}"

    def _get_cache_dir(self) -> Path:
        """
        Get the cache directory for scancode installations.

        Returns:
            Path to the cache directory
        """
        return Path(platformdirs.user_cache_dir("liscopelens")) / "scancode"

    def _get_platform_info(self) -> tuple[str, str]:
        """
        Get platform and architecture information for scancode download.

        Returns:
            Tuple of (platform, architecture) strings
        """
        system = platform.system().lower()
        machine = platform.machine().lower()

        # Map platform names
        if system == "windows":
            platform_name = "windows"
        elif system == "darwin":
            platform_name = "macos"
        elif system == "linux":
            platform_name = "linux"
        else:
            raise ValueError(f"Unsupported platform: {system}")

        # Map architecture names
        if machine in ["x86_64", "amd64"]:
            arch = "x86_64"
        elif machine in ["aarch64", "arm64"]:
            arch = "arm64"
        else:
            raise ValueError(f"Unsupported architecture: {machine}")

        return platform_name, arch

    def _build_download_url(self, scancode_ver: str, python_ver: str) -> str:
        """
        Build the download URL for scancode based on version and platform.

        Args:
            scancode_ver: Scancode version (e.g., "32.4.0")
            python_ver: Python version (e.g., "3.13")

        Returns:
            Download URL string
        """
        platform_name, _ = self._get_platform_info()

        # Build filename based on platform (no architecture in filename)
        if platform_name == "windows":
            filename = f"scancode-toolkit-v{scancode_ver}_py{python_ver}-{platform_name}.zip"
        else:
            # For Linux and macOS, use the same format
            filename = f"scancode-toolkit-v{scancode_ver}_py{python_ver}-{platform_name}.tar.xz"

        base_url = "https://github.com/aboutcode-org/scancode-toolkit/releases/download"
        return f"{base_url}/v{scancode_ver}/{filename}"

    def _download_scancode(self, url: str, target_path: Path) -> bool:
        """
        Download scancode from the given URL with progress bar.

        Args:
            url: Download URL
            target_path: Target file path to save the download

        Returns:
            True if download successful, False otherwise
        """
        try:
            response = requests.get(url, stream=True, timeout=45)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))

            print(f"Downloading scancode... Total size: {total_size} bytes")
            downloaded = 0

            with open(target_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            print(f"\rProgress: {percent:.1f}% ({downloaded}/{total_size} bytes)", end="", flush=True)

            print(f"\n✓ Download completed: {target_path}")
            return True

        except requests.RequestException as e:
            print(f"✗ Download failed: {e}")
            return False

    def _extract_scancode(self, archive_path: Path, extract_dir: Path) -> bool:
        """
        Extract scancode archive to the specified directory.

        Args:
            archive_path: Path to the downloaded archive
            extract_dir: Directory to extract to

        Returns:
            True if extraction successful, False otherwise
        """
        try:
            extract_dir.mkdir(parents=True, exist_ok=True)

            if archive_path.suffix == ".zip":
                with zipfile.ZipFile(archive_path, "r") as zip_ref:
                    zip_ref.extractall(extract_dir)
            elif archive_path.suffix in [".tar", ".xz"] or archive_path.name.endswith(".tar.xz"):
                with tarfile.open(archive_path, "r:xz") as tar_ref:
                    tar_ref.extractall(extract_dir)
            else:
                raise ValueError(f"Unsupported archive format: {archive_path}")

            print(f"✓ Extraction completed: {extract_dir}")
            return True

        except Exception as e:
            print(f"✗ Extraction failed: {e}")
            return False

    def _initialize_scancode(self, exe_path: Path, init_flag_file: Path) -> bool:
        """
        Initialize scancode by running it once in its root directory.
        This is required for first-time setup after download.

        Args:
            exe_path: Path to the scancode executable
            init_flag_file: Path to the initialization flag file

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            scancode_root = exe_path.parent
            print("Initializing scancode for first use...")
            print(f"Scancode root directory: {scancode_root}")

            # Run scancode --help to trigger initialization
            init_cmd = [str(exe_path.resolve()), "--help"]

            print(f"Running initialization: {' '.join(init_cmd)}")

            # Run initialization from scancode root directory
            process = subprocess.Popen(
                init_cmd,
                cwd=str(scancode_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            # Stream initialization output
            print("Scancode initialization output:")
            while True:
                output = process.stdout.readline()
                if output == "" and process.poll() is not None:
                    break
                if output:
                    line = output.rstrip("\n\r")
                    if line:
                        print(f"  {line}")

            return_code = process.poll()

            if return_code == 0:
                # Create initialization flag file
                init_flag_file.touch()
                print("✓ Scancode initialization completed")
                return True
            else:
                print(f"✗ Scancode initialization failed with return code {return_code}")
                return False

        except Exception as e:
            print(f"✗ Scancode initialization failed: {e}")
            return False

    def _get_scancode_executable(self, scancode_ver: str, python_ver: str) -> Path:
        """
        Get the path to the scancode executable, downloading if necessary.

        Args:
            scancode_ver: Scancode version
            python_ver: Python version

        Returns:
            Path to the scancode executable

        Raises:
            FileNotFoundError: If scancode cannot be found or downloaded
        """
        cache_dir = self._get_cache_dir()
        platform_name, _ = self._get_platform_info()
        version_dir = cache_dir / f"scancode-{scancode_ver}-py{python_ver}-{platform_name}"
        init_flag_file = version_dir / ".scancode_initialized"

        # Check if version_dir exists and find the actual extracted directory
        if version_dir.exists():
            # Look for scancode executable in version_dir and its subdirectories
            for root, _, _ in os.walk(version_dir):
                root_path = Path(root)
                for exe_name in ["scancode", "scancode.exe", "scancode.bat"]:
                    exe_path = root_path / exe_name
                    if exe_path.exists() and exe_path.is_file():
                        # Check if initialization is needed
                        if not init_flag_file.exists():
                            self._initialize_scancode(exe_path, init_flag_file)
                        return exe_path

        # If not found, look for existing installation with possible paths
        possible_paths = [
            version_dir / "scancode",
            version_dir / "scancode.exe",
            version_dir / "scancode.bat",
            version_dir / f"scancode-toolkit-v{scancode_ver}" / "scancode",
            version_dir / f"scancode-toolkit-v{scancode_ver}" / "scancode.exe",
        ]

        for exe_path in possible_paths:
            if exe_path.exists():
                # Check if initialization is needed
                if not init_flag_file.exists():
                    self._initialize_scancode(exe_path, init_flag_file)
                return exe_path

        # Download and install if not found
        print(f"Scancode {scancode_ver} (Python {python_ver}) not found in cache.")
        print("Downloading from GitHub releases...")

        try:
            download_url = self._build_download_url(scancode_ver, python_ver)
            print(f"Download URL: {download_url}")

            # Create cache directory
            cache_dir.mkdir(parents=True, exist_ok=True)

            # Download
            platform_name, _ = self._get_platform_info()
            if platform_name == "windows":
                archive_name = f"scancode-v{scancode_ver}-py{python_ver}-{platform_name}.zip"
            else:
                archive_name = f"scancode-v{scancode_ver}-py{python_ver}-{platform_name}.tar.xz"

            archive_path = cache_dir / archive_name

            if not self._download_scancode(download_url, archive_path):
                raise FileNotFoundError(f"Failed to download scancode from {download_url}")

            # Extract
            if not self._extract_scancode(archive_path, version_dir):
                raise FileNotFoundError("Failed to extract scancode archive")

            # Clean up archive
            archive_path.unlink()

            # Find executable in the extracted directory structure
            exe_path = None
            if version_dir.exists():
                for root, _, _ in os.walk(version_dir):
                    root_path = Path(root)
                    for exe_name in ["scancode", "scancode.exe", "scancode.bat"]:
                        exe_path = root_path / exe_name
                        if exe_path.exists() and exe_path.is_file():
                            # Initialize scancode after first installation
                            self._initialize_scancode(exe_path, init_flag_file)
                            return exe_path

            for exe_path in possible_paths:
                if exe_path.exists():
                    self._initialize_scancode(exe_path, init_flag_file)
                    return exe_path

            raise FileNotFoundError("Scancode executable not found after installation")

        except Exception as e:
            error_msg = (
                f"Failed to download or install scancode {scancode_ver} (Python {python_ver}). "
                f"Please check if the --scancode-ver and --python-ver parameters are correct. "
                f"Error: {e}"
            )
            raise FileNotFoundError(error_msg) from e

    def _run_scancode_scan(self, target_path: str) -> str:
        """
        Run scancode scan on the specified target.

        Args:
            target_path: Path to scan

        Returns:
            Path to the generated JSON output file

        Raises:
            RuntimeError: If scan fails
        """
        scancode_ver = getattr(self.args, "scancode_ver", "32.4.0")
        python_ver = getattr(self.args, "python_ver", "3.13")

        # Get scancode executable
        scancode_exe = self._get_scancode_executable(scancode_ver, python_ver)

        # Get the scancode root directory (where the executable is located)
        scancode_root = scancode_exe.parent

        # Prepare output file with absolute path
        target_name = Path(target_path).name
        output_dir = getattr(self.args, "output", None)
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            output_file = output_path / "scancode_result.json"
        else:
            output_file = Path.cwd() / f"scancode_output_{target_name}.json"

        # Build command with absolute paths
        process_count = getattr(self.args, "scancode_process", 1)
        cmd = [
            str(scancode_exe.resolve()),  # Use absolute path for executable
            "--json",
            str(output_file.resolve()),  # Use absolute path for output
            "--license",
            '--ignore=".*"',
            f"-n {process_count}",
            str(Path(target_path).resolve()),
        ]

        try:
            # Run scancode from its root directory with real-time output
            process = subprocess.Popen(
                cmd,
                cwd=str(scancode_root),  # Execute from scancode root directory
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True,
            )

            # Stream output in real-time
            print("Scancode output:")
            while True:
                output = process.stdout.readline()
                if output == "" and process.poll() is not None:
                    break
                if output:
                    # Remove trailing newline and print directly
                    line = output.rstrip("\n\r")
                    if line:  # Only print non-empty lines
                        print(f"  {line}")

            # Wait for process to complete and get return code
            return_code = process.poll()

            # Check if output file exists instead of relying on return code
            if output_file.exists() and output_file.stat().st_size > 0:
                print(f"✓ Scancode scan completed: {output_file}")
                if return_code != 0:
                    print(f"⚠ Warning: Scancode returned non-zero exit code ({return_code}), but output file exists")
                return str(output_file)
            else:
                error_msg = f"Scancode scan failed - no valid output file generated (return code: {return_code})"
                raise RuntimeError(error_msg)

        except subprocess.CalledProcessError as e:
            error_msg = f"Scancode scan failed with return code {e.returncode}"
            print(f"✗ {error_msg}")
            raise RuntimeError(error_msg) from e
        except Exception as e:
            error_msg = f"Scancode scan failed: {e}"
            print(f"✗ {error_msg}")
            raise RuntimeError(error_msg) from e

    def add_license(self, context: GraphManager, file_path: str, spdx_results: DualLicense, test):
        """Add license information to the context node.

        Args:
            context: GraphManager instance to modify
            file_path: Path of the file to which the license applies
            spdx_results: DualLicense object containing license information
            test: Test identifier for the license application

        This method adds the license information to the context node corresponding to the file path."""
        parent_label = "//" + file_path.replace("\\", "/")
        context_node = context.query_node_by_label(parent_label)

        if context_node and spdx_results:
            context_node["licenses"] = spdx_results
            context_node["test"] = test
            self.count.add(parent_label)

    def _report_shadow_license_stats(self, license_usage: dict[str, set[str]]):
        """
        Print a rich table summary of shadow license application results.
        """
        if not license_usage:
            print("No shadow licenses applied.")
            return

        print("\nShadow License Application Summary:")
        print("-" * 80)
        print(f"{'License':<30} {'Node Count':<12} {'Example Nodes (max 3)'}")
        print("-" * 80)

        total = 0
        for license_str, nodes in license_usage.items():
            total += len(nodes)
            examples = ", ".join(list(nodes)[:3])
            print(f"{license_str:<30} {len(nodes):<12} {examples}")

        print("-" * 80)
        print(f"Total Nodes Modified: {total}")

    def _apply_shadow_licenses(self, context: GraphManager, shadow_patterns: dict[str, str]) -> dict[str, set[str]]:
        """
        Apply shadow licenses using wildcard patterns, and return stats.

        Returns:
            A dict mapping license string -> set of node IDs
        """
        spdx = SPDXParser()
        license_usage = defaultdict(set)

        for node_id, node_data in context.nodes(data=True):
            if node_data.get("type") == "code":
                for pattern, license_str in shadow_patterns.items():
                    if fnmatch.fnmatch(node_id, pattern):
                        spdx_license = spdx(license_str)
                        if spdx_license:
                            context.modify_node_attribute(node_id, "licenses", spdx_license)
                            license_usage[license_str].add(node_id)
                        break

        return license_usage

    def parse_shadow(self, json_path: str, context: GraphManager):
        """
        Parse the shadow license file and add the license to the context.
        The shadow license file should be in JSON format, with the following structure:
        {
            "//kernel/*": "Apache-2.0",
            "//specific/file.c": "MIT"
        }

        Usage:
            ```python

            parser = ScancodeParser(args, config)
            context = parser.parse_shadow("shadow.json", context)
            ```
        """
        if context is None:
            raise ValueError(f"Context can not be None in {self.__class__.__name__}.")

        with open(json_path, "r", encoding="utf-8") as f:
            shadow_rules = json.load(f)

        direct_matches = {}
        wildcard_patterns = {}

        for pattern, license_str in shadow_rules.items():
            if "*" in pattern or "?" in pattern or "[" in pattern:
                wildcard_patterns[pattern] = license_str
            else:
                direct_matches[pattern] = license_str

        spdx = SPDXParser()
        license_usage = defaultdict(set)

        for key, license_str in direct_matches.items():
            spdx_license = spdx(license_str)
            if spdx_license:
                context.modify_node_attribute(key, "licenses", spdx_license)
                license_usage[license_str].add(key)

        if wildcard_patterns:
            wildcard_usage = self._apply_shadow_licenses(context, wildcard_patterns)
            for lic, nodes in wildcard_usage.items():
                license_usage[lic].update(nodes)

        self._report_shadow_license_stats(license_usage)
        return context

    def remove_ref_lang(self, spdx_id: str) -> str:
        """Remove scancode ref prefix and language suffix from SPDX IDs.

        Args:
            spdx_id: The SPDX ID to process.

        Returns:
            str: The processed SPDX ID with ref prefix and language suffix removed."""

        if not self.checker.is_license_exist(spdx_id):
            new_spdx_id = re.sub(r"LicenseRef-scancode-", "", spdx_id)
            if self.checker.is_license_exist(new_spdx_id):
                return new_spdx_id
            new_spdx_id = re.sub(r"-(en|cn)$", "", new_spdx_id)
            if self.checker.is_license_exist(new_spdx_id):
                return new_spdx_id
            return spdx_id

        return spdx_id

    def parse_json(self, json_path: str, context: GraphManager):
        """Parse the scancode JSON output file and add licenses to the context.

        Args:
            json_path: The path to the scancode JSON output file.
            context: GraphManager instance to modify.

        This method reads the scancode JSON file, extracts license detections,
        and adds them to the context.
        """

        if context is None:
            raise ValueError(f"Context can not be None in {self.__class__.__name__}.")

        if root_path := getattr(self.args, "scancode_dir", None):
            rel_path = os.path.relpath(os.path.dirname(json_path), root_path)
        else:
            rel_path = None

        with open(json_path, "r", encoding="utf-8") as f:
            scancode_results = json.load(f)

            for detects in scancode_results["license_detections"]:
                for match in detects["reference_matches"]:
                    if rel_path:
                        file_path = os.path.join(rel_path, match["from_file"])
                    else:
                        # ! Remove scancode project root, because gn profile json does not contain it.
                        file_path = os.path.relpath(match["from_file"], match["from_file"].split(os.sep)[0])

                    spdx_results = self.spdx_parser(
                        match["license_expression_spdx"],
                        file_path,
                        proprocessor=self.remove_ref_lang if self.args.rm_ref_lang else None,
                    )

                    if spdx_results:
                        self.add_license(context, file_path, spdx_results, match["license_expression_spdx"] + "_m")

            for file in scancode_results["files"]:
                if rel_path:
                    file_path = os.path.join(rel_path, file["path"])
                else:
                    # ! Remove scancode project root, because gn profile json does not contain it.
                    file_path = os.path.relpath(file["path"], file["path"].split(os.sep)[0])

                if file["detected_license_expression_spdx"]:
                    spdx_results = self.spdx_parser(file["detected_license_expression_spdx"], file_path)

                    self.add_license(context, file_path, spdx_results, file["detected_license_expression_spdx"] + "_f")

    def parse(self, project_path: str, context: Optional[GraphManager] = None) -> GraphManager:
        """
        Parse scancode results or run scancode scan.

        Usage:
        ```shell
        # Parse existing scancode output
        scancode --json-pp license.json .
        # or
        scancode --json-pp license.json /path/to/your/project

        # Run scancode scan directly
        liscopelens --scancode-scan /path/to/target --scancode-ver 32.4.0 --python-ver 3.13
        ```
        """

        # Handle scancode scan execution
        if getattr(self.args, "scancode_scan", None):
            scan_target = self.args.scancode_scan
            if not os.path.exists(scan_target):
                raise FileNotFoundError(f"Scan target not found: {scan_target}")

            print(f"Starting scancode scan on: {scan_target}")
            output_file = self._run_scancode_scan(scan_target)

            # Parse the generated output
            self.parse_json(output_file, context)

        elif getattr(self.args, "scancode_file", None):
            if not os.path.exists(self.args.scancode_file):
                raise FileNotFoundError(f"File not found: {self.args.scancode_file}")
            self.parse_json(self.args.scancode_file, context)

        elif getattr(self.args, "scancode_dir", None):
            if not os.path.exists(self.args.scancode_dir):
                raise FileNotFoundError(f"Directory not found: {self.args.scancode_dir}")
            for root, _, files in track(os.walk(self.args.scancode_dir), "Parsing scancode's output..."):
                for file in files:
                    if file.endswith(".json"):
                        self.parse_json(os.path.join(root, file), context)

            json.dump(
                list(
                    set(node[0] for node in context.nodes(data=True) if node[1].get("type", None) == "code")
                    - self.count
                ),
                open("scancode.json", "w", encoding="utf-8"),
            )
        else:
            raise ValueError("No scancode input provided. Use --scancode-file, --scancode-dir, or --scancode-scan.")

        if getattr(self.args, "shadow_license", None):
            print("Parsing shadow license...")
            self.parse_shadow(self.args.shadow_license, context)

        if output := getattr(self.args, "output", None):
            os.makedirs(output, exist_ok=True)

            context.save(output + "/origin.json")

        return context


class ScancodeParserEntry(BaseParserEntry):
    """
    The entry for Scancode parser.
    This entry will be used when user input the command `liscopelens scancode`.
    """

    parsers = (ScancodeParser,)  # Replace with actual Scancode parser classes
    entry_help = "Scan the project using Scancode toolkit."
    entry_name = "scancode"
