# Dartmouth BASIC 方言(dialects/basic.stx)

Dartmouth BASIC(1964,DTSS)在 Naru 规则系统上的重构。
考据条目:`historical/basic/1964/`(1964-10 手册原件 + 索引卡;语句集另据
Kurtz 2005 年对原始 BASIC 的说明)。第四版(1968)另立条目 `historical/basic/1968/`。

## 运行

```powershell
# 单文件
.\target\naru.exe build examples\basic\sum.bas --rules dialects\basic.stx --frontend basic.frontend --unit program --relation emit_program --runtime crt-static --target exe -o target\basic-sum.exe
.\target\basic-sum.exe

# 项目(整程序模式)
.\target\naru.exe build --project examples\basic --target exe -o target\basic-project.exe
```

`--frontend basic.frontend` 必须显式给出:BASIC 是行导向语言,本方言在前端把源码
按物理行切分,逐行词法 + 解析,再拼接为程序项。`--runtime crt-static` 用于 PRINT/INPUT
(printf/fgets/strtod 在 CRT 里)。

## 支持的语法

- **行号程序**:每行 `<行号> <语句>`;行号是 CFG 跳转目标(lowering 为 `cfg` 标签)。
  程序末尾隐含退出(退出码 0)
- **赋值**:`LET v = e` 与隐式 `v = e`;数组元素 `LET A(i,j) = e`;`=` 在 LET 中是赋值,
  在条件里是相等比较
- **PRINT**:逗号/分号分隔的表达式列表;末尾分隔符抑制换行;逗号输出 15 个空格;
  裸 `PRINT` 只输出换行
- **INPUT**:逐变量从标准输入读取一行
- **READ / DATA / RESTORE**:内部数据与读取游标
- **DIM**:一维/二维数组上界(零元素恒存在);未 DIM 的数组隐式 0..10
- **GOTO <行号>**、**IF <条件> THEN <行号>**、**GOSUB <行号>** / **RETURN**(含嵌套)
- **FOR v = a TO b [STEP s]** / **NEXT [v]**:跨行配对;STEP 为字面负值时向下计数
- **DEF FNx(v) = 表达式**:单参数程序员函数(代入式内联)
- **标准函数**:`ABS ATN COS EXP INT LOG RND SIN SQR TAN`(lowering 到 LLVM math 内在函数)
- **运算符**:`+ - * /`、幂 `^`(右结合,`-x^2` = `(-x)^2`)、关系 `= <> < <= > >=`
- **END / STOP**:程序结束;**REM**:行级注释
- **变量**:无声明,出现的名字自动声明为 `f64`;**大小写不敏感**

## 实现选择与限制

| 偏离 | 理由 |
| --- | --- |
| 数值一律 f64 | BASIC 的浮点模型;整数/实数统一,整数输出经 sitofp |
| `RND(0)` 返回常量 0.5 | 随机状态尚未实现 |
| INPUT 用 `fgets`+`strtod` | 逐行读取并转换浮点数 |
| `^` 词法改写为私有终结符 | base 库把 `^` 定义为异或(更松优先级),其规则跨度更长;改写后仅本方言的幂规则匹配 |
| PRINT 数字用 `%g` | 手册规定前导空格/尾随空格、字符数为 3 的倍数;字段宽度未实现 |
| 逗号分区用固定 15 空格串 | 不跟踪实际列位置,也不实现 75 列自动换行 |
| FOR 的比较在解析期定死 | 依 STEP 字面量符号选 `<=`/`>=`;运行时才知符号的 STEP 不支持 |
| 数组无运行时越界检查 | 越界为未定义行为;DIM 上界须为字面常量 |
| 变量名不限字母+数字 | 手册限制为单字母或字母+数字;本方言接受一般标识符 |
| 未实现 | MAT 矩阵语句、多语句行(`:`)、字符串变量、DIM 表达式上界、GOSUB 深度上限 |

## 规则实现

- **行导向前端**:`text.lines` 切物理行 → 每行 `text.lex` + `source.parse_tokens`
  (带 commit 的上下文解析接口)。行号即标签。
- **关键字不保留**:关键字按普通词在模板里匹配;标识符折叠小写以支持大小写不敏感。
- **`^` 重分类**:`classify_one` 把 kind-5 的 `^` 改写为 kind-14 的私有拼写,模板用
  引号终结符匹配;通用分支加守卫排除 `^` 以避免两条规则歧义。
- **解析器 resolver**:`basic.resolve` 让同跨度候选取本方言的规则(如 `^`)。
- **CFG 复用**:`cfg` 提供 `Label`/`Jump`/`Detached` 的存储与 lowering;方言补
  `base.check_body` 对 `Label`/`Jump`/`Detached` 的检查规则(与 `b.stx` 同模式)。
- **GOSUB/RETURN**:运行时压栈返回行号,`RETURN` 用 `cfg.dispatch` 派发到该行标签;
  程序开头用 `BGosubTable` 把 `gosub_sites` 收集的返回点建为 switch 目标。
- **数组**:全局 `f64` 数组 + 扁平索引(`i0*(d1+1)+i1`);隐式上界 10(0..10)。
- **DEF FN**:`tree.rewrite` 把参数名代入实参(代入式内联);参数名同时是普通变量亦无妨。
- **DATA/READ**:全局 `f64` 数据数组 + `i64` 读指针;`RESTORE` 归零指针。
- **INPUT**:`__acrt_iob_func(0)` 取 stdin → `fgets` 读入 128 字节缓冲 → `strtod` 转换。
- **字符串驻留**:`tree.rewrite_with` 把字符串字面量去重为 LLVM 字节全局;printf 声明为
  `!llvm.func<i32 (ptr, ...)>` 外部符号。

## 测试

`examples/basic/`(12 个程序):hello、sum、countdown、table、step、equations(Cramer)、
arrays、readdata、subroutine(嵌套 GOSUB)、functions(DEF FN + 标准函数 + 幂)、
guess(手册猜数游戏,含 INPUT)、normal(手册正态分布图,40 行星号钟形曲线)。

回归:`tests/dialects/regressions.json` 的 21 个 `basic_*` 用例(B、Pascal、C11 同表),
经 `python tests/dialect_debug.py --dialect basic` 在 O0/O2 运行,比较 stdout 与退出码;
INPUT 用例经框架的 stdin 通道喂入。

## 后续支持

MAT 矩阵语句(第四版);多语句行 `:`;PRINT 精确格式(前导空格、3 字符倍数、75 列边界);
真随机数 RND;数组运行时越界检查;DIM 表达式上界;GOSUB 深度上限;
字符串变量与比较;变量名严格限制(单字母/字母+数字)。
