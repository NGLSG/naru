# 编译器实现

Naru 核心负责装载规则、解析结构化项、求值、模块解析及 IR 构造。语言特性由 `.stx` 模块实现，用户项目选择规则组和编译入口。

## 编译流程

```text
项目配置 → 规则装载 → 前端 → 分析与改写 → MLIR → 目标 pass → 产物
```

项目的 `package.entry` 指定源码路径，`language.frontend` 选择前端关系，入口不限制文件扩展名。默认前端使用语法模板和 Pratt 解析；C、B、Pascal、BASIC 使用各自的词法或源码组织规则。

`syntax` 将 token 映射到结构化项，`effect` 对这些项执行匹配、分析和改写。整程序模式先收集声明，再检查函数和生成 IR，因此基础库支持前向调用与递归。程序模块由核心加载，导出、可见性及跨模块语义由语言库决定。

构建与命令行用法见 [building.md](building.md)，项目字段见 [projects.md](projects.md)。

## 规则求值

项、列表和环境不可变。构造器、字符串和精确整数按结构比较；SSA 句柄、卫生符号、环境和逻辑变量保留身份。

规则分派按关系、参数个数和首参数形状建立索引。普通匹配优先于 fallback，同级多个匹配报歧义。纯守卫读取上下文，提交关系只在唯一候选选定后执行。解析结果按类别、位置、优先级和不可变上下文缓存。

核心提供词法绑定、持久环境、列表与树迭代、结构统一、精确数值及 IR 工具。接口和预算规则见 [rule-system.md](rule-system.md)。

## 语言库组合

[base](../dialects/base.stx) 提供函数、局部变量、表达式和控制流；其他库通过开放关系加入类型表示、表达式检查、存储、调用和 lowering。`pipeline.steps` 收集各库的阶段声明，按依赖排序执行。

[组合工程](../examples/emergence/) 同时使用结构体、泛型、枚举、运算符、闭包、所有权、defer 和 C 接口。多个方言共同装载时使用相同的冲突检查；跨语言转换需要对应规则。扩展接口见 [rule-libraries.md](rule-libraries.md)。

## 进程内后端

前端通过带显式长度的 C ABI 与 `naru_mlir_backend.dll` 交互。MLIRContext、模块、操作、region、block 和 SSA 值均使用真实 MLIR 对象；整个模块无需经文本重解析。

`emit` 构造并验证 MLIR。`build` 使用 PassManager 执行管线并逐 pass 验证，CPU 目标继续导出 LLVM IR，经优化、TargetMachine 对象发射和 LLD 链接生成程序。成功后替换最终产物，失败保留原文件。

目标可输出 MLIR 文本、bytecode、LLVM IR、对象或 Windows EXE。自定义设备通过 IRDL 或原生插件注册方言，由目标配置选择 pass 和产物。见 [后端接口](../backend/README.md)。

## AOT 固化

冻结器将语法匹配、结果构造、effect 模式和静态右侧表达式生成为 Vyx 函数。生成的编译器内嵌规则，无需再次读取对应 `.stx`；共享解析调度仍处理类别递归与优先级。

冻结编译器可以追加动态模块，两者参与同一套分派、fallback 和冲突检查。已冻结模块只能按原内容重选。扩展后的规则组可以再次固化。生成流程及清单格式见 [tools/freeze/README.md](../tools/freeze/README.md)。

## 内存与执行

列表共享 tail，环境使用持久哈希树。规则回调拥有嵌套分配作用域，回收未从结果或 IR 副作用逃逸的临时节点、边和环境索引。树遍历与长迭代使用显式工作栈；arena 的整数日志使用独立活动区间。

回调以外的解析和求值临时值仍保存在编译 arena。规则步数、解析步数和递归深度分别受限；长序列应使用迭代原语。独立构建和测试任务可以并行，单个 Engine 中有顺序要求的回调按序执行。

日志使用 Vyx `std/logger`，写入 stderr。AST、JSON 和 IR 写入 stdout。`--log-level debug` 可查看装载与求值信息。

运行时基准位于 [benchmarks/runtime](../benchmarks/runtime/)，使用 base 语法编写程序，与 Vyx、C++ 和 Rust 的同类函数比较。规则解释器与编译内存测量使用 `tests/*_perf.py`；两类结果分别记录。当前缺陷见 [status.md](status.md)。
