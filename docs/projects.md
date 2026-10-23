# 项目与原生链接

`Naru.toml` 是项目入口。应用项目选择规则包的导出方言；规则包也是 Naru
项目，用同一种清单声明依赖和导出。`.nru` 不需要引用 `.stx`。项目可同时选择
base、externc、ownership 等方言，语法与开放关系仍按既有模块规则组合。

## 应用项目

`examples/ffi/Naru.toml` 是可运行的 C 调用示例：

```toml
[package]
name = "ffi-demo"
version = "0.1.0"
entry = "main.nru"

[dependencies]
std = { path = "../../dialects", package = "naru-stdlib", version = "^0.2.0" }

[language]
dialects = ["std/base", "std/externc"]
entry = "item"
relation = "base.emit_program"
unit = "program"

[backend]
target = "exe"
opt_level = 2

[link]
runtime = "crt-static"

[build]
output_dir = "target"
```

```powershell
.\target\naru.exe resolve --project examples\ffi
.\target\naru.exe build --project examples\ffi --locked --report target\ffi.report.json
& .\examples\ffi\target\ffi-demo.exe
# 打印文本，返回 42
```

在应用目录及其子目录中直接执行 `naru build`，会向上查找 `Naru.toml`，使用
`package.entry` 和默认输出 `target/<package.name>.<artifact extension>`。
`--project` 接受目录或清单路径，并支持从其他工作目录构建。
`build.output` 可指定完整输出路径，`build.output_dir` 可改变默认输出目录。
采用目标 JSON 时，请明确设置 `build.output` 或 `-o`；前端默认后缀为 `.mlir`。

依赖路径、导出路径、入口、项目配置中的链接与扩展路径都相对于声明它们的
清单。显式 CLI 输入和输出路径相对于当前目录；CLI 标量覆盖项目标量，重复
列表选项追加到项目列表。旧 `language.rules = ["file.stx"]` 和 `--rules` 仍可使用。

入口文件名与语言无关。`package.entry` 是文件路径，不限制 `.nru`、`.c` 或其他
扩展名；编译器不根据文件后缀选择语言。`language.entry`（CLI `--entry`）是
默认规则解析器的语法类别，与入口文件路径是两个设置。

方言可以通过 `language.frontend` 指定普通 effect 关系，在默认词法分析之前
接收 `[绝对入口路径, 原始源码文本, 选项环境]`，返回程序项列表。C 示例选择：

```toml
[package]
name = "c11-demo"
version = "0.1.0"
entry = "main.c"

[dependencies]
std = { path = "../../dialects", package = "naru-stdlib", version = "^0.2.0" }

[language]
dialects = ["std/c11"]
frontend = "c11.frontend"
entry = "c11.item"
relation = "c11.emit_program"
unit = "program"

[frontend]
include_paths = "."
```

`examples/c11` 的入口为 `main.c`，头文件和 `#include "xxx.c"` 由 C 方言规则
处理；当前 C11 规则仍在补齐及验证。命令行也可使用
`naru build main.c --rules dialects/c11.stx --frontend c11.frontend --relation c11.emit_program --unit program`。
`--frontend` 覆盖项目中的关系，重复 `--frontend-option key=value` 覆盖对应前端
选项。核心不会协调独立方言的语言行为；同级规则同时匹配时仍报告冲突。

前端选项环境包含 `project_directory` 及 `target_configuration`。后者是与原生
后端一致的目标 JSON，供 `target.toolchain` 查询目标事实和已安装的 SDK 路径。
C 的完整验收目标、系统标准库来源与当前缺口见 [C11 方言](c11.md)。

规则与解析步数、递归深度均可配置；CLI 的 `--rule-budget`、`--parse-budget`、
`--rule-depth`、`--parse-depth` 覆盖项目值。步数默认 1000000，深度默认 256，
深度范围为 1..1024；迭代原语适合很长的规则链。
步数必须是 1 到 1,000,000,000 的整数：

```toml
[limits]
rule_steps = 100000000
parse_steps = 100000000
rule_depth = 512
parse_depth = 512
```

这些是资源预算，独立于语言语义。线性扫描或遍历应使用 `list.fold`、
`list.unfold`、`tree.fold` 或 `rule.iterate`，提高步数和深度不会消除递归成本。

## 规则包

```toml
[package]
name = "my-language"
version = "1.2.3"

[dependencies.std]
path = "../naru-stdlib"
package = "naru-stdlib"
version = "~0.2.0"

[exports]
my_language = "rules/main.stx"
```

应用写 `lang = { path = "../my-language", version = "^1.2.0" }`，再选择
`dialects = ["std/base", "lang/my_language"]`。导出名必须等于文件中的 `mod`
身份，不会创建重命名的关系或构造器。项目自身的导出可直接使用 `"my_language"`。
STX 的 `use base;` 通过已解析的项目导出目录找到 base，再按规则模块可见性链接。

解析器遍历传递依赖，同一实际清单在菱形依赖中只解析一次，并检测环、缺失文件、
包名不匹配、版本不匹配和导出冲突。一个构建只能包含一个相同包名的项目，
规则模块身份也必须唯一；不支持同名包的多版本并存。

稳定版本须为 `major.minor.patch`，支持精确版本、`*`、`^` 和 `~`。
`^1.2.3` 接受相同 major；`^0.2.3` 接受相同 minor；`^0.0.3` 仅接受该版本。
`~1.2.3` 接受相同 major/minor 且不低于指定 patch。编译器解析本地 path 依赖；
[包管理器](packages.md) 可从 JSON registry 或 Git 自动获取来源、锁定提交及内容，
并生成这些本地依赖。`naru.ps1 build` 自动先完成获取；`naru.exe` 自身不联网。
版本约束暂不支持 prerelease 或比较符范围。

多个方言有同名关系时，使用限定名，例如 `ownership.analyze`。需要统一程序
入口时由规则包提供聚合关系；`std/standard` 的 `standard.emit_program` 已支持
基础函数和 ownership/resource 检查项共存。项目依赖系统不替代方言自身的组合语义。

## 锁文件和冻结编译器

`resolve`、`build`、`freeze` 原子生成或更新 `Naru.lock`。锁文件记录包名、版本、
依赖边，以及所有清单和实际参与链接的 STX 模块的 SHA256。文件路径相对于根项目，
所以项目和依赖一起搬移后仍可 `--locked` 构建。未选中的导出和用户程序内容不影响
锁中的规则指纹；所有声明的导出文件仍受输出覆盖保护。

`--locked` 要求锁文件已存在且与本次解析一致；失败不更新锁或产物。它是依赖输入
快照，不是编译缓存，也不记录原生对象、库或已安装 SDK 的内容散列。锁文件可调整
空白格式，条目和字段顺序使用生成器的规范顺序。规则包自身也可执行 `resolve`，
只解析包依赖，不强制设置应用语法入口。

```powershell
python tools\freeze\build.py --core target\naru.exe --project examples\ffi --locked --output target\specialized-externc
.\target\specialized-externc\target\naru.exe build --project examples\ffi --locked
```

冻结镜像固化所选规则及导入闭包。项目构建检查已冻结模块的指纹，使用原生匹配器和 effect 实现。已冻结模块内容改变时须重新冻结。

`--rules` 和项目引用可以追加动态模块，参与相同的 fallback 和冲突检查。项目须保留冻结组的依赖闭包；不传 `--project` 时使用内嵌方言组。详见 [固化说明](../tools/freeze/README.md)。

## 链接配置

```toml
[link]
runtime = "freestanding" # 或 crt-static、crt-dynamic
subsystem = "console"    # 或 windows
native_entry = "main"    # 仅 freestanding 使用
objects = ["native/bridge.obj"]
libraries = ["my_runtime", "native/explicit.lib"]
library_paths = ["native/lib"]
# 可选，默认通过环境、注册表和 Visual Studio Setup Configuration 自动发现：
# vc_tools_dir = "D:/VS/VC/Tools/MSVC/14.xx.xxxxx"
# windows_sdk_dir = "C:/Program Files (x86)/Windows Kits/10"
# windows_sdk_version = "10.0.xxxxx.0"
```

项目依赖贡献的对象、库、库目录及 IRDL/插件数组按依赖先于使用者的顺序合并。
运行时、入口、子系统和优化流水线等标量由根应用控制。原生源码需由其提供者
预先编译为兼容目标的对象或库，Naru 不调用宿主 C 编译器构建依赖。

库名可省略 `.lib`；显式路径按所在清单解析。搜索顺序为项目/CLI 库目录、`LIB`
环境目录、自动发现的 MSVC 和 SDK 目录。相同物理对象和库，包括硬链接别名，
只送入链接器一次。CLI 对应 `--link-object`、`--link-library`、`--library-path`、
`--runtime`、`--subsystem` 和上述 SDK 配置字段的连字符形式。
目标 JSON 对应数组名为 `link_objects`、`link_libraries`、`library_paths`，其路径
相对于目标 JSON。

默认 freestanding 使用 `/entry:main /nodefaultlib`，不需要安装 CRT 库。
CRT 模式让 LLD 选择原生 CRT 启动入口，并加入 MSVC、UCRT 和 kernel32 库；
需安装对应架构的 MSVC/Windows SDK 库文件，但不会调用 `vswhere`、Clang、
`lld-link` 或任何子进程。Windows EXE 链接仍通过进程内 LLD COFF；其他目标
可发射对象，但尚未实现其他平台的可执行文件链接。

`--report` 记录实际解析的对象、库、搜索目录、运行时和发现的 SDK 版本。
链接失败保留已有产物；输入对象、显式库和搜索后解析的库都受输出/报告覆盖保护。
自定义 MLIR 的 IRDL、方言插件、pass 插件、设备 pipeline 和产物选择继续通过
`[backend]` 配置，不要求设备目标经过 LLVM 或原生链接器。

配置接受上述表、字符串、字符串数组、依赖内联表与 `backend.opt_level` 整数。
重复键、未知字段和错误类型会报错；这不是完整 TOML 实现。
