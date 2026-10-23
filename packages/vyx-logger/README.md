# Vyx std/logger for the Naru Windows build

`src/log.vyx` and `native/spdlog_dci.hpp` originate from the installed
Vyx SDK's `std_packages/logger` package. The SDK licenses are included here.
The exported module remains `std.log`; this is the standard library logger.

The SDK prepare script currently selects Linux commands, a Linux DCI triplet,
and pthread. `prepare.py` prepares the same spdlog 1.14.1 package with Ninja,
the Windows C++ ABI and the static CRT. The manifest removes pthread. The
native logger uses spdlog's thread-safe stderr sink so AST, JSON and IR output
on stdout remain usable by other tools. A pointer/length DCI helper constructs
fmt's string view inside C++, since the SDK adapter rejects its by-value Windows
ABI. Public standard-library logging functions are preserved. No Vyx
development files are modified.

The SDK's local-package module discovery does not add `std.log` to the root
module list. Naru therefore lists this package's Vyx module in its source list
as well as depending on its native library. Frozen build staging resolves these
host build paths before invoking Vyx.

Prepare with `python packages/vyx-logger/prepare.py --jobs 4`. `build.ps1` runs
this step automatically before compiling Naru. Vendored sources, native build
products and generated DCI contracts are build dependencies, not source files.
