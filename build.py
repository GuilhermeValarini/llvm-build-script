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
llvm_projects = [
    "clang",
    "clang-tools-extra",
    "compiler-rt",
    "debuginfo-tests",
    "libc",
    "libclc",
    "libcxx",
    "libcxxabi",
    "libunwind",
    "lld",
    "lldb",
    "llgo",
    "openmp",
    "parallel-libs",
    "polly",
    "pstl"
]
llvm_targets = [
    "AArch64",
    "AMDGPU",
    "ARM",
    "BPF",
    "Hexagon",
    "Lanai",
    "Mips",
    "MSP430",
    "NVPTX",
    "PowerPC",
    "RISCV",
    "Sparc",
    "SystemZ",
    "WebAssembly",
    "X86",
    "XCore"
]

# Define comandline argument options
arg_parser = argparse.ArgumentParser()
# Project path options
arg_parser.add_argument(
    "-sp", "--source-path",
    type=pathlib.Path, default=current_path/"llvm-project/llvm",
    help="Path to the llvm-project source directory. " +
         "Default: \"$PWD/llvm-project\"."
)
build_path_args = arg_parser.add_mutually_exclusive_group()
build_path_args.add_argument(
    "-tb", "--temporary-build",
    action="store_true",
    help="Store CMake and build files in a temporary directory."
)
build_path_args.add_argument(
    "-bp", "--build-path",
    type=pathlib.Path, default=current_path/"llvm-build",
    help="Path to a directory used by CMake as its build path. " +
         "By default, use \"$PWD/llvm-build/<build-type>\"."
)
install_path_args = arg_parser.add_mutually_exclusive_group()
install_path_args.add_argument(
    "-ip", "--install-path",
    type=pathlib.Path, default=current_path/"llvm-install"/execution_datetime,
    help="Path to a directory used by CMake as the llvm install path. " +
         "Default: \"$PWD/llvm-builds/<build-label>\"."
)
install_path_args.add_argument(
    "-il", "--install-label",
    type=str, default=None,
    help="Label to use when installing to the default install path. " +
         "Default: datetime of the execution of this script."
)

# LLVM options
arg_parser.add_argument(
    "-ep", "--enable-projects",
    type=str.lower, choices=llvm_projects, default=["clang", "openmp"], nargs="+",
    help="LLVM projects enabled during the build."
)
arg_parser.add_argument(
    "-et", "--enable-targets",
    type=str, choices=llvm_targets, default=["X86"], nargs="+",
    help="LLVM projects enabled during the build."
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
    help="Build system used as CMake generator. If installed, Ninja will be " +
         "used by default."
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
    if not args.source_path.exists():
        printFatalError(f"Source path does not exists: {args.source_path}")

    if args.temporary_build:
        args.build_tmp_dir = tempfile.TemporaryDirectory()
        args.build_path = pathlib.Path(args.build_tmp_dir.name)
    
    args.build_path /= args.build_type.lower()

    if args.build_path.exists and not isDirectoryEmpty(args.build_path):
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

    args.enable_projects = ";".join(args.enable_projects)
    args.enable_targets = ";".join(args.enable_targets)

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
        f"-DLLVM_ENABLE_PROJECTS={args.enable_projects}",
        f"-DLLVM_TARGETS_TO_BUILD={args.enable_targets}"
    ]
    if not args.environment_compiler:
        cmake_config_command.append(f"-DCMAKE_C_COMPILER={args.clang_path}")
        cmake_config_command.append(
            f"-DCMAKE_CXX_COMPILER={args.clangxx_path}")
    if not args.disable_ccache:
        cmake_config_command.append(f"-DLLVM_CCACHE_BUILD=ON")
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
