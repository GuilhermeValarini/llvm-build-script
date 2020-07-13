import argparse
import datetime
import pathlib
import subprocess
import sys
import shutil
import tempfile
import os

# Global variables
current_path = pathlib.Path(".").absolute()
execution_datetime = datetime.datetime.now().strftime("%Y-%m-%d-T%H%M%S")

# Command line options choices
build_type_options = ["Release", "Debug"]
linker_option = ["lld", "gold"]
cmake_generators = ["Ninja", "Unix Makefiles"]

# Define comandline argument options
arg_parser = argparse.ArgumentParser()
# Project path options
arg_parser.add_argument(
    "-sp", "--source-path",
    type=pathlib.Path, default=current_path/"llvm-project/llvm",
    help="Path to the llvm-project source directory. " +
         "Default: \"$PWD/llvm-project\"."
)
arg_parser.add_argument(
    "-bp", "--build-path",
    type=pathlib.Path, default=None,
    help="Path to a directory used by CMake as its build path. " +
         "By default, this script will create a temporary directory in the " +
         "temporary folder of your operational system. If you desired to " +
         "keep the CMake build files, please provide a path through this flag."
)
install_path_args = arg_parser.add_mutually_exclusive_group()
install_path_args.add_argument(
    "-ip", "--install-path",
    type=pathlib.Path, default=current_path/"llvm-install"/execution_datetime,
    help="Path to a directory used by CMake as the llvm install path. " +
         "Default: \"$PWD/llvm-builds/<build-label>\"."
)
install_path_args.add_argument(
    "-bl", "--install-label",
    type=str, default=None,
    help="Label to use when installing to the default install path. " +
         "Default: datetime of the execution of this script."
)
# Build options
arg_parser.add_argument(
    "-bt", "--build-type",
    type=str.capitalize, choices=build_type_options, default="Release",
    help="Build type passed to the CMake system. Default: Release"
)
arg_parser.add_argument(
    "-dc", "--disable-ccache",
    action="store_true",
    help="Disable CCache build cache."
)
arg_parser.add_argument(
    "-edm", "--enable-debug-messages",
    action="store_true",
    help="Enable detailed libomptarget debug messages."
)
arg_parser.add_argument(
    "-g", "--generator",
    type=str, choices=cmake_generators,
    default="Ninja" if shutil.which("ninja") != None else "Unix Makefiles",
    help="Use local compilers provided by CC and CXX environment variables " +
         "instead of clang."
)
arg_parser.add_argument(
    "-bs", "--environment-compiler",
    action="store_true",
    help="Use local compilers provided by CC and CXX environment variables " +
         "instead of clang."
)
arg_parser.add_argument(
    "-l", "--linker",
    type=str, choices=linker_option, default=None,
    help="Linker to be used during the LLVM compilation. " +
         "Default: system default linker."
)
# Script stages options
arg_parser.add_argument(
    "-db", "--disable-build",
    action="store_true",
    help="Disable the script build stage."
)
arg_parser.add_argument(
    "-dt", "--disable-tests",
    action="store_true",
    help="Disable the script test stage."
)
# Script options
arg_parser.add_argument(
    "-po", "--print-only",
    action="store_true",
    help="Only print actions instead of executing them."
)
arg_parser.add_argument(
    "-fo", "--force-overwrite",
    action="store_true",
    help="Overwrite previous build installs."
)


def printWarning(warning_msg: str) -> None:
    terminal_width = shutil.get_terminal_size()[0]
    sys.stderr.writelines([
        f"{' Warning Start '.center(terminal_width, '=')}\n",
        f"{warning_msg}\n",
        f"{' Warning End '.center(terminal_width, '=')}\n"
    ])


def printFatalError(error_msg: str) -> None:
    terminal_width = shutil.get_terminal_size()[0]
    sys.stderr.writelines([
        f"{' Fatal Error '.center(terminal_width, '=')}\n",
        f"{error_msg}\n"
    ])
    exit(1)


def runShellCommand(command: list, error_msg: str = "", print_only: bool = True) -> None:
    print(f"{' '.join(command)}\n")
    if not print_only:
        returncode = subprocess.run(command).returncode
        if returncode != 0:
            printFatalError(
                "Executed shell command failed:\n"
                f"Command: {' '.join(command)}\n"
                f"Return code: {returncode}"
            )


def isDirectoryEmpty(path: str) -> bool:
    return not pathlib.Path(path).exists() or len(os.listdir(path)) == 0


def main(args: argparse.Namespace) -> None:
    # Preprocess arguments and create temporary and output directories
    if not args.source_path.exists:
        printFatalError(f"Source path does not exists: {args.source_path}")

    if args.build_path == None:
        args.build_tmp_dir = tempfile.TemporaryDirectory()
        args.build_path = pathlib.Path(args.build_tmp_dir.name)
    elif args.build_path.exists and not isDirectoryEmpty(args.build_path):
        printWarning("Build path not empty and CMake build cache may be "
                     f"used: {args.install_path}")

    if not args.print_only:
        args.build_path.mkdir(parents=True, exist_ok=True)

    if args.install_label != None:
        args.install_path = args.install_path.parent / args.install_label

    if not args.force_overwrite and not args.disable_build:
        if args.install_path.exists and not isDirectoryEmpty(args.install_path):
            printFatalError(f"Install path not empty: {args.install_path}")

    if not args.print_only:
        args.install_path.mkdir(parents=True, exist_ok=True)

    if not args.disable_ccache:
        args.ccache_path = shutil.which("ccache")
        if args.ccache_path == None:
            printWarning(
                f"CCache enabled but not installed. Building without cache.")
            args.disable_ccache = True

    if not args.environment_compiler:
        args.clang_path = shutil.which("clang")
        args.clangxx_path = shutil.which("clang++")
        if args.clang_path == None or args.clangxx_path == None:
            printWarning(
                f"Clang not found. Building with default C/C++ compilers.")
            args.environment_compiler = True

    args.enable_debug_messages = int(args.enable_debug_messages)

    print(f"{args}\n")

    # Define the commands to be called
    cmake_config_command = [
        "cmake",
        f"-S{args.source_path}",
        f"-B{args.build_path}",
        f"-G{args.generator}",
        f"-DCMAKE_BUILD_TYPE={args.build_type}",
        f"-DCMAKE_INSTALL_PREFIX={args.install_path}",
        f"-DLIBOMPTARGET_ENABLE_DEBUG={args.enable_debug_messages}",
        "-DLLVM_ENABLE_PROJECTS=clang;openmp",
        "-DLLVM_TARGETS_TO_BUILD=X86;NVPTX"
    ]
    if not args.environment_compiler:
        cmake_config_command.append(f"-DCMAKE_C_COMPILER={args.clang_path}")
        cmake_config_command.append(
            f"-DCMAKE_CXX_COMPILER={args.clangxx_path}")
    if not args.disable_ccache:
        cmake_config_command.append(
            f"-DCMAKE_C_COMPILER_LAUNCHER={args.ccache_path}")
        cmake_config_command.append(
            f"-DCMAKE_CXX_COMPILER_LAUNCHER={args.ccache_path}")
    if args.linker != None:
        cmake_config_command.append(f"-DLLVM_USE_LINKER={args.linker}")
    if args.build_type == "Debug":
        cmake_config_command.append("-DBUILD_SHARED_LIBS=1")
        cmake_config_command.append("-DLLVM_USE_SPLIT_DWARF=1")

    cmake_build_command = [
        "cmake",
        "--build",
        f"{args.build_path}",
        "--target",
        "install"
    ]

    test_command = [
        'ninja' if args.generator == "Ninja" else "make",
        '-C',
        f'{args.build_path}',
        'check-all'
    ]

    # Scripts stages
    # CMake configuration
    runShellCommand(
        cmake_config_command,
        "Failed to generate the build rules using the passed configurations",
        args.print_only
    )

    # Build
    if not args.disable_build:
        runShellCommand(
            cmake_build_command,
            "Failed to build the LLVM project",
            args.print_only
        )

    # Test
    if not args.disable_tests:
        runShellCommand(
            test_command,
            "Failed to successfully test the LLVM project failed",
            args.print_only
        )


if __name__ == "__main__":
    args = arg_parser.parse_args()
    main(args)
