# 方言调试记录（2026-10-12）

本记录对应 2026-10-12 的 B、Pascal 和 C11 动态规则。修复涉及类型、存储、树改写及控制流。当前范围见各方言说明。

## 已复现的缺陷与修复

| 方言 | 缺陷与后果 | 修复和回归 |
| --- | --- | --- |
| B | 下标重复缩放；赋值检查直接生成 IR，报 SSA 错误 | 统一字地址，只在 word_ptr 乘 8；vector_read/write |
| B | auto v[0] 被当成标量，访问零地址 | 标量和向量用不同构造器；vector_zero |
| B | !/~ 重复包装已检查操作数，无法 lowering | 直接 lower 操作数；not/complement |
| B | 比较值仍是 i1，覆盖 i64 留下旧高位：1024 → true 得到 1025；直接返回类型错误 | 比较统一为 i64；comparison_overwrite/return |
| B | 复合比较赋值符号扩展 true 为 -1 | 零扩展为 1；compound_comparison |
| B | 条件常量默认 i32 不被接受；?: 的 select 执行两个分支副作用 | 归一化字值，用 SCF 分支区域；ternary_yes/no |
| B | extrn 列表只处理第一个名字 | 遍历全列表，保留已有绑定；extrn_list |
| B | 整程序漏注册 char/lchar；跨 item 字符串重名；未对齐地址可能被截断 | 共享播种，跨 item 驻留计数，8 字节对齐；strings_items |
| B | lchar 写只读字符串；char 对高位字符符号扩展 | 可写存储、字符零扩展；string_mutation/char_unsigned |
| B | 接受 09；外部初始化不接受 052；负初值未检查 | 验证每个八进制位，补齐常量/尺寸路径、初值检查；octal_global/invalid_octal/global_negative |
| B | 普通移位产生未经检查的 Binary；全局类型提示缺失 | 独立检查构造器、逻辑右移、声明类型提示；shift_left/zero_fill |
| B | exit 未声明且 CRT 签名错误 | 声明 void exit(i32)，宿主状态 0；exit |
| Pascal | case 命中后丢掉后续语句；选择器重复执行；接受重复标签 | 单次求值、公共续体、标签唯一性；case 系列 |
| Pascal | 函数结果改写不认识未检查的 write/case 等节点 | 共享 tree.rewrite 保留未知构造器；case_selector_once |
| Pascal | 大小写敏感；const 可赋值 | 只折叠标识符 token；只读常量绑定；casefold/const_assignment |
| Pascal | for 在整数端点继续加减，死循环；上下界求值顺序反了 | 端点先退出，顺序求值一次，私有名字隔离嵌套循环；for 系列 |
| Pascal | / 在无期望实数类型时整除；div/mod 无整数约束 | 区分语义构造器、实除转 f64；real_division/div_real_rejected |
| Pascal | 输出检查丢失返回类型，续体拼接不接受 Return | 保留结果类型与终止节点；原始 showcase、输出后 halt |
| Pascal | 程序变量/常量被放进 main 局部，子程序引用报未绑定 | 共享静态对象与声明环境常量；global_variable/global_const/read_write/boolean_real |
| Pascal | const 接受函数调用或可变值，局部常量别名缺少稳定事实 | 检查字面量/先前常量并保存只读已检查值；const_alias/local_const/runtime/assignment |
| C11 | ?: 丢失指针限定符，把 void* 错选为对象指针；缺少空指针、聚合和 void 分支 | 补齐选择类型、限定符合并与 void 区域；conditional 系列 |
| C11 | sizeof("abc") 返回 8；字符串过早衰减 | 驻留引用保留数组长度，sizeof/取地址使用数组类型；sizeof/string_array_address 系列 |
| C11 | 函数指针与 NULL 混同普通 void* 转换；隐式函数地址→void* 被当成标准兼容 | 标准 NULL 转换与比较独立；宿主互转为可选组合模块；function_null/interop 系列 |
| C11 | 有序函数指针和 void* 比较缺少对象类型约束 | 按 N1570 §6.5.8p2 拒绝；ordered 指针诊断 |
| C11 | 1-1 作为静态空指针初值可用，普通初始化/参数/返回/比较却被拒绝 | 指针上下文先识别整数常量表达式，再复用同一常量求值器；null_ice 系列 |
| C11 | sizeof(expr) 不进入常量事实；三元常量求值执行未选中的除零分支 | 保留未求值操作数的对象类型，分支类型检查与求值分离；null_ice_sizeof/lazy_select |

B 外部向量目前只有数据数组，没有独立的可重绑定地址槽。旧实现的
`v = ...` 和 `&v` 实际指向元素 0，可能静默破坏数据。现在明确报错；
`v[n]` 读写仍支持。完整重绑定需要改变存储表示，尚未实现。

## 标准与宿主扩展

C11 语义依据 [WG14 N1570](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf)
§6.3.2.3、§6.5.3.4、§6.5.8、§6.5.15、§6.6。Pascal for 依据 ISO 7185
§6.8.3.9；B 以收藏的 MH-TSS 手册为锚。

未经改写的 TinyExpr 将函数地址存入 const void*。压力测试显式组合
`dialects/c11/function-pointer-interop.stx`，采用当前 Windows x64 LLVM
指针 ABI 提供该扩展，原始源文件与校验和不变。默认 C11 规则仍保留
相应诊断。cJSON 的函数指针 NULL 用标准规则处理。

void* 的有序比较，当前 Clang 即使开启 pedantic 仍接受；该诊断用例
直接依据 N1570 §6.5.8p2，报告标记参考编译器差异，没有将其记为
Clang 验证通过。有效 C 用例均对照独立的 Clang 原生程序。

整数常量零与运行时的零值保持区别：`1-1`、枚举差值、固定对象的
`sizeof` 差值、整数条件表达式可以用于对象/函数指针；普通变量、
`const int` 对象以及 `(x=0)` 都不能因此获得隐式指针转换。
相关用例同时验证初始化、赋值、参数、返回、比较、条件分支和 `(void*)0`。
普通运行时算术不调用这条常量求值路径，避免改写运行时副作用。

## 重现

```powershell
python tests/dialect_debug.py
python tests/c11_stress.py --reference D:/LLVM/bin/clang.exe --memory-mib 1536 --timeout 45 --report target/c11-debug-stress.json
```

`tests/dialects/regressions.json` 保存最小复现和原始例子路径。
`target/dialect-debug.json` 保存 O0/O2 运行结果、诊断、时间、提交峰值及
编译器/用例/规则 SHA-256；测试前后规则必须相同。每个 Naru 编译进程
禁止子进程、内存限制 512 MiB，运行限制 64 MiB，构建顺序执行。
真实 C 项目使用单独的 1536 MiB 上限。

该次回归包含 95 个用例：B 28、Pascal 24、C11 43，各运行 O0/O2，
共 190 项全部通过。第二轮增加 26 个用例，该轮最小用例编译的提交
峰值约 50.9 MiB；这不是
运行时性能或完整项目内存测量。完整 C11 压力结果另存于
`target/c11-debug-stress.json`。

完整 C11 压力测试 12/12 通过，包括系统头文件、CRT、多翻译单元，以及
源码未改写的 TinyExpr/cJSON。TinyExpr 使用上文列明的可组合宿主扩展。
现有 C 规则组合检查另有 88/88 通过，覆盖布局、限定符、枚举、跳转、
switch、符号属性与拒绝诊断，结果为 `target/c11-debug-composition.json`。

## 仍需解决

- B：外部向量地址槽、历史位宽、多字符打包、完整运行库。裸地址和
  向量没有运行时越界保护，当前字地址模型也不等于原机器 ABI。
- Pascal：完整声明顺序/同块重名和嵌套作用域、var 参数、
  集合、记录、文件、字符/字符串类型；`''` 转义、声明段缩写、const
  完整表达式约束与 const 名 case 标签尚未补齐。
- C11：该快照尚缺完整常量表达式、声明、位域、聚合 ABI、VLA、原子和复数。后续实现见 [C11 方言](c11.md)，测试方法见 [条款验收](c11-conformance.md)。
