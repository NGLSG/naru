# B 语言考据注记(Users' Reference to B on MH-TSS, S. C. Johnson)

依据:`users-reference-to-b.pdf`(1972,Bell Laboratories,已入库原件)。
Kernighan 教程(`b-tutorial-kernighan.pdf`)为辅助材料。所有条款号引用手册章节。

## 一、语言核心事实(带条款)

1. **无类型**(§2.1):变量从上下文获得类型,无类型转换,无类型检查。
2. **rvalue/lvalue**(§3.0):rvalue 是定长位模式(H6070 为 36 位);lvalue 是地址。
   一元 `*`(间接)把 rvalue 当 lvalue;一元 `&`(取地址)反向。
   `*3 = x` 合法;`*(&x+1)` = x 之后的字。
3. **字地址机器**(§3.0):"addresses are stored in the right half of a word,
   adding 1 to a pointer gives a pointer to the next word in memory" —— 地址算术
   以字为单位。**Naru 重构采用 64 位字的字地址模型**(`*e` = load(e×8);
   `&x` = x 的 LLVM 地址 ÷ 8),保真于语义而非 36 位位宽。
4. **常量**(§4.1):十进制;**前导零 = 八进制**;字符常量 `'c'` 右对齐打包
   (H6070 至多 4 字符);**字符串打包进相邻字、以 `*e`(ascii EOT=4)结尾**,
   字符串的 rvalue = 首字的 lvalue。
5. **向量**(§4.1.7):`v[n]` ≡ `*(v+n)`;`x[0]` ≡ `*x`。n 是字偏移。
6. **一元**(§4.2):`* & - ! ++ -- ~`;右结合(`-!x++` ≡ `-(!(x++))`);
   前缀/后缀 `++/--` 语义与 C 相同。
7. **二元**(§4.3–4.10):`* / %`(`%` 仅两正数有意义)、`+ -`、`<< >>`
   (零填充,计数负或超字长未定义)、`< <= > >=`、`== !=`、`& ^ |`
   全部左结合。
8. **条件表达式**(§4.11):`a?b:c`,**右结合**。
9. **17 个赋值算符**(§4.12):`= =* =/ =% =+ =- =<< =>> =< =<= => =>= === =!= =& =^ =|`
   —— **前置顺序**(`x =* 10` ≡ `x = x*10`),右结合(`x=y=0`),结果为存储值。
10. **switch 是落空穿透的**(§5.4):`case 'a': y=1; case 'b': z=2;` 在 x=='a'
    时**两个都执行**;switch 是计算转移而非 C 的分派。`default:` 与 `break` 可用。
11. **goto 取 rvalue**(§5.5):标签是 internal 存储类,可赋给变量再 goto
    (函数/标签地址在字的左半,数据指针在右半,§11.0)。
12. **隐式 return**(§5.7):函数定义 closing `}` 前自动生成 return。
13. **声明**(§6.0–6.3):`auto`/`extrn`/internal 三类;auto 向量
    `auto v[10];` 分配 constant+1 字并把**基址存入 v**;
    未声明名字首用 = internal 声明;标签是 internal 的唯一现行用途。
14. **外部定义**(§7.0–7.2):程序 = 外部定义序列;隐藏启动序列 `main(); exit();`;
    `name ival;` 的 ival 可以是**名字**(取其 lvalue);向量定义四种形式,
    实际大小 = max(constant+1, 初值个数)。
15. **运行时**(§8.0–8.2):putchar(H6070 每字 4 字符,NUL/EOT 删除)、getchar、
    putstr/getstr、**printf 的 `%x` 两字母序列(%c %d %o %s)**、char/lchar、
    getvec/rlsevec、nargs、exit。
16. **Nasty**(§12.4):`&` 在真值语境(if/while/?:)按**逻辑与**解释;
    强制位运算须写 `(a&077) != 0`。§12.1:`a+++b` 可解析而 `a+++++b` 不行。

## 二、Naru 重构的机器模型决策

- **字 = i64**,字地址模型(见上 3)。这是"一台 64 位、字寻址的 B 机器",
  保真于语言定义(B 显式随机器字长参数化,§14.0 也承认字节寻址机器催生了 C)。
- **字符串 = 每字一字符 + EOT(4) 结尾**。H6070 的多字符打包是机器相关
  实现(§4.1.4 "machine dependent"),一机一策。
- **putchar 单字符输出**,保留 NUL/EOT 删除语义于 putstr 层(milestone 2)。
- **§12.4 的 & 逻辑语义**列为 milestone 2(milestone 1 全程位运算,记录为偏差)。

## 三、与 C 谱系的对照点(档案馆叙事素材)

| 特性 | B | C(K&R) |
| --- | --- | --- |
| 赋值算符顺序 | `x =+ 1` | `x += 1` |
| 字符串终止 | `*e`(EOT=4) | `*0`(NUL) |
| 转义引导符 | `*n` `*t` `*0` | `\n` `\t` `\0` |
| 地址算术 | 字(word) | 字节(byte) |
| switch | 落空穿透、case 是转移目标 | 每 case 独立、break 退出 |
| 自动向量 | 基址存入变量 | 数组名退化为指针 |
| 类型系统 | 无 | 有 |

## 四、验收程序来源

- §7.3 的 min(a,b);§9.2 convert(s,v)(switch/goto/标签——milestone 2);
- §9.3 lower(s)(while + char + lchar);§9.4 snide(printf——milestone 2);
- Kernighan 教程的 putchar 序列程序。
- milestone 1 验收:min、向量求和/赋值、字符串遍历(B 层 while+char)、
  17 个赋值算符、八进制、`*(&x+1)` 邻字访问、递归。
