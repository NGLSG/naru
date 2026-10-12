# C11 声明和解析作用域

块作用域 typedef 必须在后续语句解析之前提交。原有前端以完整函数作为
`source.parse_tokens` 的一个 item，提交发生在函数体已经解析完成之后，
因此添加一个 typedef 语法规则并不能让下一条语句识别这个类型。

`dialects/c11/scopes.stx` 现在在预处理后接管片段组织，仍由原有 C11
语法规则选出每个声明、表达式和语句。核心不识别 typedef 或 C 作用域。

## 数据与提交

- 原 token 行按 `()`、`[]`、`{}` 分组，保持文件、行、列及 token 分类。
  不改写用户标识符或删除语言关键字，括号不匹配在原位置报错。
- 文件声明、函数体、块语句与 for 子句使用不可变环境。退出块和 for
  语句后返回原环境，内部 typedef 和普通名字不泄漏到后续文件项。
- 声明器使用此前的类型环境；完整声明器之后，普通名字立即遮蔽同名
  typedef，初始化式和同一声明中的后续声明器使用新的环境。
  例如 `typedef long long T; int T=sizeof(T);` 的 sizeof 使用新 int 对象。
- 形参列表逐参数解析。形参名字会影响后续参数；原型作用域在列表
  结束时恢复，定义的形参名字则进入函数体的最外层块。
- 声明器扫描明确区分函数形参、嵌套声明器和不属于声明器的分组。
  __declspec/__attribute__/__pragma 注解，以及 sizeof、_Alignas、
  _Alignof、_Generic、_Static_assert 等分组不再递归当作函数参数。
  这种剪枝只影响作用域扫描；原始 token 和所有注解参数完整交给
  相应语法规则，因此未知注解或非法 deprecated 参数仍会报错。
- 独立片段仍使用上下文语法守卫和默认严格冲突诊断。嵌套语句、参数
  列表的内部占位行只连接已解析的语法值，原 token 坐标仍随节点保留。
- 局部 typedef 保留 `LocalTypedef` 语义节点，用于普通名字空间约束和
  遮蔽外层运行时对象；它不分配运行时存储，也不生成 LLVM 指令。
- 声明头和逗号声明器迭代保留完整 specifier 策略。`declaration_base`、
  `declaration_storage`、`declaration_type` 是方言库可扩展的组合规则；
  _Alignas 在声明器完成指针/数组绑定后装到每个最终对象类型，再由
  现有 sema/layout 规则求值和降低，因此不会改变元素/所指类型的大小。
  类型名、多次合并、静态局部存储、零对齐和全部常量约束继续保留。
  _Alignas 的类型名/表达式冲突根据当前可见 typedef 消解；普通对象
  遮蔽 typedef 时仍走表达式形式，并要求整数常量表达式。

这些规则只依赖现有列表、环境、树遍历和上下文解析原语。冻结的编译器
需要包含新模块及语法规则；当前验证使用动态规则，尚未将新规则冻结验证。

## 当前覆盖与边界

实现普通标量/指针/数组/函数指针 typedef、同块兼容 typedef 重声明、
嵌套 typedef 遮蔽及恢复、普通对象和参数的类型名遮蔽、原型作用域、
for 声明作用域，以及 if/while/do/switch/label 下的复合语句。
同块对象/typedef 冲突、重复形参、不兼容局部 typedef 和 typedef
作为表达式的使用会被拒绝。

for 初始化声明逐个检查声明器：拒绝 static、extern、typedef，以及
直接或由 typedef 引入的函数类型；后续逗号声明器同样检查。
该约束来自 C11 6.8.5p3，要求所声明的名字属于自动或 register 对象。
关于此约束的范围，WG14 在 [DR 277](https://www.open-std.org/jtc1/sc22/wg14/www/docs/dr_277.htm)
中也作了讨论。auto/register 关键字当前尚未接入声明语法，合法用法
仍会明确解析失败，不能把本次拒绝非法存储类当作这两项已支持。

本模块没有完成局部 extern/函数原型及链接属性、auto/register、局部
枚举和标签的完整作用域、VLA、旧式函数定义、复杂参数声明中的所有
类型兼容规则。现有标签收集仍有平坦作用域行为，不能据此宣称完整 C11
名字空间符合性。局部具名 struct/union 的定义与遮蔽还需单独验收。

## 独立回归

```powershell
python tests/c11_scopes.py
```

该测试含 56 个有效程序与必须拒绝的程序，每个运行 O0/O2，对照独立
Clang C11。Naru 编译串行执行，禁止子进程，内存限制 512 MiB，超时
20 秒；程序运行限制 64 MiB、3 秒。报告保存实际选用编译器及其同目录
后端、测试和规则 SHA-256，任一输入在测试期间改变则不会把整轮记为
验收通过。`--frozen --compiler <exe>` 支持已经冻结 C11 的编译器，
此模式不传 `--rules`；是否冻结和实际编译器路径也写入报告。
普通用例的求值/解析预算为 10M；真实系统 stdlib、limits、stdarg
头文件用例为 100M，进程内存和时间限制不变。MSVC 注解用例的 Clang
对照明确启用 `-fms-extensions`。

2026-10-12 动态规则稳定验收为 112/112，结果为 `target/c11-scopes.json`，
编译器、后端、测试及规则指纹均未变化。
`for_later_function_rejected` 的两项检查依据标准要求拒绝；本机 Clang
22.1.1 没有诊断混合声明里的后续函数声明，报告单独记录
`reference_diagnostic_gap`，不把这两项称为 Clang 一致性通过。
