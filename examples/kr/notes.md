# examples/kr — K&R C 验收程序(里程碑 1-7,全覆盖)

运行方式见 `docs/kr.md`;期望值与验证点见下表。

| 程序 | 模式 | 验证点 | 期望 |
| --- | --- | --- | --- |
| hello.c | item | K&R §1.1 原样结构 | stdout `hello, world` |
| expr.c | item | 优先级链/八进制 077/十六进制 0x2A/复合赋值/移位/括号 | exit 42 |
| fahr.c | item | K&R §1.2 温度表,for + `%d %6d` 宽度 | 原书表格,exit 0 |
| power.c | program | K&R §1.7:旧式函数、先调用后定义、`-3` 的幂 | 原书表格,exit 0 |
| swap.c | program | K&R §5.2:指针参数、`&`/`*` | exit 21 |
| str.c | item | 字符串字面量为 char 数组、指针索引走查、putchar | stdout `5`+`hs`,exit 5 |
| incdec.c | item | 前后缀 `++/--`、`*p++` 与 `*++p`、数组平方和 | exit 61 |
| goto.c | item | goto/标签/do-while/break/continue 嵌套 | exit 13 |
| longs.c | item | long 加法溢出、unsigned 环绕、sizeof、`1L<<40` | stdout 三行,exit 9 |
| chars.c | program | 转义全集、`\101` 八进制、char 参数截断(1000→-24) | stdout `a`,exit 89 |
| logic.c | item | `&&`/`||` 短路保住除法、`?:`、混宽比较 | exit 48 |
| float.c | item | double/float 算术、int↔float 转换、`%g`、整除后转 double | stdout 两行,exit 47 |
| comma.c | item | 逗号算符:for 双变量初始化/步进、`(1,2,3)` 取末值、序列点 | exit 98 |
| docont.c | item | do-while 的 continue 跳到**条件**(不跳过测试) | exit 98 |
| switch.c | program | case 落空穿透、break、default、字符/转义标签 | exit 29 |
| arrinit.c | program | 外部数组初值列表(补零/推断大小)、char[]=字符串、局部 char 数组 | stdout `K&R`,exit 220 |
| storage.c | program | static/extern:声明+定义共存、纯声明不发射 | exit 110 |
| struct.c | item | 结构布局/成员/`->`/结构数组元素 | stdout 两行,exit 17 |
| union.c | program | union 共享存储(m.i=65 → m.c='A')+ 结构指针参数 | stdout `A`,exit 44 |
| casexpr.c | item | case 常量表达式:`1+1`/`1<<3\|1`/`'A'`/比较折叠 | exit 24 |
| macro.c | item | 对象/函数宏、实参替换、重扫描、#undef 位置语义 | exit 31 |
| statloc.c | program | 局部 static 跨调用持续 | exit 3 |
| typedef.c | program | typedef 词对/struct 别名/`length *lp` 声明优先/ulong 环绕 | stdout,exit 63 |
| fptr.c | program | 函数指针:typedef 形、指针参数传递、`(*fp)(a,b)` 间接调用 | exit 27 |
| bits.c | item | 位域:符号提取/4 位环绕/RMW/零宽关闭容器/无名填充 | stdout,exit 0 |
| fptr2.c | program | 成员函数指针 `(*n.emit)` + 全局 `opfn table_op = &add2` | exit 18 |
| parr.c | item | `int (*row)[3] = &mat`、`(*row)[i]` 按元素缩放 | stdout,exit 20 |
| bitswide.c | item | char 3 位符号容器(-2)、long 40 位容器(符号扩展 + RMW) | exit 2 |
| multidim.c | program | `int grid[2][3]`/`int m[2][3]`、行缩放索引、sizeof 不退化 | exit 18 |
| fptable.c | program | 函数指针数组表驱动分发 | exit 13 |
| ifdef.c | item | #ifdef/#ifndef/#else/#endif 组合 | exit 13 |
| forward.c | program | 前向声明 + 后定义覆盖 | exit 22 |
| register.c | item | register/auto 存储类拼写 | exit 42 |

item 模式 = 单条命令直接 build;program 模式 = `--unit program --relation emit_program`
或 `--project examples/kr`(Naru.toml 已配置,入口 power.c)。

switch/arrinit/storage 为多 item 文件,必须 program 模式(`--unit program
--relation emit_program` 或 `--project examples/kr`)。

已知宿主差异:longs.c 用 `%lld` 打印 long(Windows CRT 的 long 是 32 位);
退出码按 Windows 惯例截断到低 8 位(chars.c 的 345 → 89)。
