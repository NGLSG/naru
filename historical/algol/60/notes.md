# ALGOL 60 考据注记

依据: `revised-report-algol60-1963.htm`(语义主依据)、`modified-report-algol60-1976.htm`(勘误)。
以下条款编号经原文检索定位;标注 (待核对) 的点在实现时逐句复核。

## 一、报告自列的未决问题(§ History 段,原文照录)

> Side effects of functions. The call by name concept. own: static or dynamic.
> For statement: static or dynamic. Conflict between specification and declaration.

这五条是 1962 罗马会议承认未解决的问题。重构时的取态建议:

1. **函数副作用**:表达式求值顺序未定义 → 方言按"实现自由"处理,验收程序避开依赖求值顺序的用例。
2. **call-by-name**:报告未指定 thunk 实现方式,只定义了行为(每次使用重求值)→ 用闭包机制 lowering,无需照抄任何历史实现。
3. **own 静态/动态**:决定性分歧点,见下节。
4. **for 语句静态/动态**:见下节。
5. **规格与声明冲突**:过程头 spec(§5.4.4)与过程体声明的类型不一致时报告无定义 → 方言报错(比报告严格,记录在案)。

## 二、own 的两义性(§5.2.3)

报告自己的示例就带动态边界:

```
own integer array A [ if c<0 then 2 else 1:20]
```

- Revised Report 允许 own 数组边界是任意算术表达式(含条件表达式);
- Modified Report 将 own 语义收紧为:静态分配、仅初始化一次;
- **重构决策(P0)**:采用 Modified Report 语义(own = 静态存储 + 一次性初始化),
  因为它可在现有 alloca/静态 lowering 上直接表达;边界仍须常量。
  报告原示例在方言中应**拒绝编译**并在诊断里引用本注记。

## 三、for 语句(§4.6)

- §4.6.3 语义原文:for clause 使后面的语句 S "被执行零次或多次";
- 未定义:控制变量在正常退出(while 失败/表耗尽)后的值、step 为零的行为;
- Modified Report 对上述两点给出了定义(控制变量值保留最后一次赋值;step 零导致死循环语义限制);
- **重构决策**:循环 lowering 用现有 cfg 块参数;控制变量退出值按 Modified Report;
  step=0 在方言检查层报错(选 implement 自由,须记录)。

## 四、悬空 else 的语法解法(§4.5.1)

ALGOL 60 不用"最近配对"惯例,而是语法层级强制:
`<if clause> ::= if <Boolean expression> then <unconditional statement>`,
else-less if 不能直接出现在 then 分支,必须 begin/end 包裹或补 else。
**方言语法规则必须复现这个层级**(unconditional statement 类别),而不是靠优先级打补丁。

## 五、字符串(§2.7、§4.7)

字符串字面量只能作为过程实参出现,不可赋值、不可比较、不可存储。
**含义**:ALGOL 60 方言不需要可变字符串设施(P0 清单里它只服务 I/O);
字符串 I/O 全部归"档案控制台"方言的过程语义。

## 六、数值语义与现有 MLIR 设施的差异(P1)

- `/` 实除与 `÷` 整除严格区分;整除方向 = ent(a/b),ent 是**向下取整**
  (与 arith.divsi 的向零截断不同)→ 必须自定义 opcode effect,不可复用默认。
- 标准函数 ent/abs/sign/sqrt/sin/… 是语言一部分(§3.2.4), lowering 归数值方言库。
- 运算符优先级链(§3.3.1,低 → 高):
  `+−(1) < ×÷(2) < ↑(3) < 关系 =≠<≤>≥(4) < ∨(5) < ∧(6) < ¬(7)`
  **关系运算符低于 ∨∧¬**(`a = b ∨ c` 解析为 `(a=b) ∨ c`)——与 C 家族直觉相反,
  映射到 Naru `syntax expr[priority,left]` 时逐条登记。
- ↑ 右结合;同级其余运算报告未规定结合性 (待核对),取左结合并记录。

## 七、I/O 与换码

报告不含任何标准 I/O 与程序格式定义;过程体可"换码"为机器指令(§5.4.4 注)。
**含义**:输入输出语义由考据对象=具体历史编译器(如 Electrologica X1、Elliot 803、
B5500 各自的 I/O 过程),起步实现挂"档案控制台"方言,并在 INDEX 备注选择依据。

## 八、Modified Report 的使用纪律

1976 修改报告仅用于修正报告已知错误(如 §4.7.4 名称参数传递遗漏),不引入新语义。
凡引用它处,notes.md 必须同时给出 Revised Report 原文行为,保证"两档忠实度"可切换。
