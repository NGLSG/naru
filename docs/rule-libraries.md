# 可组合的语言规则库

项目选择 `std/standard` 即可在普通 `.nru` 中使用下面这些规则。程序无需引用 `.stx`。可以单独选择导出模块，也可以把用户规则和标准组一起加入项目的 `language.dialects`。

| 模块 | 已接入普通函数的能力 |
| --- | --- |
| `records` | 名义结构体、别名、字段读取与修改、pair、聚合传参与返回、可变聚合存储 |
| `generics` / `traits` | 显式类型参数、按需实例化、实例缓存、递归泛型、开放能力证据与约束 |
| `variants` / `patterns` | 用户枚举、option/result、标签和载荷、模式绑定、重复分支与穷尽性检查 |
| `control` | void、表达式语句、范围循环、break/continue、unless、短路逻辑、移位、数值转换 |
| `operators` | 用户运算符函数、异类型实参、独立结果类型、开放候选与实现策略、动态扩展 |
| `affine` | owned、move、共享/独占借用、真实地址和解引用、借用结束、分支合流、循环状态检查 |
| `arrays` / `shapes` | 定长数组、动态索引与赋值、越界 trap、向量构造和算术、现有向量/张量投影 |
| `functions` / `closures` | 函数值、高阶参数、间接调用、显式值捕获闭包、嵌套闭包、闭包环境与调用 |
| `defer` | 注册时捕获调用目标和实参，按逆序清理，覆盖作用域结束、return、break、continue |
| `pipeline` / `tree` | 多库阶段注册、依赖排序、通用项遍历，保留未知库的构造器 |
| `layout` / `cfg` | 根据大小和对齐事实组合对象布局，预声明标签、跳转和整数分派；独立目标规则可复用 |

这些能力没有变成 Vyx 核心的关键字或类型分支。检查、类型表示、存储和 lowering 都在库的开放关系中组合。核心新增的 `collect` 和 `list.fold` 是通用规则工具。

## 完整工程示例

[`examples/emergence/main.nru`](../examples/emergence/main.nru) 同时使用结构体、别名、枚举、模式、泛型、用户 `cents` 类型、能力证据、数组、循环、函数值、闭包、所有权、借用、defer 和 C 接口。`demo.stx` 增加 `twice(...)` 并声明自己的准备阶段；生成程序打印一行文字并返回 42。

```powershell
.\target\naru.exe build --project examples\emergence --locked
& .\examples\emergence\target\demo.exe
$LASTEXITCODE # 42
```

整个方言组可以固化为一份编译器：

```powershell
python tools\freeze\build.py --core target\naru.exe --project examples\emergence --locked --output target\specialized-emergence
.\target\specialized-emergence\target\naru.exe build --project examples\emergence --locked
python tests\emergence.py --compiler target\specialized-emergence\target\naru.exe --frozen
```

## 阶段组合协议

多个库可以贡献 `pipeline.steps()`。普通 effect 调用依然拒绝重叠；只有显式 `collect("pipeline.steps", [])` 收集所有匹配的事实。收集保持注册顺序，有普通匹配时排除 fallback；守卫仍须纯净。

```text
effect pipeline.steps()
    => pipeline.Step("my-desugar", [], ["generics", "records"], "my_rules.prepare");
```

三参数 `Step(name, after, relation)` 指定前置阶段；四参数 `Step(name, after, before, relation)` 同时指定后续阶段。未安装的顺序约束被忽略，已安装阶段形成依赖图。重名和环会诊断失败，实际执行使用迭代的 `list.fold`，避免阶段数量增加整个分析的调用深度。

标准组的依赖顺序是泛型实例化、名义类型解析、运算符声明、闭包提升、defer 展开、affine 检查、字符串提升，然后进行整组基础类型检查和 MLIR lowering。用户库通过声明顺序加入这些阶段。运算符声明与候选扩展见 [运算符规则](operators.md)。

## 开放接口

- 类型库扩展 `types.repr`、`traits.accepts` 和 `types.solve_one`。
- 表达式库扩展 `base.hint`、`base.check` 和 `base.lower`。
- 语句库扩展 `base.continue`、`base.check_body`、`base.prepare_storage`、`base.lower_flow` 和 `base.flow_terminal`。
- 聚合库扩展 `records.aggregate`；基础存储提供可替换的分配、读和写协议。
- 可调用值扩展 `base.signature_params`、`base.signature_result`、`base.call_checked` 及 `functions.invoke`。
- 模式库扩展 `patterns.pattern`、`patterns.exhaustive`、`patterns.bound_names`。闭包与所有权分析使用相同绑定作用域。
- 添加语句时也应定义 `control.append`、`control.range_continues`，并让需要遍历它的准备阶段保留其控制流与作用域。

字段规则可写成 `` `$value:expr . $field:ident` ``。捕获类型中的相邻点表示限定类别，例如 `library.expr`；有空格的点是源语法字面量。中缀规则支持 `[90,left,fallback]`，普通匹配优先于 fallback，同级重叠仍报错。

## 语义范围

泛型目前需要显式类型实参，能力证据不等于完整 trait 方法系统。枚举每个分支有一个载荷，多个字段可以用结构体表示。闭包显式列出按值捕获的名字，注册 defer 时也捕获调用目标与实参。

affine 实现的是普通函数内的顶层所有权和词法借用。借用不能复制成另一份绑定或无生命周期契约地逃逸函数；含 owned/ref 的聚合和闭包捕获需要尚未实现的部分移动及生命周期协议，因此会拒绝。循环要求外层所有权状态在下一轮前恢复。它还没有自动析构、跨函数生命周期推断或完整 Rust 借用模型。

数组索引按现有整型转换规则规范化为 64 位，再检查边界；SSA 数组的动态读取会临时存储并恢复栈，避免循环反复增长栈。可变数组直接访问其现有存储。向量构造当前支持一维，跨浮点格式转换支持 f16/f32/f64。源类型能表示的其他 MLIR 格式，仍受目标和 pass 的 lowering 能力约束。

堆容器、异步运行时、完整泛型推断、自动析构和跨函数生命周期尚未实现。实际 MLIR 方言/pass 的注册继续通过 IRDL 或原生插件；STX 可以选择、组合和生成它们的操作，并未替代其底层实现。

## 验证

`python tests/emergence.py` 在禁止子进程且 PATH 为空的 Windows Job 中编译，覆盖 O0/O2 原生行为、非法程序、失败产物保护、越界、清理顺序和项目组合。`target/emergence-tests.json` 保存动态结果；冻结结果保存在 `target/emergence-frozen-tests.json`。

`.\test.ps1 -ComposedAot` 运行回归并只固化这一份完整方言组；`-Aot` 另外构建各独立规则验收夹具。
