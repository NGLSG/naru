# Naru

[English](README.en.md) · [构建](docs/building.md) · [实现状态](docs/status.md) · [贡献](CONTRIBUTING.md)

Naru 是用 Vyx 编写的语言研究型 AOT 编译器。核心提供规则求值、模块、工具链和 MLIR 接口；语言的语法、类型系统、所有权和编译过程由 `.stx` 规则库定义。

`fn`、`let`、结构体和运算符都来自规则库。项目选择方言后，用户代码直接使用它们，入口可以是 `.nru`、`.c` 或其他文件。多个规则库可以组合，同级规则匹配冲突时报错。

后端在进程内使用 MLIR，支持自定义方言和 pass。CPU 目标通过 LLVM 和 LLD 生成原生程序，设备目标可以保留自己的 IR。规则既可动态加载，也可 AOT 固化到编译器中。

当前版本为 **0.2.0-preview.1**，开发平台为 **Windows x86_64**。C11 方言尚未完成全部兼容性验证，已知问题见 [实现状态](docs/status.md)。

## 示例

```text
fn main() -> i32 {
    var total = 0;
    var i = 0;
    while i < 7 {
        total = total + i;
        i = i + 1;
    }
    return total * 2;
}
```

这段程序使用 [base 方言](dialects/base.stx)。其中的加法语法由规则定义：

```text
syntax expr[50,left] `$a:expr + $b:expr` => Add($a, $b);
```

`syntax` 生成结构化项，`effect` 规则负责分析和 lowering。扩展语言时，可以复用已有语法并增加类型语义，也可以定义自己的前端。见 [规则系统](docs/rule-system.md) 和 [规则库组合](docs/rule-libraries.md)。

## 使用分发包

在解压目录执行：

```powershell
.\naru.exe build --project .\Naru.toml --target exe -o .\target\answer.exe
& .\target\answer.exe
$LASTEXITCODE # 42
```

保留包中的规则、后端 DLL、插件和运行库目录。编译器运行时无需 Python 或外部编译器；链接系统 CRT 需要安装相应的 MSVC/Windows SDK 库。包管理器需要 Python 3.11+，获取 Git 包还需要 Git。

## 从源码构建

准备 Vyx Windows LLVM 22 SDK 及 [构建依赖](docs/building.md)，在 x64 开发者 PowerShell 中执行：

```powershell
$env:VYX_SDK_ROOT = 'C:\SDK\vyx-sdk-windows-x86_64-llvm22'
python tools/mlir/bootstrap.py
.\build.ps1 -Release -Jobs 4
.\target\naru.exe build examples\answer.nru --target exe -o target\answer.exe
& .\target\answer.exe
```

首次构建会下载固定版本的 MLIR SDK，准备 LLD 和日志库。内存有限时使用 `-Jobs 1`。

## 规则库与档案馆

- [dialects/](dialects/)：基础语言、所有权、闭包、协程、C11、B、Pascal、BASIC 及共享设施。
- [组合示例](examples/emergence/)：将多个规则库用于同一套语言。
- [包管理器](docs/packages.md)：JSON 注册表、Git 来源、方言模板和依赖锁定。
- [historical/](historical/)：语言版本、文献索引与考据。

创建方言库：

```powershell
.\naru.ps1 pkg init target\my-language --name my-language
.\naru.ps1 build --project target\my-language
```

## 开发

```powershell
python tests/run.py
python tests/rules.py
python tests/iteration.py
```

其他测试见 [tests/README.md](tests/README.md)。架构见 [编译器实现](docs/implementation.md)，提交修改前请读 [贡献说明](CONTRIBUTING.md)。

## 许可证

Naru 原创代码、规则、示例和文档采用 [MIT](LICENSE-MIT) OR [Apache-2.0](LICENSE-APACHE) 双许可。第三方组件及历史材料的许可见 [THIRD_PARTY.md](THIRD_PARTY.md)。源码预览包包含档案条目和注记，不附带第三方史料原件。
