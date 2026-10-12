# Naru

Naru 0.2 是用 Vyx 实现的语言研究型 AOT 编译器。核心提供规则装载、结构化项、规则求值、模块和通用 MLIR 构造边界；具体语言特性由 `.stx` 方言规则组合得到。用户程序由所选方言解析，项目选择方言组后即可直接使用其语法。

入口路径不限制扩展名。`package.entry` 可以是 `main.c`、`main.nru` 或其他文件名；项目选择的规则及 `language.frontend` 决定如何编译。C 方言的源码示例在 `examples/c11/main.c`，当前 C11 实现仍在补齐和验证中。

C11 验收使用安装的系统头文件和 CRT，以及固定版本、未经改写的 TinyExpr 和 cJSON。`python tests/c11_stress.py` 保存真实失败及资源数据；当前尚不能编译完整 C11 项目。共享前端设施和未完成范围见 [C11 压力测试](docs/c11.md)。

当前版本已实现 `.nru → 规则解析与分析 → MLIR → 优化 → LLVM 对象发射 → LLD 链接`，整个编译后端运行在 Naru 进程内，也能保留自定义 MLIR 方言作为目标产物。规则可以动态装载，或将语法匹配和 effect 代码 AOT 固化为下一份编译器。运行已构建的编译器只需要 `naru.exe` 和同目录的 `naru_mlir_backend.dll`。

## 构建与运行

在 PowerShell 中进入本项目。编译脚本默认使用指定的 Vyx SDK，也支持 `-VyxSdk` 或 `VYX_SDK_ROOT`：

```powershell
.\build.ps1 -Release
.\target\naru.exe parse examples\answer.nru
.\target\naru.exe emit examples\answer.nru -o target\answer.raw.mlir
```

根目录 `Naru.toml` 通过 `[dependencies]` 引用 `dialects` 规则包项目，再选择导出 `std/base`，因此示例程序无需引用规则文件。直接执行 `naru build` 会查找项目入口和输出目录。也可显式选择方言：

```powershell
.\target\naru.exe parse examples\answer.nru --rules dialects\base.stx
```

项目引用支持传递依赖、稳定版本约束、导出身份检查和 SHA256 锁文件；一个项目可同时选择多个方言。外部对象和库由 `[link]` 配置，CRT 模式自动发现 MSVC/Windows SDK 库，链接仍在进程内完成：

```powershell
.\target\naru.exe resolve --project examples\ffi
.\target\naru.exe build --project examples\ffi --locked
& .\examples\ffi\target\ffi-demo.exe # 打印文本，返回 42
```

完整配置见 [项目与链接](docs/projects.md)，C 语法和 ABI 范围见 [C interop](docs/externc.md)。[包管理器](docs/packages.md) 支持 JSON 注册表、按名称查找安装、Git 链接、方言库模板与离线锁定获取，安装后复用编译器的 path 依赖解析。CRT 链接需要已安装对应架构的 Windows SDK/MSVC 库。

```powershell
.\naru.ps1 pkg init target\my-language --name my-language
.\naru.ps1 pkg fetch --project target\my-language
.\naru.ps1 resolve --project target\my-language
.\naru.ps1 build --project target\my-language --locked
```

`naru.ps1` 是包管理入口，使用 Python 3.11+，Git 仓库获取还需要 Git；原生 `naru.exe` 继续独立工作。

开发构建使用当前工作区 `.tools/mlir` 下固定版本的 MLIR SDK。新工作区先执行 `python tools/mlir/bootstrap.py`，准备 Clang、CMake、Ninja 和 Visual Studio C++ 构建环境，再执行 `build.ps1`；首次构建会准备相同版本的 LLD 静态库。已构建的编译器可直接生成原生程序：

```powershell
.\target\naru.exe build examples\answer.nru --target exe -o target\answer.exe --report target\answer.report.json
& .\target\answer.exe
$LASTEXITCODE # 42
```

安装器下载并校验约 563 MB 的 SDK。Naru 前端由 Vyx 的 LLVM 22 工具链编译；MLIR 24 和匹配版本的 LLVM/LLD 静态链接进后端 DLL，两者通过带显式长度的 C ABI 和不透明句柄交互。`.nru` 生成的操作图直接构造成真实 MLIR 对象，不通过整个模块的文本重解析。编译器运行时无需 Python、Clang、`mlir-opt`、`mlir-translate`、`lld-link` 或 Vyx SDK。

`package.ps1` 生成 `target/dist/naru-windows-x86_64` 和 ZIP，包含编译器、规则组、示例、目标配置和依赖许可证：

```powershell
.\package.ps1
.\target\dist\naru-windows-x86_64\naru.exe build --project .\target\dist\naru-windows-x86_64\Naru.toml --target exe -o target\distributed-answer.exe
```

## 规则组合

标准组现在包含结构体、泛型和能力约束、枚举与穷尽模式、数组和向量算术、范围控制流、函数值与闭包、普通函数的 affine 所有权及 defer。完整组合工程和开放接口见 [可组合规则库](docs/rule-libraries.md)。

用户可在 `.nru` 中声明 `operator+` 等运算符函数，左右参数类型和结果类型可以独立。候选与实现策略由 [运算符规则](docs/operators.md) 提供，动态方言可扩展冻结语法的类型含义。

```powershell
.\target\naru.exe build --project examples\emergence --locked
& .\examples\emergence\target\demo.exe # 打印文本，返回 42
```

`fn`、`let`、`return`、算术和类型检查都来自 [base.stx](dialects/base.stx)。类型表示和数值策略分别由 [types.stx](dialects/types.stx) 与 [numbers.stx](dialects/numbers.stx) 定义：

```text
mod base;
use types;

syntax expr `$n:int` => Int($n);
syntax expr[50,left] `$a:expr + $b:expr` => Add($a, $b);
syntax item[fallback] `fn $name:ident($params:parameters) -> $result:typename { $body:body }`
    => TypedFunction($name, $params, $result, $body);

effect opcode("div", Signed($width)) => "arith.divsi";
effect opcode("div", Unsigned($width)) => "arith.divui";
```

`syntax` 将 token 模板映射到带标签的结构化项。`$name:category` 捕获子语法，方括号声明运算优先级和结合性；前缀运算符也遵循绑定强度。`effect` 按结构匹配调用并执行右侧表达式，可用 `when` 添加纯条件。`[fallback]` 显式声明后备规则，同级的多个匹配仍报歧义，规则装载顺序不决定语义。关系、类型、所有权状态及约束均可使用任意用户构造的项。详见 [规则系统契约](docs/rule-system.md)。

核心规则工具提供词法局部绑定 `bind`、卫生身份 `symbol`、持久环境 `env.*`、列表组合与关系调用 `list.* / apply`，以及 `logic.fresh/unify/resolve`。统一支持任意构造器、结构类型和列表，并执行 occurs check；失败保留原替换环境。规则算术采用精确整数，不再限制为 i32。浮点工具按 MLIR 格式和明确舍入模式转换，返回 IEEE 状态，由规则库选择溢出与精度策略。

基础类型库提供 `bool`、`i8…i128`、`u8…u128`、任意位宽 `i<N>/u<N>`、IEEE 浮点、`bf16`、`tf32`、MLIR 的 FP8/FP6/FP4 格式，以及向量、张量和元组类型。数值支持基数、分隔符、指数、类型后缀和上下文定型；越界字面量和有损的隐式类型混合会被规则拒绝。向量和张量支持多维 shape，例如 `vector<2 x 3, f32>`；加载 [shapes.stx](dialects/shapes.stx) 后，`a[1]` 可 lowering 为 `vector.extract` 或 `tensor.extract`（当前 tensor 抽取要求 rank-1）。整数运行时加减乘采用 MLIR 模运算语义，除法保持 arith 的除零和溢出前提；未实现自动运行时检查。

`--unit program` 把整个程序项列表交给指定关系。基础库先收集函数签名、检查全部函数，再 lowering，因此支持参数、局部变量、卫生遮蔽、前向调用和递归。根项目已选择 `emit_program`：

```powershell
.\target\naru.exe build examples\typed_calls.nru --target exe -o target\typed-calls.exe
.\target\naru.exe emit examples\numeric_types.nru
.\target\naru.exe emit examples\numeric_types.nru --rules dialects\shapes.stx --unit program --relation emit_program
.\target\naru.exe emit examples\money.nru --rules dialects\money.stx --unit program --relation emit_program
```

[money.stx](dialects/money.stx) 仅通过规则扩展就定义 `cents` 类型、字面量检查、操作选择和 MLIR 表示，不需要修改核心。

[externc.stx](dialects/externc.stx) 在同一套 `base` 上扩展 `extern "C"` 声明、`char`、`ptr`、`*T`、`null` 和静态 UTF-8/NUL 字符串。扩展已有关系时写 `effect base.lower(...)`、`effect types.repr(...)`；裸写 `effect lower(...)` 会定义当前模块自己的关系。C 标量调用已与独立 C 程序在 Windows x64 的 O0/O2 下链接运行验证。实际调用外部函数时先生成对象文件，再由宿主 C 工具链链接；当前 EXE 链接器尚不能添加外部库。详见 [C 互操作规则](docs/externc.md)。

`.stx` 的 `use` 导入规则模块，并在链接阶段解析名称；规则歧义会报错。`.nru` 的 `mod/use` 加载程序模块图，依赖文件先于使用者处理。`source.modules()` 向规则提供模块名、路径、导入和局部项，供语言库定义导出与可见性。当前基础库的函数采用整个程序组的平坦命名空间。

方言可以继续组合，而不需要复制规则。仓库提供 [standard.stx](dialects/standard.stx) 作为一个聚合入口，它依次导入 `base`、`ownership`、`resources`、`loops`、`unless` 和 `shapes`；用户只需选择这个入口，`.nru` 就能同时看到这些规则：

```powershell
.\target\naru.exe parse examples\typed_calls.nru --rules dialects\standard.stx
.\target\naru.exe check examples\ownership\valid.nru --rules dialects\standard.stx --relation ownership.analyze
.\target\naru.exe check examples\ownership\multiple_resources.nru --rules dialects\standard.stx --relation resources.analyze
.\target\naru.exe check tests\fixtures\composed.nru --rules dialects\standard.stx --relation standard.analyze --unit program
.\target\naru.exe build tests\fixtures\composed.nru --rules dialects\standard.stx --relation standard.emit_program --unit program --target exe -o target\composed.exe
```

这里的 `imports` 是核心的规则/程序模块装载设施，不是必须单独复制的一套语言特化。多个方言可能定义同名关系，例如 `ownership.analyze` 和 `resources.analyze`；裸写 `analyze` 会得到歧义诊断，使用带模块名的关系即可。若项目需要单一入口关系，可以在自己的 `.stx` 中写一个 facade 规则，按明确顺序调用这些关系。
`standard.stx` 已提供这样的 facade：它逐项分析 ownership/resource 项，把基础函数项收集后交给 `base.emit_program`，所以 `composed.nru` 能在同一项列表中同时包含 `check` 和 `fn`。

[alternate.stx](dialects/alternate.stx) 用 `def` 构造同一个 `base.Function`，复用原有 lowering。下面两种源语法生成相同的 MLIR：

```powershell
.\target\naru.exe emit examples\answer.nru --rules dialects\base.stx
.\target\naru.exe emit examples\alternate.nru --rules dialects\alternate.stx
```

所有权研究示例使用普通状态项 `Owned/Moved/MaybeMoved`，定义顺序传递与分支合流。[unless.stx](dialects/unless.stx) 扩展表面语法并复用分析，[loops.stx](dialects/loops.stx) 进一步扩展已有关系，用递归和相等判断计算有限状态不动点：

```powershell
.\target\naru.exe check examples\ownership\loop_valid.nru --rules dialects\loops.stx --relation analyze
.\target\naru.exe check examples\ownership\loop_invalid.nru --rules dialects\loops.stx --relation analyze
```

第二个程序会因循环后续迭代可能使用已移动资源而失败。该有限状态示例分析单个抽象资源；另一份 [resources.stx](dialects/resources.stx) 通过持久环境实现多资源身份、共享/独占借用、显式结束借用和保守的分支合流。资源只在一侧移动时，合流状态会变成 `MaybeMoved`；借用必须在每条分支上结束，才能继续使用资源。该方言仍未集成基础库的运行时分配、析构、跨函数借用或完整控制流生命周期推断。任意递归规则不保证收敛，核心提供求值步数和深度上限。

## MLIR 与优化

`emit` 构造并验证真实 MLIR，再输出通用操作格式。`build` 使用进程内 `PassManager`，逐 pass 验证，成功后原子替换最终产物。默认优化是 `canonicalize,cse`；CPU 目标继续转换到 LLVM IR，执行 LLVM 优化流水线，由 `TargetMachine` 发射对象，调用 LLD 库链接。`20 + 22` 和用户程序中的 `2 + 8 * 5` 都可折叠为常量 42，O0/O3 原生程序实际返回 42。

自定义设备方言可通过 IRDL 或原生插件注册，目标包选择 pass pipeline 和产物类型：

```powershell
.\target\naru.exe build examples\device.nru --rules dialects\custom_device.stx --target backend\device-target.json -o target\device.mlir
.\target\naru.exe build examples\answer.nru --pass-pipeline 'builtin.module(canonicalize,cse)' -o target\answer.opt.mlir
.\target\naru.exe build examples\sum_loop.nru --rules dialects\base.stx --unit program --relation emit_program --target exe -o target\sum-loop.exe
.\target\naru.exe opt backend\examples\fusion.mlir --target backend\fusion-target.json -o target\fusion.mlir
```

设备示例会验证并保留 `naru_device` 操作，无需转成 LLVM。后端验收另包含真实 affine 循环融合案例：两轮循环合为一轮，中间缓冲区及对应读写消除。这是后端优化用例；当前基础源语法尚不能表达该数组程序。自定义操作的优化语义仍由方言接口及专用 pass 提供。

通用构造接口支持 SSA 结果、类型、属性、嵌套 region、多块 region、块参数、控制流后继和回边。`base.stx` 使用这些接口实现普通函数、可变局部变量、分支和循环，核心无需识别相应语法。`control_flow.stx` 仅保留为低层块参数和回边的后端验收夹具。支持输出 MLIR 文本、MLIR bytecode、LLVM IR、对象文件和 Windows 可执行文件。详见 [后端协议与自定义目标](backend/README.md)。

## AOT 固化规则

```powershell
python tools/freeze/build.py --core target/naru.exe --rules dialects/base.stx --output target/specialized-base
.\target\specialized-base\target\naru.exe build examples\answer.nru --target exe -o target\frozen-answer.exe
python tools/freeze/build.py --core target/naru.exe --rules dialects/money.stx --output target/specialized-money
python tools/freeze/build.py --core target/naru.exe --rules dialects/resources.stx --output target/specialized-resources
python tools/freeze/build.py --core target/naru.exe --rules dialects/standard.stx --output target/specialized-standard
```

生成的编译器内嵌方言组，无需运行时读取其 `.stx`，也可以通过 `--rules` 或项目引用追加新模块。冻结部分保留原生匹配器和 RHS，动态部分参与同一套分派、fallback 和歧义检查；冻结模块内容不可替换。语法模板匹配、语法结果构造、effect 模式匹配和静态右侧表达式均生成为原生 Vyx 函数；共享 Pratt 调度仍处理优先级和类别递归。后端 DLL 一并复制，固化编译器运行时同样无需外部工具链。构建记录保存所有传递规则依赖及编译器、后端的哈希。完整进程的小样本测量受启动成本影响，不能据此宣称固化已显著加速。详见 [固化实现与验证](tools/freeze/README.md)。

基础、ownership、控制流、规则契约、多资源借用以及 `money` 自定义类型方言都已分别通过固化构建；组合入口也支持同一套固化流程。155 条数值、类型、借用和规则契约在动态编译器及相应冻结编译器之间保持一致。专门化编译器生成本身目前较耗内存和时间，代码规模随所选规则组增加。`target/specialized-*` 是隔离验收产物，不代表语言存在互斥模式；实际项目可以只维护一个聚合 `.stx` 并固化它。

## 性能现状

当前性能数据使用 warm filesystem、独立进程和 20 次交错测量，因此包含进程启动、规则装载和 MLIR 初始化，不能当作稳定吞吐基线。标准聚合方言在 `examples/typed_calls.nru` 上，动态编译器的解析中位数约 **17.6 ms**、whole-program emit 约 **39.4 ms**；冻结的 `specialized-standard` 分别约 **20.8 ms** 和 **41.4 ms**。小程序中冻结版本不一定更快，因为固化可执行文件更大，启动成本更高；它主要消除规则解析和动态 effect 匹配，源文件变大后才会显现收益。原始结果保存在 `target/standard-typed-timing-final.json`。

独立测量还记录了 `check` 和原生构建：动态中位数分别为 **28.15 ms** 和 **79.72 ms**，冻结版本为 **30.64 ms** 和 **81.80 ms**。同一个极小程序生成的 exe 启动并退出约 **6.8 ms**；这个数包含进程启动，程序本身只有常量计算，不能代表实际应用吞吐。完整数据见 `target/runtime-process-timing.json`。

此前 `sum_loop` 测量通过专用 `.stx` 直接生成算法的 MLIR，绕过了普通函数、局部变量与循环的语言链路；它只是一项后端微基准，不能作为 Naru 源语言与其他语言的性能比较。该报告已标注适用范围。

正式运行时基准位于 [benchmarks/runtime](benchmarks/runtime)。Naru 只加载 `base.stx`，使用普通 `fn`、参数、函数调用、`var`、赋值、`while` 和 `as` 编写 `.nru` 程序；Vyx、C++、Rust 提供相同参数和计算结构的手写函数。入口 `python benchmarks/runtime/run.py` 会编译、校验并交错测量 O2 程序，保留每次样本、完整命令、工具链、源码哈希及 Naru 的原始 MLIR/优化后 LLVM IR。标量变量使用可优化的栈槽；基准要求 O2 IR 中不再存在局部变量的分配、读写，并保留真正的循环。最新结果保存在 `target/base-runtime-benchmark/results.json`。

2026-10-10，Intel Core Ultra 7 265KF / Windows x64，各程序预热 3 次后交错运行 25 次的中位数如下。计时仍包含进程启动，但长循环降低了启动成本的占比；各结果均通过独立 Python 参考实现校验。

| 普通源码工作负载 | Naru | Vyx | C++ | Rust |
| --- | ---: | ---: | ---: | ---: |
| LCG，1 亿次 | 17.981 ms | 12.784 ms | 19.277 ms | 18.784 ms |
| LCG，10 亿次 | 112.089 ms | 52.019 ms | 115.741 ms | 114.042 ms |
| 双状态乘加/XOR，1 亿次 | 114.299 ms | 113.794 ms | 115.609 ms | 114.442 ms |

这些整数循环中，Naru 与 C++/Rust 的运行时接近；双状态循环也与 Vyx 接近。LCG 主调用路径中，Vyx 把 20 次线性递推归并为一组乘加，Naru/C++/Rust 归并 8 次，因此 Vyx 在该项领先。对照使用各自安装的工具链：Naru LLVM 24、Vyx/Clang 22、Rust 1.92 / LLVM 21；这不是控制相同 LLVM 版本后的纯前端对比，也不代表数组、内存管理、借用、浮点或大型应用的性能。

前端已使用共享 tail 的不可变列表、持久哈希环境、relation/arity/首参数形状索引和规则回调分配作用域回收。C 类型完成结果也按标签缓存；通用树遍历使用显式工作列表，避免宽列表和深树增加规则调用栈。2026-10-11 的同输入报告 `target/frontend-performance.json` 记录了回调临时项与系统头文件处理的内存改进，测量范围和限制见 [C11 基础设施](docs/c11.md)。这些结果测量编译器前端，不代表生成程序的运行时性能。每次 CLI 启动仍重新创建 MLIRContext、TargetMachine 和 LLD 状态；长驻 session/daemon、解析临时项生命周期及更大项目的稳定基线仍待实现。固化测量见 [说明](tools/freeze/README.md)。

## 验证与当前范围

```powershell
.\test.ps1
.\test.ps1 -Aot
python tests/path_lifetime.py
```

测试覆盖语法优先级、结合性、模块图、规则歧义与求值上限、所有权分支和循环、动态/AOT 结果与诊断一致性、真实 MLIR 验证与优化、多块 CFG、O0/O3 原生运行、原生方言与 pass 插件，以及失败产物和输入文件保护。后端验收把编译器放进仅允许一个进程的 Windows Job，并清空 PATH；实际执行成功证明编译流程无需创建子进程。详见 [测试说明](tests/README.md)。

这是具备编译和分发链路的研究型编译器。规则机制提供开放项、条件与后备规则、词法绑定、卫生身份、持久环境、精确数值、结构统一、多规则收集和迭代 fold；标准库已将名义聚合、显式泛型、模式、普通函数所有权、闭包和清理组合进同一条编译链。完整泛型推断、跨函数生命周期、部分移动与自动析构、堆容器、异步运行时、远程包管理和成熟性能基线仍未完成。Windows EXE 支持 freestanding、静态及动态 CRT 和外部对象/库链接；其他 LLVM 目标可输出对象，具体设备操作的 lowering 取决于目标方言和 pass 配置。
