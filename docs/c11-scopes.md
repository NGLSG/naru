# C11 声明与作用域

`c11.scopes` 在预处理后组织解析片段。块级 typedef 必须在下一条语句解析前提交，因此声明、函数体、块及 for 子句分别携带不可变上下文。

## 解析与提交

原 token 按括号分组，保留文件、行、列和分类。语法守卫读取当前上下文，唯一结果选定后才提交。退出块或 for 后恢复外层环境。

声明器使用此前的类型环境，完整声明器结束后名字立即生效：初始化式和后续逗号声明器可见新名字。例如外层有 `typedef long long T;` 时，内层 `int T=sizeof(T);` 的 sizeof 使用新 int 对象。

参数逐个解析。原型作用域在参数列表结束时恢复，函数定义的形参进入函数最外层块。扫描区分声明器与 sizeof、_Alignas、_Generic 及目标注解的分组，注解参数交给各自语法规则处理。

`LocalTypedef` 保留名字空间及遮蔽事实，不分配运行时存储。`declaration_base`、`declaration_storage`、`declaration_type` 供其他规则组合。_Alignas 在指针/数组绑定完成后附到最终对象，保持元素和所指类型布局。

## 声明点身份

词法绑定使用 `DeclarationView` 保存当时类型，链接登记表维护定义和 ABI。后续数组边界或函数原型不能反向改变早先引用。

块 extern 和函数声明通过 `LocalLinked` 绑定链接实体，不创建局部对象；可见的内部链接声明由 extern 继承。局部自动对象遮蔽后，嵌套 extern 可重新引用外部实体。

标签、枚举和普通名字使用 `name_scope` 的稳定身份与不可变可见事实。类型引用和成员运算保存使用点快照，后置定义不能修复此前非法的 sizeof 或成员访问。

旧式定义按名字关联参数，ABI 采用默认提升，进入函数体后转换为声明类型。register 的取地址约束保留。

## 约束

同块对象/typedef 冲突、重复形参、不兼容 typedef 重声明及将 typedef 用作表达式均报错。

for 初始化逐个检查声明器，拒绝 static、extern、typedef 和函数类型，包括 typedef 引入的函数类型。依据为 C11 6.8.5p3 及 [DR 277](https://www.open-std.org/jtc1/sc22/wg14/www/docs/dr_277.htm)。

全部参数约束、VM 交互和跨单元兼容仍需结合 [支持计划](c11-full-support.md) 审核。

## 测试

```powershell
python tests/c11_scopes.py
python tests/c11_tags.py
python tests/c11_declaration_model.py
```

作用域套件在 O0/O2 对照 Clang，编译限额为 512 MiB、20 秒，程序运行限额为 64 MiB、3 秒。`--frozen --compiler <exe>` 使用已包含 C11 规则的冻结编译器。

普通用例预算为 10M，stdlib/limits/stdarg 头用例为 100M，内存和时限不变。MSVC 注解对照启用 `-fms-extensions`。Clang 22.1.1 未诊断混合声明中的后续函数声明，相关反例按标准检查并标记 `reference_diagnostic_gap`。
