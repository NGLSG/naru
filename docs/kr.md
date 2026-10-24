# K&R C 方言(dialects/kr.stx)

K&R C(1978,《The C Programming Language》第 1 版附录参考手册)在 Naru 规则系统上的重构。
考据条目:`historical/c/kr/1978/`(考据注记 + 谱系论文;书籍按版权仅引用)。

## 运行

```powershell
# 单函数程序(item 模式)
.\target\naru.exe build examples\kr\hello.c --rules dialects\kr.stx --frontend kr.frontend --runtime crt-static --target exe -o target\kr-hello.exe

# 多函数程序(整程序分析):CLI 直传或项目配置
.\target\naru.exe build examples\kr\power.c --rules dialects\kr.stx --frontend kr.frontend --unit program --relation emit_program --runtime crt-static --target exe -o target\kr-power.exe
.\target\naru.exe build --project examples\kr --target exe -o examples\kr\target\power.exe
```

`--frontend kr.frontend` 必须显式给出:K&R 的词法(`/* */`、多字符算符、28 词保留字表、
无三角字符组)由方言定义。使用 printf/putchar 的程序需要 `--runtime crt-static`。

## 已实现(里程碑 1-7,全覆盖)

- **类型机器**:int(i32)/char(i8)/long(i64)/short(i16)/unsigned(u32)/unsigned long(u64)、
  任意深度 `Ptr(t)`;存储为 LLVM 栈槽(alloca/load/store 按元素类型)
- **K&R 转换全套**:整型提升(char/short → int)、常用算术转换
  (int+unsigned → unsigned、int+long → long、unsigned long 同化等)、
  赋值/实参/返回的隐式转换(任意整型互转、int ↔ 指针、指针重标)
- **指针语义**:`*`/`&`、`p + n` 按元素大小缩放(getelementptr)、`p - p` 元素距离、
  指针比较、`p++` 步进一个元素、`p == 0`(int → ptr 转换)
- **数组**:局部 `int a[10]`、`int *p[3]`(指针数组);名字退化为首元素指针
- **常量**:十进制/八进制/十六进制(0x)、`L` 后缀(long)、字符常量(类型为 int)
  含 `\n \t \b \r \f \\ \' \" \0` 与 `\ddd` 八进制转义
- **字符串字面量**:**可写**(K&R 语义,无 constant 标记的 char 数组全局)、NUL 结尾、
  按拼写去重;`char *s = "hi"`、printf 格式串直接可用(真 CRT printf,%d/%u/%s/宽度全免费)
- **表达式**:K&R 精确优先级表(独立 `krexpr` 类别,见结构备注)、17 种赋值算符、
  `?:`、`sizeof`(类型与表达式)、`(type)` 强制转换(0-3 层指针)、
  `&& ||` 短路求值(scf.if)、比较产生 int
- **语句**:复合、if/else(悬空 else 最近配对)、while、**do-while**、
  **for(continue 跳到步进——精确 C 语义,break/return/goto 跳过步进)**、
  break/continue、**goto/标签**(cfg 库)、return(含隐式 return 0)、空语句、
  表达式语句、块内声明(不限块首)
- **旧式函数定义**:`int power(base, n) int base; int n; { ... }`;
  省略类型说明符 = 默认 int(`main() { ... }`);参数提升后传递、
  char 参数截断(经典 K&R 行为)、参数是可赋值的局部
- **隐式函数声明**:调用未声明函数 = 返回 int 的函数,实参按默认实参提升
- **两遍声明收集**:同文件先定义后调用直接解析到真实签名(对正确程序与 K&R 编译器行为一致)
- **CRT**:printf(变参)、putchar、getchar、puts、exit

### 里程碑 2 增补

- **float/double**(K&R §4):float 在表达式中先升 double(1st ed 转换表);
  int↔float 双向隐式转换(sitofp/uitofp/fptosi/fptoui,control.stx 注册);
  `long float` = double(历史拼写);浮点字面量(1.5/1e10/3.0e2)经 numbers 库;
  `sizeof(float)`=4(对象尺寸,与算术宽度无关)
- **switch/case/default**(K&R §3.6):整型选择器求值一次入隐藏槽;
  case 标签为整型/字符常量(可取负);**落空穿透**(每个 case 体线性流入下一个
  case 的块);break 跳出(default 后落空同);标签查重;空 case 体(标签堆叠);
  default 可在任意位置;cf.switch 稠密跳转表
- **do-while 的 continue**(K&R §3.7 语义):continue 跳到**条件求值**——
  在 continue 点重发条件、真则回循环头假则跳出(条件副作用只发生一次)
- **逗号算符**(K&R 附录 A):左到右求值,值为右操作数;
  表达式类别拆为 `krx`(赋值级)+ `krexpr`(完整表达式),参数/初值列表无歧义
- **外部数组初值**(K&R 8.x):`int a[6] = {...}`(不足补零,超出报错)、
  `int a[] = {...}`(大小=初值数)、`char msg[] = "K&R"`(字符串即数组内容,
  非指针——独立于驻留的 CStrRef 路径,专用 InitStr 项携带原文)
- **局部 char 数组初始化**(K&R 4.9):`char s[8] = "ab"` 逐字节 store(转义解码、
  NUL + 补零);`char s[] = "..."` 大小=len+1;数值局部数组初值列表**拒绝**(K&R 无此特性)
- **static/extern 数据**(K&R 8.x):static=内部链接定义;extern 无初值=纯声明
  (不发射 MLIR,与后续定义共存,悬空声明链接期报错);extern 带初值=外部链接定义

### 里程碑 3 增补

- **struct/union**(K&R 8.5-8.6):定义/布局(自然对齐,LP64 规则;union 偏移全 0、
  尺寸=最大成员)、`s.m` 与 `p->m`(糖为 `(*p).m`)、结构指针参数(旧式声明
  `struct point *p`)、结构数组(字节块分配 + 按元素尺寸缩放的动态索引)、
  嵌套成员类型、`sizeof struct`;**无结构赋值/传值/返回**(K&R 档,报错);
  布局在 commit 期解析(逐项注册进上下文池,item 模式同样可用)
- **case 整常量表达式**(K&R 6.4):字面量、字符常量、一元 -/~/!、
  算术/位/移位/比较/逻辑、括号——检查期折叠;除零报错
- **函数存储类**:`static int f() {}` / `extern int f() {}`(单编译单元不可观测,仅记录)
- **局部 static**(K&R 8.5):发射期提升为函数私有全局(`.stat.<fn>.<name>`),
  初值须为常量表达式;存储跨调用持续
- **#define / #undef**(K&R 11):对象宏 + 函数宏(实参按 token 替换、重扫描)、
  **单遍位置语义**(#undef 之前的展开保持早定义);`list.fold` 状态机实现
  (常数规则深度),worklist 重扫描队列;`#include` 明确拒绝(单文件单元,CRT 直连)

### 里程碑 4 增补

- **typedef**(K&R 8.7):token 级预扫描(行 `typedef ... ;` 移出流、名字进解析上下文,
  `syntax.context()` 守卫的 kr.ts 规则让名字在类型位置可解析);类型解码覆盖
  基本词对(int/unsigned/long/short/char/float/double 组合)、struct/union 标签、
  多层指针、函数指针形 `( * name ) ( params )`;commit 期随结构走查解析
  (typedef→typedef、typedef→struct 链);**声明优先**:`length *lp;` 是声明不是乘法
  (kr.ts 守卫使非 typedef 标识符不匹配,声明规则因而可安全地非 fallback);
  `sizeof(name)` 的类型读法优先
- **函数指针**(K&R 8.6/7.6):声明符 `( * name ) ( params )`(局部/参数);函数名在
  值位置退化为地址(`op = mul` 等价 `op = &mul`);`(*fp)(args)` 间接调用
  (llvm.call,操作数 = [fp, args...]);实参按默认实参提升、无元数检查(无原型,忠实);
  **用户函数降为 llvm.func**(私有 CheckedKFunc 项 + 独立 region 构造,
  返回走 ReturnOpKey=llvm.return;直调改用 KDirectCall→llvm.call)——
  这是函数地址可被 llvm.mlir.addressof 取得的前提

### 里程碑 5 增补

- **位域**(K&R 8.5):`name : width` 与无名 `: width`(纯填充)、零宽 `: 0`
  (关闭容器);同型容器顺序打包,放不下/类型变化/零宽即开新容器
  (容器按成员自然对齐,off 推进过容器);**读**:无符号 = 逻辑移位 + 掩码,
  有符号 = 双移位符号扩展;**写 = 读-改-写**(掩码清旧值、或入新值)——
  复合赋值与 `++/--` 同样走 RMW;`&x.f` 拒绝(位域无地址,C 规则);
  union 位域拒绝(打包机器相关,记录偏离)
- **结构体成员函数指针**:`int (*cmp)();` 成员,`(*n.emit)(a, b)` 间接调用
- **全局函数指针初值**:`opfn table_op = &add2;`——全局初值检查可见函数签名
  (declare 环境线程进 CheckedKGlobal)

### 里程碑 7 增补(全覆盖)

- **register/auto 存储类拼写**:接受并忽略(register 是优化提示;auto 即默认)——
  局部与参数声明均可
- **前向声明** `double sqrt();`(K&R 10):注册**无原型签名** SigU(结果类型已知、
  元数不查、实参默认提升);声明无条件注册,后定义覆盖声明,双定义仍报错
- **#ifdef/#ifndef/#else/#endif**(K&R 11 条件编译):预处理状态机加条件栈——
  活性 = 栈上任一为假;跳过模式下指令仍被跟踪(嵌套)、define/undef 被忽略、
  死分支 token 全弃;`#line N ["file"]` 行号偏移(后续 token 的行号平移)
- **多维数组** `int m[2][3]`(K&R 5.7):声明符 dims 列表(含 `[]` 未定首维)、
  类型 = 嵌套 KArrT、绑定携带维度列表、**子数组衰减**(`m[i]` 的 lvalue 读时
  退化为行指针,不 load)、行缩放索引(字节 gep 按行大小)、全局平铺存储
  (行主序 = C 布局;首维可由初值数推出)、`sizeof m` 不退化(总字节)
- **函数指针数组** `int (*ops[4])()`:声明符 + 表驱动调用 `(*ops[i])(a, b)`
- **函数指针声明符标记反转**:普通标识符变 fallback、带维度的声明符非
  fallback(否则短跨度非 fallback 永远挡住长声明符——引擎规则第三次生效)

## 测试(examples/kr/)

- **指向数组的指针声明符** `int (*row)[3]`(K&R 8.6):类型 `Ptr(KArrT(elem, n))`;
  `&arr` 合法化(数组绑定携带元素计数;全局数组按声明大小,未定大小 -1);
  `(*row)[i]` = 解引用得数组值(数组不 load)再按元素缩放索引
- **char/long 位域容器**:位域实现本就按声明类型的宽度/对齐通用化——
  `char c : 3` 用 i8 容器(3 位有符号 -2 ✓)、`long l : 40` 用 i64 容器
  (40 位符号扩展、跨字段的 RMW 精确)——零新增代码,验证通过

## 测试(examples/kr/)

| 程序 | 验证 | 结果 |
| --- | --- | --- |
| hello.c | K&R §1.1 原样 | 输出 `hello, world` |
| expr.c | 优先级链、八进制/十六进制、复合赋值、移位 | 退出码 42 |
| fahr.c | K&R §1.2 温度表(for + `%d %6d`) | 原书表格 |
| power.c | K&R §1.7 旧式函数 + 先调用后定义(项目模式) | 原书表格(含 -3 的幂) |
| swap.c | K&R §5.2 指针参数 | 21(x=2,y=1) |
| str.c | 字符串字面量、指针走查、putchar | 输出 `5`/`hs` |
| incdec.c | 前后缀 ++/--、`*p++`/`*++p`、数组平方和 | 61 |
| goto.c | goto/标签/do-while/break/continue 嵌套 | 13 |
| longs.c | long 溢出回绕、unsigned 环绕、sizeof、`1L<<40` | 9 |
| chars.c | 转义全集、`\101` 八进制、char 参数截断 | 89(345 mod 256) |
| logic.c | `&&`/`||` 短路保住除法、`?:`、混宽比较 | 48 |
| float.c | double/float 算术、int 转换、`%g`、7/2 整除后转 double | 47 |
| comma.c | 逗号算符:for 双变量、`(1,2,3)`、`(i=7, i+1)` | 98 |
| docont.c | do-while 的 continue 跳到条件(不跳测试) | 98 |
| switch.c | case 落空穿透、break、default、字符标签(项目模式) | 29 |
| arrinit.c | 外部数组初值/补零、char[]=字符串、局部 char 数组(项目模式) | 220 |
| storage.c | static/extern 声明与定义共存(项目模式) | 110 |
| struct.c | 结构布局/成员读写/指针/数组元素(`.` 与 `->`) | 17 |
| union.c | union 共享存储 + 结构指针参数(项目模式) | 输出 `A`,44 |
| casexpr.c | case 常量表达式折叠(`1+1`、`1<<3|1`、`'A'`、比较) | 24 |
| macro.c | 对象/函数宏、重扫描、#undef 位置语义 | 31 |
| statloc.c | 局部 static 跨调用持续(项目模式) | 3 |
| typedef.c | typedef 基本词对/struct 别名/指针/ulong 环绕/sizeof(项目模式) | 63 |
| fptr.c | 函数指针:typedef 形、指针参数、`(*fp)` 间接调用(项目模式) | 27 |
| bits.c | 位域:符号提取/环绕/RMW 复合赋值/零宽/无名填充 | 0 |
| fptr2.c | 成员函数指针 `(*n.emit)` + 全局函数指针初值(项目模式) | 18 |
| parr.c | `int (*row)[3] = &mat`、`(*row)[1] = 55`、元素缩放索引 | 20 |
| bitswide.c | char 3 位符号容器、long 40 位容器(符号扩展+RMW) | 2 |
| multidim.c | `int m[2][3]` 全局/局部、行缩放索引、sizeof 不退化(项目模式) | 18 |
| fptable.c | `opfn ops[2]` 表驱动 `(*ops[i])(a,b)`(项目模式) | 13 |
| ifdef.c | #ifdef/#ifndef/#else/#endif 组合 | 13 |
| forward.c | 前向声明 `double twice();` 先声明后定义(项目模式) | 22 |
| register.c | register/auto 拼写接受 | 42 |

## 与 K&R 1 版的偏离(全部有意并记录)

| 偏离 | 理由 |
| --- | --- |
| int=32、long=64(LP64)、指针 8 字节 | 历史宿主 PDP-11 是 16 位;语言层语义忠实,机器接口现代(x64 ABI) |
| `>>` 有符号为算术右移(shrsi) | PDP-11 行为;K&R 未定义 |
| 打印 long 用 `%lld` | Windows 宿主 CRT 的 long 是 32 位(K&R 时代 `%ld` 对应 32 位 long) |
| 浮点字面量含 0x 十六进制浮点拼法 | K&R 无十六进制浮点;核心 lexer 保留拼法,方言按 hex 整数解析失败报错 |
| case 标签限字面量(int/char/负号) | 常量表达式折叠(如 `case 1+1:`)未实现;K&R 允许整常量表达式 |
| switch 选择器限整型 | K&R 即如此(无拒绝 float 的明确条文,取 C 传统) |
| 无位域、函数指针、typedef、auto/register 存储类、`#include`、`(*a)[3]` 声明符 | 明确拒绝或未实现;`entry` 按原书保留但未实现 |
| 位域打包 | 现代 LP64 小端顺序打包;K&R/PDP-11 打包机器相关(K&R 明言 machine-dependent) |
| union 位域 | 拒绝(打包语义实现定义) |
| 函数宏的 `#`/`##` 算符 | C89 新增,K&R 无 |
| `#include` | 拒绝:单文件单元,CRT 直连无需头文件 |
| 无结构赋值/传值/返回 | K&R 1 版即无(报错忠实) |
| 无符号一元负号拒绝 | base 无 unsigned neg;K&R 时代编译器行为不一 |
| 声明可在块内任意位置 | K&R 要求块首;不强制是宽松化(记录) |
| 调用点实参按声明签名转换 | K&R 编译器完全不检查(lint 才查);这是 UB 的清理诊断化 |
| 同文件后定义的函数解析到真实签名 | K&R 单遍编译为隐式 int;对本来正确的程序行为一致 |
| 未初始化局部/落尾返回值为 0 | C 为不确定值;零给出干净诊断 |
| 全局量 internal 链接 | 单文件编译单元;外部链接随 extern/M2 |
| 字符串字面量去重按拼写、每文件 | K&R 未规定;实现自由 |
| 逗号算符、`(*a)[3]` 指向数组的声明符、多字符常量 | 里程碑 2 / 明确拒绝(机器相关) |

## 结构(方言作者备注)

- **独立表达式类别 `krexpr`**:核心 `expr` 模板把 `&`/`|` 注册在与 C 相反的相对层级
  (`&` 比比较紧,C 相反),同拼写不同层级会形成同跨歧义——所以 K&R 拥有自己的
  全套算符表(层级 90 后缀 … 10 赋值),完全按手册优先级。**引擎要点:非 fallback
  语法规则无条件压过 fallback,与跨度无关**(数组声明符 `a[10]`、多声明符 `i, j, n`
  的长规则必须是非 fallback 才能赢过短的普通规则)。
- **效果歧义规则**:两个非 fallback 效果子句同时匹配 = 报错(不按特异性选)。
  守卫对(`when eq`/通用)必须把通用侧标 `[fallback]`。
- **转换三闸门**:`kr_check_any`(推导检查)→ `kr_expect`(期望相等/Any 放行)→
  `kr_coerce`(插入 Converted/CToPtr/CFromPtr)。所有隐式转换只在这里发生;
  期望 `Any()` 时永不转换。
- **指针零值**:`Typed(Ptr, Integer(0))` 会走 base 的 `arith.constant : !llvm.ptr`
  (非法)——指针零初始化用专用 `CPNull` 项(inttoptr)。
- **指针提升签名**:旧式参数全部提升(int 化)进签名,char 参数 = 提升后的 int 实参
  截断进影子局部(`KShadow` 从环境里的 `Slot` 解构出 SSA 身份——`symbol()` 不稳定,
  不可预计算)。
- **for 的 continue 语义**:脱糖为 `while (cond) { B[continue→step;continue]; step; }`,
  步进重写走 `kr_for_continues` 树遍历(control.stx 的 range 模式),内层循环自持有
  其 continue。
- **字符串驻留**:commit 期树重写(B 同款),但全局**无 constant 标记**(K&R 可写)、
  NUL 结尾、对齐 1;转义解码与 MLIR `\XX` 再转义一遍完成。
- **printf 直通**:格式串就是真 CRT printf 的格式串——`%6d`/`%u`/`%s`/`%g` 等全部免费,
  这是不模仿 1978 运行库实现的边(B 方言需要手工 `%c`)。
- **两个表达式类别**:`krx`(赋值级,参数/初值元素)+ `krexpr`(含逗号算符)——
  C 语法用 assignment-expression 限定实参,否则逗号算符与分隔符歧义。
- **switch 自管块**(不走 cfg.Label):prepare 为每个 case 名 + " case.default" +
  " switch.exit" 预建块;lower 发射 cf.switch(稠密 case 值表)后,每个 arm 体从自己的
  块开始、以**下一个 arm 的块**为落空续接(KToBlock finish),default 体单独落 exit。
  continue 的 for 重写(kr_for_continues)与 do 的 kr_do_continues 是同一树遍历模式。
- **字符串初值与驻留的两条路**:commit 驻留把 CQuoteStr 全部改写为 CStrRef(指针语义);
  `char m[] = "hi"` 需要字节作为数组本体内容——kr.init 对字符串产出 **InitStr(原文)**,
  驻留走查不触碰,数组初值路径直接用原文。
- **extern 纯声明不发射 MLIR**:同文件 `extern int x; int x = 7;` 若声明也发射会重名;
  声明只绑环境,悬空声明留给链接器报错。
- **词法数字续集**:text.lex 配置第 4 槽加 `.`、第 5 槽(signs)`eE`——浮点拼写
  (1.5/1e10)由核心配置驱动成单 token;规则层 kr_float_p 分派到 Literal(numbers 库)。
- **守卫求值注意**:效果歧义检查会求值**所有**守卫且 `and` 不短路——守卫里的
  text.byte 必须先用 lt($i,$end) 层级化(见 kr_byte_at 的分层)。
- **程序模式**:`--unit program --relation emit_program`(CLI 直传或 examples/kr/Naru.toml);
  KRuntimeDecls 由 commit 每文件注入一次(item 模式下也是首个条目)。

- **预处理状态机**:list.fold 单遍(常数规则深度——逐 token 递归会撞 256 深度上限);
  状态 KPS(mode, macros, out, pending, name, l1, l2, nest, cur, done);
  宏展开的 worklist 在每个 fold 步先抽干(拼接 token 入队首,重扫描即重入队);
  函数宏调用的 `(` 由下一个 token 补(nest 从 0 计);未定义宏用墓碑记录(无 env.remove)

## 与 MSC40(1986)的过渡对照(K&R → 1986 编译器已接受项)

MSC40 条目(`historical/c/kr/1984/`)是 1986 年 Microsoft C 的语言参考,代表
K&R→C89 之间的过渡态。kr 方言按 1978 档实现,以下为可核对的差异点:

| 特性 | K&R 1 版 (kr) | MSC40 1986 | C89 |
| --- | --- | --- | --- |
| 结构赋值/传参/返回 | 无(kr 报错) | 已接受 | 强制 |
| 函数原型 `int f(int)` | 无(旧式定义) | 已接受 | 强制 |
| `void` 类型 | 无 | 已接受 | 强制 |
| `const`/`volatile` | 无 | 已接受 | 强制 |
| `enum` | 无 | 已接受 | 强制 |
| 位域 | 有(打包机器相关) | 有 | 有 |
| 结构体位域容器跨单元 | 实现定义 | 实现定义 | C89 仍未定义 |

kr 方言在遇到这些 1986 特性时报错并给出名称——这正是"方言 = 语言史切片"的
验收方式:同一份代码在 kr 与 c11 两个方言下编译,行为差异即语言演化本身。

## 状态:全覆盖

K&R 1 版的语言面全部落地(28 关键字、完整优先级表、全部语句与声明形式、
条件编译、多维数组):字机器、类型转换全套、旧式函数、隐式声明、
goto/do/for(精确 continue)、可写字符串、sizeof、float/double、switch(落空穿透)、
逗号、do-while continue、数组初值、char[]=字符串、static/extern、struct/union
(无结构赋值档)、case 常量折叠、局部 static、#define/#undef(位置语义)、
typedef、函数指针、位域、指向数组的指针。仅存的刻意缺口:`entry`(原书保留未实现)、
`#include`(单文件单元)、多字符常量(机器相关)——三者为忠实性记录。
