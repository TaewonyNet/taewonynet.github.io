"""
Bootstrap Optimizer (Command-Driven)
====================================

This module provides a robust, cross-platform dependency management system
that relies on shell commands for validation and installation.

Key Features:
- Direct Shell Command Execution: Allows full control over how dependencies are checked and installed.
- Cross-Platform Support: Handles Windows, Linux, and macOS commands via OSMap.
- Dynamic Path Handling: Automatically substitutes the current Python interpreter path.
- Windows Environment Hot-Reload: Updates PATH without requiring a system restart.
"""

import logging
import os
import platform
import subprocess
import sys
from collections import namedtuple
from typing import Optional, Union, List

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("Bootstrap")

# NamedTuple for defining OS-specific commands.
# Defaults to None, indicating the dependency is not required/supported on that OS.
OSMap = namedtuple("OSMap", ["win", "linux", "mac"], defaults=[None, None, None])

# NamedTuple for defining a dependency configuration.
# name: Display name for logging.
# version_cmd: Command to check existence. Returns exit code 0 if satisfied.
# install_cmd: Command to install the dependency if version_cmd fails.
Dependency = namedtuple(
    "Dependency",
    ["name", "version_cmd", "install_cmd"]
)


class EnvironmentTools:
    """
    A utility class for OS detection and environment management.
    """

    @staticmethod
    def get_os_key() -> Optional[str]:
        """
        Identify the current operating system key.

        Returns:
            str: 'win', 'linux', or 'mac'. Returns None for other OSs.
        """
        s = platform.system()
        if s == "Windows":
            return "win"
        if s == "Linux":
            return "linux"
        if s == "Darwin":
            return "mac"
        return None

    @staticmethod
    def refresh_windows_path():
        """
        Reload Windows PATH environment variables from the registry into the current process.
        This allows the script to recognize newly installed binaries (e.g., via Winget)
        without restarting the shell.
        """
        if os.name != 'nt':
            return
        try:
            import winreg
            path_list = []
            
            # Retrieve User PATH
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as k:
                    val, _ = winreg.QueryValueEx(k, "Path")
                    path_list.append(val)
            except OSError:
                pass
            
            # Retrieve System PATH
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment") as k:
                    val, _ = winreg.QueryValueEx(k, "Path")
                    path_list.append(val)
            except OSError:
                pass
            
            if path_list:
                # Merge and expand variables (e.g., %SYSTEMROOT%)
                new_path = os.path.expandvars(";".join(path_list))
                os.environ["PATH"] = new_path
                logger.debug("Environment PATH refreshed successfully.")
                
        except Exception as e:
            logger.warning(f"Failed to refresh PATH environment variables: {e}")


class DependencyOptimizer:
    """
    Manages the lifecycle of checking and installing dependencies using explicit shell commands.
    """

    def __init__(self, dependencies: List[Dependency]):
        """
        Initialize the optimizer.

        Args:
            dependencies: A list of Dependency objects to process.
        """
        self.dependencies = dependencies
        self.os_key = EnvironmentTools.get_os_key()
        self.python_exe = sys.executable  # Current python interpreter path

    def _resolve_cmd(self, cmd_map: Union[str, OSMap]) -> Optional[str]:
        """
        Selects the appropriate command for the current OS and substitutes placeholders.

        Args:
            cmd_map: A single command string or an OSMap object.

        Returns:
            The formatted command string, or None if no command exists for this OS.
        """
        cmd = cmd_map
        if isinstance(cmd_map, OSMap):
            cmd = getattr(cmd_map, self.os_key, None)
        
        if cmd:
            # Replace placeholder with safe quoted path
            cmd = cmd.replace("{PYTHON}", f'"{self.python_exe}"')
        return cmd

    def _run_shell(self, cmd: str, ignore_error: bool = False) -> int:
        """
        Executes a shell command and returns the exit code.

        Args:
            cmd: The command string to execute.
            ignore_error: If True, suppresses error logging.

        Returns:
            int: The exit code (0 indicates success).
        """
        try:
            # shell=True is used to support complex commands (pipes, chaining)
            # Standard output is suppressed to keep logs clean
            result = subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            return result.returncode
        except Exception as e:
            if not ignore_error:
                logger.error(f"Command execution error: {cmd}\n{e}")
            return -1

    def process(self):
        """
        Main execution loop.
        Checks each dependency, installs if missing, and validates installation.
        Exits the program if a dependency fails to satisfy the requirements.
        """
        logger.info(f"Starting Bootstrap Optimizer (OS: {self.os_key})")

        for dep in self.dependencies:
            # 1. Resolve Commands
            v_cmd = self._resolve_cmd(dep.version_cmd)
            i_cmd = self._resolve_cmd(dep.install_cmd)

            # Skip if no command is defined for this OS
            if not v_cmd:
                continue

            # 2. Initial Validation
            # Exit code 0 means the dependency is already satisfied
            if self._run_shell(v_cmd, ignore_error=True) == 0:
                logger.info(f"Found existing dependency: {dep.name}")
                continue

            # 3. Installation
            if not i_cmd:
                logger.warning(f"Missing dependency: {dep.name}, but no install command provided. Skipping.")
                continue

            logger.info(f"Installing missing dependency: {dep.name}")
            logger.debug(f"Executing install command: {i_cmd}")
            
            # Execute installation
            self._run_shell(i_cmd)
            
            # Attempt to refresh PATH for Windows (for binaries like ffmpeg)
            if os.name == 'nt':
                EnvironmentTools.refresh_windows_path()

            # 4. Post-Installation Validation
            if self._run_shell(v_cmd) == 0:
                logger.info(f"Successfully installed: {dep.name}")
            else:
                logger.error(f"Failed to setup dependency: {dep.name}")
                logger.error("Please check the logs or install manually.")
                sys.exit(1)

        logger.info("Environment bootstrap completed. System is ready.\n")



def dependency_check(deps):
    dependencies = []
    if isinstance(deps, list):
        dependencies = deps
    elif isinstance(deps, dict):
        if len(deps) > 0 and isinstance(next(iter(deps.values())), Dependency):
            dependencies = deps.values()
        else:
            for dep in deps.items():
                dependencies.append(Dependency(dep[0],
                                               f'{{PYTHON}} -c "import {dep[0]}"',
                                               f'{{PYTHON}} -m pip install -q {dep[0]}'))
    optimizer = DependencyOptimizer(dependencies)
    optimizer.process()

if __name__ == "__main__":
    # Define dependencies with explicit check/install commands.
    # Use '{PYTHON}' to refer to the current Python interpreter.
    
    deps = [
        # 1. Python Package: TQDM
        # Check: Try importing the module.
        # Install: Pip install.
        Dependency(
            name="TQDM (Progress Bar)",
            version_cmd='{PYTHON} -c "import tqdm"',
            install_cmd='{PYTHON} -m pip install -q tqdm'
        ),

        # 2. Python Package with Version Constraint: Numpy >= 1.20
        # Check: Import and assert version.
        # Install: Pip install with version specifier.
        Dependency(
            name="Numpy (>=1.20)",
            version_cmd='{PYTHON} -c "import numpy; assert numpy.__version__ >= \'1.20\'"',
            install_cmd='{PYTHON} -m pip install -q \"numpy>=1.20\"'
        ),

        # 3. System Binary: FFmpeg
        # Check: Run 'ffmpeg -version'.
        # Install: Use OS-specific package managers (Winget, Apt, Brew).
        Dependency(
            name="FFmpeg",
            version_cmd=OSMap(
                win='ffmpeg -version',
                linux='ffmpeg -version',
                mac='ffmpeg -version'
            ),
            install_cmd=OSMap(
                win='winget install --id Gyan.FFmpeg -e --silent --accept-package-agreements --accept-source-agreements',
                linux='sudo apt-get install -y ffmpeg',
                mac='brew install ffmpeg'
            )
        ),

        # 4. Windows-Only Tool: 7-Zip
        # Check: Run '7z'.
        # Install: Winget.
        Dependency(
            name="7-Zip",
            version_cmd=OSMap(win='7z'), # None for Linux/Mac implies skipping
            install_cmd=OSMap(win='winget install --id 7zip.7zip -e --silent --accept-package-agreements --accept-source-agreements')
        )
    ]

    # Initialize and run the optimizer
    optimizer = DependencyOptimizer(deps)
    optimizer.process()

    # Application Logic Start
    import tqdm
    print(f"Main application started. TQDM Version: {tqdm.__version__}")
    