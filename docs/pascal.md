# Pascal 方言(dialects/pascal.stx)

ISO 7185 标准 Pascal 在 Naru 规则系统上的重构。考据条目:`historical/pascal/iso-1983/`
(规范原件 + 考据注记);Wirth 1972 报告谱系见 `historical/pascal/1970/`。

## 运行

```powershell
.\target\naru.exe build examples\pascal\showcase.pas --rules dialects\pascal.stx --frontend pascal.frontend --runtime crt-static --target exe -o target\pascal-showcase.exe
.\target\pascal-showcase.exe
```

- `--frontend pascal.frontend` 必须显式给出:Pascal 的词法(`:=`/`<>`/`(* *)` 注释、
  保留字表)由方言自己定义,核心默认扫描器不认识这些记号。
- 使用 write/writeln 的程序需要 `--runtime crt-static`(printf 在 CRT 里);
  纯计算的程序无需该参数(freestanding 默认)。

## 已实现(里程碑 1 + 2 + 3)

- 程序头 `program Name;` / `program Name(input, output);`(参数接受并忽略)
- `var` 声明段(每组一个 `var` 关键字)、`const` 段(编译期只读绑定)、
  值参数函数、过程(结果为弃置的 32 位零)
- 语句:赋值 `:=`、复合 `begin...end`、`if/then/else`、`while/do`、`for/to/downto/do`、
  空语句 `;`、`case/of/else`(整数与布尔常量,相等比较 if 链 lowering)、
  `write`/`writeln`(档案控制台 v0,printf 后端)、过程调用(表达式语句)
- 表达式:`+ - * / div mod`、关系 `= <> < <= > >=`、`and or not`、
  `integer`(i32)、`boolean`、`real`(f64)、函数调用、字符串字面量 `'...'`
  (仅可写入 writeln;`''` 转义未解码)
- 函数结果:`f := expr` 赋给函数名(ISO §6.8.2.2),落到函数体末尾隐式返回;
  函数名只写不读(体内读函数名未实现)
- `for`：初值、终值按顺序求值一次；私有槽隔离嵌套循环；端点后不溢出递增
- `case`：选择器求值一次，命中后继续后续语句；重复常量标签报错
- 标识符和关键字不区分大小写，字符串内容保留；const 使用只读绑定
- 程序变量使用共享静态存储，函数/过程和 main 读写同一个对象；程序常量、
  常量别名对子程序可见，参数与局部变量/常量可以遮蔽程序声明。
  const 拒绝函数调用、可变对象和普通算术表达式作为初值。
- 悬空 else 绑定最近的 `if`(语法 fallback 层级实现,`dangling_else.pas` 验证:退出码 8)
- writeln 参数类型:i32/%d、u32/%u、real/%g、boolean→TRUE/FALSE(%s + llvm.select)、
  字符串(%s);writeln 末尾换行;参数间无分隔符(ISO 语义,字段宽度未实现)

## 与 ISO 7185 的偏离和未实现范围

| 偏离 | 理由 |
| --- | --- |
| `integer` = 32 位 | ISO 不定宽度;历史宿主是 16 位,现代互操作取 32 |
| 变量/结果槽零初始化 | ISO 未定义未赋值结果;零初始化给出干净诊断 |
| writeln 实数用 `%g` | ISO 规定科学计数法与字段宽度;period 格式化是档案考据项 |
| const 完整表达式约束 | 目前接受字面量、已声明常量及其负号形式；完整 ISO 常量集合仍需补齐 |
| case 仅整数字面量/布尔 | const 名与子界待 milestone 3 |
| 每组声明要求重复 `var` | 一组多行的缩写未收 |
| 不支持嵌套过程/过程调用语句以外的前向声明 | 平坦命名,与 base 库一致 |
| 完整声明顺序和同块作用域约束 | 程序声明收集后检查函数，可能允许源码中的前向可见性；同块局部重名仍需检查 |
| `halt` 是 Turbo Pascal 扩展 | 非 ISO;作为显式标注的扩展收入 |

## 结构(方言作者备注)

- **词法**:`lex_config` 数据 + 通用扫描器 `text.lex`;token 重分类
  (标点→kind 14 不可分割终端、保留字→kind 8、丢弃换行行)用 `list.fold` 迭代。
- **多字符算符**:`:=`/`<>` 不在核心 tokenizer 的双字符表里,模板必须写成
  引号终结符 `":="`;`<=`/`>=` 按单字符切分,直接复用 base 的普通模板。
- **语句序列**:邻接递归 `pseq`;`;` 本身是空语句(ISO §6.8.2.3),
  尾分号自然消解。`pseq` 既是链构造器也是转换器:parser commit 的逐项求值
  触发它,语句在此进入 base.continue / Pascal 扩展的转换。
- **冻结与 commit**:`source.parse_tokens` 会冻结 item 项,后续求值不再下潜;
  commit 在逐项求值后用共享树遍历区分 `/` 与 div/mod 的语义构造器。
- **程序展开**:`prepare_module` 把 `ProgramItem` 拆成全局声明、函数项和隐式 `main`。
  程序变量生成私有 `llvm.mlir.global`，读取/赋值使用同一全局地址；常量
  在声明环境中保存已检查的值，无运行时初始化。`base.emit` 对 `ProgramItem` 重载为
  整程序 lowering,单文件 `build` 无需 `--unit program`。
- **字符串提升**:格式串与源字面量经管线步骤 `intern_strings`
  (externc 的 tree.rewrite 机制)去重为 `llvm.mlir.global`,printf 声明为
  `llvm.func @printf(!llvm.ptr, ...)` 外部符号;调用走 `llvm.call` +
  `var_callee_type`(c11 同款机制)。
- **函数结果槽**:名字为 `" " + 函数名`(前导空格,不可能与源标识符冲突);
  不要对同一名字二次调用 `symbol()`(check_body 会对 Var 名再净化一次)。

## 测试

`examples/pascal/`:hello(42)、sum(1..10 求和 + 函数,42)、
dangling_else(8,最近配对)、factorial(while + if,120→42)、
hello_world(writeln)、showcase(全特性输出演示)。
验收对拍(黄金输出 vs 历史结果)在档案侧 `historical/pascal/iso-1983/notes.md` 规划。

## 里程碑 3 候选(按档案 P0/P1)

`/` 已转为 f64 实除，div/mod 已检查整数操作数，大小写已在 token 层折叠。
隐式整→实赋值转换、`set of` 位向量、variant records、case 的 const 名与子界;
`for` 控制变量赋值检查;一致性数组参数(依赖运行时边界数组)。

当前 O0/O2 最小复现及原始 showcase 回归见 `target/dialect-debug.json`，
具体缺陷与未解决范围见 [方言调试记录](dialect-debug.md)。
