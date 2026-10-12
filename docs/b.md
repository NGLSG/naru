# B 方言(dialects/b.stx)

B 语言(1972,Users' Reference to B on MH-TSS)在 Naru 规则系统上的重构。
考据条目:`historical/b/1972/`(手册原件 + 考据注记,条款号可追溯)。

## 运行

```powershell
# 单函数或纯计算程序(无需 CRT 时)
.\target\naru.exe build examples\b\expr.b --rules dialects\b.stx --frontend b.frontend --target exe -o target\b-expr.exe

# 使用 putchar 的程序(printf 在 CRT 里)
.\target\naru.exe build examples\b\hello.b --rules dialects\b.stx --frontend b.frontend --runtime crt-static --target exe -o target\b-hello.exe

# 多函数程序(跨函数调用需要整程序分析):使用项目配置
.\target\naru.exe build --project examples\b --target exe -o examples\b\target\recursion.exe
```

`--frontend b.frontend` 必须显式给出:B 的词法(`=+` 系列赋值算符、`/* */` 注释、
保留字表)由方言自己定义。

## 已实现(里程碑 1+2)

- **字机器**(§3.0):无类型,一切皆字;本宿主定义 64 位字。语言地址为字地址，
  仅在宿主指针转换时乘/除 8
- **lvalue/rvalue**(§3.0):一元 `*`(间接)、`&`(取地址);`*(&x)` 恒等;
  向量引用 `v[n]` ≡ `*(v+n)`，不重复缩放下标
- **常量**(§4.1):十进制、八进制(前导零,`077`=63)、字符 `'c'`(含 `*` 转义)、
  字符串(字节存储,`*e` EOT 结尾)
- **表达式**(§4.2-4.11):全部一元(`- ! ~ ++ --` 前缀后缀)、二元
  (`* / % + - << >> < <= > >= == != & ^ |`,零填充逻辑右移)、条件表达式 `?:`(右结合)
- **17 个赋值算符**(§4.12):`=` `=* =/ =% =+ =- =<< =>> =< =<= => =>= === =!= =& =^ =|`,
  前置顺序(`x =* 10` ≡ `x = x*10`),右结合,结果为存储的 rvalue
- **声明**(§6.0-6.2):`auto`(标量 + `name[constant]` 自动向量)、`extrn`
- **外部定义**(§7.0-7.2):`name;` / `name ival;` / 向量定义 `name[c] ival,...;`
- **语句**(§5):复合、if/else(悬空 else 最近配对)、while、`return`/`return(e)`
  (§5.7 隐式 return)、**goto/标签(§5.5-6.3,cfg 库)**、rvalue 语句、空语句
- **运行时**(§8 子集):`putchar`(单字符,§8.1)、`char(s,n)` / `lchar(s,n,c)`
  (§8.2)、`exit`
- **§12.4 条件 `&` 逻辑语义**:在 if/while 真值语境按逻辑与(两操作数非零)解释
- 函数:递归、按值传参(§7.3)、跨函数调用(项目整程序模式)

## 测试(examples/b/)

| 程序 | 验证 | 结果 |
| --- | --- | --- |
| expr.b | 算术优先级 `2+8*5` | 退出码 42 |
| assign.b | 11 个赋值算符链 | 3 |
| octal.b | 八进制 `077`=63、`0100`=64 | 64 |
| ternary.b | `?:` | 42 |
| vector.b | 自动向量 + `=+` 求和 1..10 | 55，O0/O2 回归 |
| ptr.b | `*(&x)`、向量高索引 | 43，O0/O2 回归 |
| hello.b | putchar ×3 | 输出 "Hi" |
| string.b | char() 遍历 + `*n` 转义 | 输出 "Hi" |
| condand.b | §12.4 条件 `&` 逻辑语义 | 42 |
| goto.b | goto/标签循环(§5.5-6.3) | 55 |
| recursion.b(项目) | 递归 fact(5),跨函数调用 | 120 |
| vecglob.b(项目) | 向量外部定义 + extrn | 30 |

上述 vector/ptr/recursion/vecglob/goto 的当前结果与新增边界用例见
`target/dialect-debug.json`；其他早期结果不代表本轮重新运行。

## 与手册的偏离和未实现范围

| 偏离 | 理由 |
| --- | --- |
| 字 = 64 位 | H6070 为 36 位;B 显式随机器字长参数化(§3.0),本宿主取 64 |
| 地址 = 宿主指针 ÷8 | 保留 v+n 的字寻址语义，宿主访问时转回字节指针 |
| 字符串每字节一字符 | H6070 每字 4-5 字符打包;打包为机器相关(§4.1.5) |
| putchar 单字符输出 | H6070 每字 4 字符;NUL/EOT 删除语义随打包走 |
| auto 变量零初始化 | 手册:返回后未定义;零初始化给出干净诊断 |
| 外部向量名重绑定和取地址 | 尚无独立地址槽；明确拒绝，避免覆盖元素 0 |
| 多字符常量、name-ival、printf/getchar/putstr/getvec | 尚未补齐；外部向量数据读写已支持 |
| 大小写敏感 | §2.2 仅小写关键字;源标识符大小写敏感度未查证,默认敏感 |

## 结构(方言作者备注)

- **词法**:c11/lex 模式 —— 通用扫描器 `text.lex` + 数据配置;token 重分类
  (标点→kind 14、保留字→kind 8、换行行丢弃、八进制数字串→kind 3 保留拼写);
  全部用 `list.fold` 迭代(深度上限)。
- **多字符算符**:所有不在核心 tokenizer 双字符表里的算符(`=+` 系列、`<<`、`++`)
  模板必须写引号终结符;`==`/`!=`/`->` 在表内可直接裸写。
- **commit 即转换**:`source.parse_tokens` 冻结 item,语句→续体的转换在
  commit 的逐项求值中完成;`pseq` 既是链构造器也是转换器。
- **字符串驻留**:commit 的树遍历把字符串字面量去重为字节全局
  (`llvm.mlir.global` i8 数组,externc 的 value-attr 模式),EOT 追加一次
  (走查与属性各一次会翻倍 —— 曾为此调试)。
- **putchar 格式**:printf 的格式串是 NUL 结尾的**字节**数组
  (`ByteFmt`),不是 B 的字打包字符串 —— C 运行时按字节读格式串。
- **内在函数**:`b_intrinsic_env` 播种(单函数模式)+ `BIntrinsics` 哨兵项
  (整程序模式的声明收集);`call_checked`/`signature_result` 扩展返回字。
- **项目模式**:多函数程序需 `--unit program --relation emit_program`
  (examples/b/Naru.toml 已配置);单函数可直接 `--rules` + item 模式。

具体缺陷、修复和验收边界见 [方言调试记录](dialect-debug.md)。

## 里程碑 3 候选(按手册)

裸地址/向量的运行时越界保护与外部向量地址槽(字地址模型不等于原机器 ABI);
switch(§5.4,落空穿透);printf(§8.1 的 %c/%d/%o/%s);putstr/getstr;
name-ival 初值(§7.1);nargs(§8.2);字长参数化(i16 档案档,PDP-11)。
