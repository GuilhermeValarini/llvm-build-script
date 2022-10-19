from argparse import Namespace
import datetime
from pathlib import Path
import subprocess
import sys
import shutil
import os
import git
import click

# Global variables
current_path = Path(".").absolute()
execution_datetime = datetime.datetime.now().strftime("%Y-%m-%d-T%H%M%S")

# Command line options choices
build_type_options = [
    "Release",
    "Debug",
]
linker_options = [
    "lld",
    "gold",
    "ld",
]
cmake_generators = [
    "Ninja",
    "Unix Makefiles",
]
llvm_projects = [
    "bolt",
    "clang",
    "clang-tools-extra",
    "compiler-rt",
    "cross-project-tests",
    "flang",
    "libc",
    "libclc",
    "lld",
    "lldb",
    "mlir",
    "openmp",
    "polly",
    "pstl",
]
llvm_runtimes = [
    "libc",
    "libunwind",
    "libcxxabi",
    "pstl",
    "libcxx",
    "compiler-rt",
    "openmp",
    "llvm-libgcc",
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
    "XCore",
]


def printWarning(warning_msg: str) -> None:
    terminal_width = shutil.get_terminal_size()[0]
    sys.stderr.writelines(
        [
            f"{' Warning Start '.center(terminal_width, '=')}\n",
            f"{warning_msg}\n",
            f"{' Warning End '.center(terminal_width, '=')}\n",
        ]
    )


def printFatalError(error_msg: str) -> None:
    terminal_width = shutil.get_terminal_size()[0]
    sys.stderr.writelines(
        [f"{' Fatal Error '.center(terminal_width, '=')}\n", f"{error_msg}\n"]
    )
    exit(1)


def runShellCommand(
    command: list,
    error_msg: str = "",
    print_only: bool = True,
    disable_output: bool = False,
) -> None:
    print(f"\n{' '.join(command)}\n")
    if not print_only:
        returncode = subprocess.run(command, capture_output=disable_output).returncode
        if returncode != 0:
            printFatalError(
                "Executed shell command failed:\n"
                f"Command: {' '.join(command)}\n"
                f"Return code: {returncode}"
            )


def isDirectoryEmpty(path: str) -> bool:
    return not Path(path).exists() or len(os.listdir(path)) == 0


@click.group(chain=True)
@click.argument("source-path", type=Path)
@click.option("--build-path", "-bp", type=Path, help="path to cmake build")
@click.option("--install-path", "-ip", type=Path, help="path to install llvm")
@click.option(
    "--build-type",
    "-bt",
    type=click.Choice(build_type_options, case_sensitive=False),
    default="Release",
    help="cmake build type",
)
@click.option(
    "--print-only",
    "-po",
    is_flag=True,
    type=bool,
    help="only print commands",
)
@click.option(
    "--generator",
    "-g",
    type=click.Choice(cmake_generators),
    default="Ninja",
    help="compiler generator to be used by cmake",
)
@click.pass_context
def cli(
    ctx: click.core.Context,
    source_path: Path,
    build_path: Path,
    install_path: Path,
    build_type: str,
    print_only: bool,
    generator: str,
) -> None:
    ctx.ensure_object(Namespace)

    if source_path == None or not source_path.exists():
        printFatalError(f"Source path does not exists: {source_path}")

    # Default build path based on source and build type
    default_build_path: Path = current_path / "builds" / source_path.name.lower()

    # Default install path based on branch name
    branch_name: Path = git.Repo(source_path).active_branch.name.replace("/", "-")
    default_install_path: Path = (
        current_path / "installs" / branch_name / build_type.lower()
    )

    # Set command chain context
    ctx.obj.source = source_path
    ctx.obj.build = default_build_path if build_path == None else build_path
    ctx.obj.build /= build_type.lower()
    ctx.obj.install = default_install_path if install_path == None else install_path
    ctx.obj.build_type = build_type.capitalize()
    ctx.obj.print_only = print_only
    ctx.obj.generator = generator

    # Print args
    print(f"Global arguments:")
    print(f"- source: {ctx.obj.source}")
    print(f"- build: {ctx.obj.build}")
    print(f"- install: {ctx.obj.install}")
    print(f"- build_type: {ctx.obj.build_type}")
    print(f"- print_only: {ctx.obj.print_only}")
    print(f"- generator: {ctx.obj.generator}")


@cli.command()
@click.option(
    "--disable-ccache",
    "-dc",
    is_flag=True,
    type=bool,
    help="disables ccache",
)
@click.option(
    "--use-env-compiler",
    "-uec",
    is_flag=True,
    type=bool,
    help="uses the environment compiler as defined by CC and CXX env vars",
)
@click.option(
    "--enable-projects",
    "-ep",
    type=click.Choice(llvm_projects),
    default=["clang"],
    multiple=True,
    help="list of enabled LLVM projects",
)
@click.option(
    "--enable-runtimes",
    "-er",
    type=click.Choice(llvm_runtimes),
    default=["openmp", "libcxx", "libcxxabi"],
    multiple=True,
    help="list of enabled LLVM runtimes",
)
@click.option(
    "--enable-targets",
    "-et",
    type=click.Choice(llvm_targets),
    default=["X86", "NVPTX"],
    multiple=True,
    help="list of enabled LLVM targets",
)
@click.option(
    "--disable-debug-messages",
    "-ddm",
    is_flag=True,
    type=bool,
    help="disable the debug messages at compile time",
)
@click.option(
    "--disable-profiler",
    "-dp",
    is_flag=True,
    type=bool,
    help="disable the profiler at compile time",
)
@click.option(
    "--linker",
    "-l",
    type=click.Choice(linker_options),
    default="lld",
    help="linker to be used",
)
@click.pass_context
def config(
    ctx: click.core.Context,
    disable_ccache: bool,
    use_env_compiler: bool,
    enable_projects: list[str],
    enable_runtimes: list[str],
    enable_targets: list[str],
    disable_debug_messages: bool,
    disable_profiler: bool,
    linker: str,
) -> None:
    # Set and check the llvm root path
    llvm_root_path: Path = ctx.obj.source / "llvm"

    if not llvm_root_path.exists():
        printFatalError(f"LLVM root path not found: {llvm_root_path}")

    # Check and create the build path
    if ctx.obj.build.exists() and not isDirectoryEmpty(ctx.obj.build):
        printWarning(
            f"Build path not empty and CMake build cache may be used: {ctx.obj.build}"
        )

    if not ctx.obj.print_only:
        ctx.obj.build.mkdir(parents=True, exist_ok=True)

    # Check ccache
    if not disable_ccache and shutil.which("ccache") == None:
        printWarning(f"CCache enabled but not installed. Building without cache.")
        disable_ccache = True

    # Check env compiler
    clang_path: Path = shutil.which("clang")
    clangxx_path: Path = shutil.which("clang++")
    if not use_env_compiler and clang_path == None or clangxx_path == None:
        printWarning(f"Clang not found. Building with default C/C++ compilers.")
        use_env_compiler = True

    # Get enabled projects and runtimes
    enable_projects: set = set(enable_projects)
    enable_runtimes: set = set(enable_runtimes)

    if not enable_projects.isdisjoint(enable_runtimes):
        printFatalError(
            f"Enabled projects ({enable_projects}) and enabled runtimes({enable_runtimes}) "
            f"list should be disjoint. Prefer placing {enable_projects & enable_runtimes} "
            "only in the runtimes list."
        )

    enable_projects: str = ";".join(enable_projects)
    enable_runtimes: str = ";".join(enable_runtimes)
    enable_targets: str = ";".join(set(enable_targets))
    openmp_standalone: int = int(
        "openmp" in enable_projects and "clang" not in enable_projects
    )
    debug_messages: int = int(not disable_debug_messages)
    profiler: int = int(not disable_profiler)

    # Print args
    print(f"Config arguments:")
    print(f"- llvm_root_path: {llvm_root_path}")
    print(f"- disable_ccache: {disable_ccache}")
    print(f"- use_env_compiler: {use_env_compiler}")
    print(f"- enable_projects: {enable_projects}")
    print(f"- enable_runtimes: {enable_runtimes}")
    print(f"- enable_targets: {enable_targets}")
    print(f"- disable_debug_messages: {disable_debug_messages}")
    print(f"- disable_profiler: {disable_profiler}")

    # Set cmake config command
    cmake_config_command = [
        "cmake",
        f"-S{llvm_root_path}",
        f"-B{ctx.obj.build}",
        f"-G{ctx.obj.generator}",
        f"-DCMAKE_BUILD_TYPE={ctx.obj.build_type}",
        f"-DCMAKE_INSTALL_PREFIX={ctx.obj.install}",
        f"-DLLVM_ENABLE_PROJECTS={enable_projects}",
        f"-DLLVM_ENABLE_RUNTIMES={enable_runtimes}",
        f"-DLLVM_TARGETS_TO_BUILD={enable_targets}",
        f"-DCLANG_VENDOR=OmpCluster",
        f"-DLIBOMPTARGET_ENABLE_DEBUG={debug_messages}",
        f"-DLLVM_ENABLE_ASSERTIONS=On",
        f"-DCMAKE_EXPORT_COMPILE_COMMANDS=On",
        f"-DLLVM_INCLUDE_BENCHMARKS=Off",
        f"-DLIBOMPTARGET_ENABLE_PROFILER={profiler}",
        f"-DOPENMP_STANDALONE_BUILD={openmp_standalone}",
    ]
    if not use_env_compiler:
        cmake_config_command.append(f"-DCMAKE_C_COMPILER={clang_path}")
        cmake_config_command.append(f"-DCMAKE_CXX_COMPILER={clangxx_path}")
        cmake_config_command.append(f"-DLLVM_USE_LINKER={linker}")
    if not disable_ccache:
        cmake_config_command.append(f"-DLLVM_CCACHE_BUILD=ON")
    if ctx.obj.build_type == "Debug":
        cmake_config_command.append("-DBUILD_SHARED_LIBS=1")
        cmake_config_command.append("-DLLVM_USE_SPLIT_DWARF=1")
    if "NVPTX" in enable_targets:
        cmake_config_command.append("-DCLANG_OPENMP_NVPTX_DEFAULT_ARCH=sm_86")
        cmake_config_command.append("-DLIBOMPTARGET_NVPTX_COMPUTE_CAPABILITIES=86")

    runShellCommand(
        cmake_config_command,
        "Failed to generate the cmake build project",
        ctx.obj.print_only,
    )


@cli.command()
@click.option(
    "--jobs",
    "-j",
    type=int,
    default=int(os.cpu_count() * 0.90),
    help="number of cores to use during build",
)
@click.pass_context
def build(ctx: click.core.Context, jobs: int) -> None:
    # Check the build path
    if not ctx.obj.build.exists() or isDirectoryEmpty(ctx.obj.build):
        printFatalError(
            f"Build path empty: {ctx.obj.build}. Please configure cmake first."
        )

    # Print args
    print(f"Build arguments:")
    print(f"- jobs: {jobs}")

    # Set cmake build command
    cmake_build_command = [
        "cmake",
        "--build",
        f"{ctx.obj.build}",
        "-j",
        f"{jobs}",
    ]

    runShellCommand(
        cmake_build_command, "Failed to build the LLVM project", ctx.obj.print_only
    )


@cli.command()
@click.pass_context
def install(ctx: click.core.Context) -> None:
    # Check the build path
    if not ctx.obj.build.exists() or isDirectoryEmpty(ctx.obj.build):
        printFatalError(
            f"Build path empty: {ctx.obj.build}. Please configure cmake first."
        )

    # Create the install path
    if not ctx.obj.print_only:
        ctx.obj.install.mkdir(parents=True, exist_ok=True)

    if not ctx.obj.install.exists():
        printFatalError(f"Install path does not exist: {ctx.obj.install}")

    if not isDirectoryEmpty(ctx.obj.install):
        printWarning(f"Install path not empty: {ctx.obj.install}")

    # Set cmake install command
    cmake_install_command = [
        "cmake",
        "--install",
        f"{ctx.obj.build}",
        "--prefix",
        f"{ctx.obj.install}",
    ]

    runShellCommand(
        cmake_install_command,
        "Failed to install the LLVM project",
        ctx.obj.print_only,
        disable_output=True,
    )


@cli.command()
@click.option(
    "--test",
    "-t",
    type=str,
    default="check-all",
    help="test to execute",
)
@click.pass_context
def test(ctx: click.core.Context, test: str) -> None:
    # Check the build path
    if not ctx.obj.build.exists() or isDirectoryEmpty(ctx.obj.build):
        printFatalError(
            f"Build path empty: {ctx.obj.build}. Please configure cmake first."
        )

    # Print args
    print(f"Test arguments:")
    print(f"- test: {test}")

    test_command = [
        "ninja" if ctx.obj.generator == "Ninja" else "make",
        "-C",
        f"{ctx.obj.build}",
        f"{test}",
    ]

    runShellCommand(
        test_command,
        "Failed to successfully test the LLVM project failed",
        ctx.obj.print_only,
    )


if __name__ == "__main__":
    cli()
