# 构建

编译器目前在 Windows x86_64 上开发和验证。

## 依赖

| 依赖 | 用途 |
| --- | --- |
| [Vyx Windows LLVM 22 SDK](https://github.com/vyx-lang/vyx/releases) | 编译前端，包含编译器、运行库、标准包和 DCI 工具 |
| Python 3.11+、Git | 依赖准备、包管理和测试 |
| Visual Studio C++ 构建工具、Windows SDK | 目标头文件、静态库和 CRT |
| Clang、llvm-nm、CMake、Ninja | 构建后端、日志库和运行时 |
| MLIR/LLVM SDK | 由 `tools/mlir/bootstrap.py` 下载并校验 |

在 Visual Studio 的 x64 开发者 PowerShell 中运行，确保 `clang++.exe`、`llvm-nm.exe`、`cmake.exe` 和 `ninja.exe` 位于 PATH。

## 配置 Vyx SDK

```powershell
$env:VYX_SDK_ROOT = 'C:\SDK\vyx-sdk-windows-x86_64-llvm22'
```

也可向构建脚本传入 `-VyxSdk <目录>`。查找顺序为：显式参数、`VYX_SDK_ROOT` / `VYX_SDK`、PATH 中的 `vyxc.exe`、工作区 `.tools/vyx-sdk/` 或 `.tools/vyx-sdk-windows-x86_64-llvm22/`。显式路径无效会报错。

2026-10-23 验证所用 `vyxc.exe` 的 SHA-256 为：

```text
4672c2a9cd117ce12ca70164b1d16cba6cb5d3471c9060f0d9039ee24d97039a
```

该构建使用了当日 SDK 的修复；使用其他版本时请先运行最小验证。工具链诊断见 [验证记录](vyx-dist-20261023.md)。

## 构建与运行

```powershell
python tools/mlir/bootstrap.py
.\build.ps1 -Release -Jobs 4
.\target\naru.exe build examples\answer.nru --target exe -o target\answer.exe
& .\target\answer.exe
$LASTEXITCODE # 42
```

`-Jobs` 控制构建线程数，内存有限时使用 `-Jobs 1`。`-RebuildBackend` 强制重建后端，`-MlirRoot` 指定兼容的 MLIR 安装目录。

MLIR 24 SDK 固定至 LLVM revision `19d3b2d2887ccd8fae4d091dc6c29d6b6d9e2b98`，下载约 563 MB，SHA-256 为 `a14f88bb2bb099505df1b01a06d02935807d5c325e7fa6394a5de8b5febfb6be`。已有归档可用 `python tools/mlir/bootstrap.py --archive <路径>` 导入。首次构建还会准备同版本 LLD 静态库和 spdlog。

前端使用 Vyx LLVM 22，后端使用 LLVM 24，两者通过 C ABI 连接。

## 测试

```powershell
python tests/run.py
python tests/rules.py
python tests/iteration.py
```

专项入口见 [tests/README.md](../tests/README.md)。C11 对照测试另需 Clang。

包管理方法见 [packages.md](packages.md)，打包方法见 [release.md](release.md)。
