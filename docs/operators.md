# 运算符重载

`std/standard` 包含 `operators`；也可单独选择 `std/operators`。`operator` 和 `fn operator` 是 `.stx` 定义的语法，核心编译器没有运算符关键字或类型表。

```text
struct Vec { x: i32; y: i32; }

fn operator+(a: Vec, b: Vec) -> Vec {
    return Vec { x: a.x + b.x, y: a.y + b.y };
}

operator +(a: Vec, b: i32) -> Vec {
    return Vec { x: a.x + b, y: a.y + b };
}

operator *(a: Vec, b: Vec) -> i32 {
    return a.x * b.x + a.y * b.y;
}
```

左右类型与结果类型独立。声明允许一或两个参数，同一符号可同时有一元和二元实现。数值默认语义仍由 `base` 提供；当前接入算术、比较、位运算、一元负号和移位。短路逻辑继续使用其控制流规则。

```powershell
.\target\naru.exe build examples\operators.nru --rules dialects\standard.stx --unit program --relation standard.emit_program --target exe -o target\operators.exe
& .\target\operators.exe
$LASTEXITCODE # 42
```

## 候选与选择

解析 `a + b` 得到的 `base.Add(a,b)` 只代表语法节点，不预先决定数值类型、结果类型或 MLIR 操作。`base.binary` 是开放关系，`operators` 在语义分析时解析候选：

1. 收集用户声明以及 `collect("operators.extension", [symbol, hints, environment])` 提供的库候选。
2. 根据参数类型筛选。已确定的类型必须相等；未标类型的整数/浮点字面量只匹配相应的字面量参数类型。
3. 唯一候选进入普通实参/结果类型检查；零候选尝试已有的数值默认规则；多个候选报告歧义。

选择不依赖加载先后，不插入隐式数值转换，也不按返回类型消除重名签名。未标类型字面量同时匹配多个重载时须标类型或显式转换。相同符号和参数类型的重复声明立即报错，返回类型不同也不能重复。

例如 `.stx` 可为现有 `+` 增加候选，无须重新声明 `+` 的语法：

```text
use operators;
use records;
use types;

effect operators.extension("+", [Record($name, $fields), Signed(32)], $environment)
    when eq($name, "Point")
    => operators.Candidate([Record($name, $fields), Signed(32)], Record($name, $fields),
        operators.FunctionTarget("translate"));
```

`FunctionTarget` 引用具有匹配签名的正常 `.nru` 函数。`RuleTarget("module.relation")` 调用规则关系，传入已检查的实参列表和环境，要求它返回已声明结果类型的 `base.Typed`。`operators.implement` 本身开放，因此方言还能定义其他实现策略。能力约束、类型族或目标设备条件可用于 extension 的纯守卫；这不要求核心了解这些类型。

普通运算符函数经过闭包提升、defer、所有权分析以及整组类型检查。owned 参数须显式 `move`，借用参数依旧遵守借用规则；运算符不会绕过这些阶段。每个实参只求值一次，结果生成直接函数调用或规则指定的 MLIR；没有运行时重载搜索。

## 新符号与冻结扩展

新符号、优先级和结合性继续由语法规则指定：

```text
syntax operator_symbol `@` => "@";
syntax expr[55,left] `$a:expr @ $b:expr`
    => operators.OperatorExpression("@", [$a, $b]);
```

随后 `.nru` 可声明 `operator @(a:i32,b:i32)->i32 { ... }`，或由库提供 `@` 的候选。同一模板若同时构造 `Add` 和 `VectorAdd`，仍是语法歧义；类型重载通过候选协议实现，不选择任意 AST。

新构建的冻结编译器允许 `--rules extra.stx` 追加动态模块。冻结规则继续执行原生 Vyx 匹配器和 RHS；新增规则使用动态解释，并参与相同的 fallback、候选收集与歧义检查。相同冻结模块可按原内容重选，修改其内容会报错。项目引用也可在冻结组上增加规则；项目须保留冻结组的依赖闭包，锁文件包含完整组合。

扩展后的规则组可以再次固化为编译器。

当前源声明使用具体参数类型，尚未提供泛型 `operator<T>` 声明和隐式转换优先级系统。类型族候选可以通过开放的 STX extension 关系实现。
