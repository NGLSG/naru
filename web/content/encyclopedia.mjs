// Original editorial text. Historical source cards and originals remain separate.
const p = text => ({ kind: 'paragraph', text })
const code = (title, language, code, notes) => ({ kind: 'code', title, language, code, notes })
const table = (columns, rows) => ({ kind: 'table', columns, rows })
const note = (title, text) => ({ kind: 'note', title, text })
const section = (id, title, blocks, refs = ['manual']) => ({ id, title, blocks, refs })
const ref = (key, title, file, locator) => ({ key, title, file, locator })
const external = (key, title, url, locator) => ({ key, title, url, locator })

export const families = {
  basic: {
    name: 'BASIC', fullName: 'Beginner’s All-purpose Symbolic Instruction Code',
    subtitle: '终端另一端，计算第一次成为日常。', origin: '1964 · Dartmouth College',
    people: 'John G. Kemeny / Thomas E. Kurtz', model: '行号程序 · 数值计算 · 分时交互', setting: 'Dartmouth Time-Sharing System（DTSS）',
    lead: 'BASIC 是从大学分时计算环境中诞生的入门语言。它把算式、简短的英语命令和可逐行修改的程序放到学生面前。这里的 BASIC 特指 Dartmouth 谱系：1964 年的早期手册与 1968 年第四版分别立档，不能把后来微型计算机上的方言当作它们的同义词。',
    related: ['fortran', 'algol', 'pascal'],
    sections: [
      section('terminal', '从排队计算，到坐在终端前', [
        p('BASIC 的故事与 DTSS 分时系统相连。语言降低了表达计算的门槛，分时系统则让更多人能够接触机器。Kemeny 与 Kurtz 希望非数学、非工程专业的学生也能学习计算；这种教育目标解释了为什么早期手册从“什么是程序”开始讲起。'),
        p('1964 年 10 月手册的入门例子是解二元一次方程组。它把 READ、LET、IF、PRINT、DATA 与 GO TO 放进一个具体问题中，而不是先展开一整套形式化语法。阅读这样的材料，也是在观察当时的人如何向初次接触计算机的读者解释编程。'),
      ], ['early', 'dartmouth']),
      section('line-numbers', '行号是一种程序组织方式', [
        p('行首数字既帮助编辑器定位一行，也为跳转提供目标。数字不必连续；留出间隔便于插入新语句。IF 后面的目标行号把判断与控制转移连在一起，因此不能用现代块式 if 的习惯直接理解早期 BASIC。'),
        code('读一段行号程序', 'Dartmouth BASIC · 自编讲解示例', '10 LET S = 0\n20 FOR I = 1 TO 10\n30 LET S = S + I\n40 NEXT I\n50 PRINT S\n60 END', ['10 初始化累加值；LET 明确表示赋值。', '20 与 40 配对，以 I 为控制变量重复计算。', '50 把数值交给输出语句；这是语言示例，尚未由 Naru 方言验收。']),
        p('行号并不是排版装饰。迁移旧程序时，删除它们可能破坏跳转目标、编辑命令以及出错位置。复原工作需要同时保存源程序顺序和行号身份。'),
      ], ['early']),
      section('environment', '语言，和承载语言的环境', [
        p('LET、FOR、NEXT 等属于程序语言；装入、保存、列出与运行程序属于用户与分时系统的交互。原始手册同时描述这两者，因为终端上的学习经验本来就是连续的。'),
        table(['层次', '需要保留的行为', '复原时的区别'], [
          ['程序', '算式、循环、数据读取、跳转', '可编译为独立程序'],
          ['编辑会话', '按行号插入与替换，保存与取回', '依赖交互工作区'],
          ['历史宿主', '数值精度、输出布局、设备习惯', '需要明确机器与环境参数'],
        ]),
        p('因此，仅让一段 BASIC 算出正确总和，还不足以声称重建了 DTSS。未来的档案控制台可以组合环境规则，但不应把尚未完成的环境显示成已经可用。'),
      ], ['fourth']),
      section('growth', '同一个名字，并不意味着同一种语言', [
        p('1968 年第四版把基础与高级 BASIC 分开讲述：目录中有函数与 DEF、GOSUB 与 RETURN、INPUT，随后单列矩阵和字母数字信息。这种组织呈现出一个已经扩展的教学与计算工具。'),
        p('版本比较需要逐项核对正文。第四版附录还把若干数据文件与程序连接设施列为未来计划，不能仅凭目录中出现某个名词就认定功能已经实现。同样，不能将后来常见的字符串变量、屏幕命令和微机设备操作倒推到 1964 年。'),
        note('本馆的版本边界', '这里收录的是两份 Dartmouth 版本文献。两档都还没有独立的 Naru 前端；已有的 historical-basic64.bas 只是源文件样例，不代表 BASIC 编译器已经实现。'),
      ], ['fourth']),
    ],
    references: [ref('early', 'Dartmouth《BASIC》手册 · 1964 年 10 月', 'basic/1964/dtss-basic-manual-196410.pdf', '正文第 I 章、II §2.1（印刷页 1–3）；自编循环示例按 FOR / NEXT 形式整理'), ref('fourth', 'Dartmouth BASIC · 第四版', 'basic/1968/dtss-basic-4th-edition-196801.pdf', '目录、§2.6 Matrices、§2.7 Alphanumeric Information、附录 E Future Plans'), external('dartmouth', 'Dartmouth：BASIC 与分时计算的诞生', 'https://home.dartmouth.edu/news/2014/04/back-basic-computings-future-was-born-dartmouth', 'Dartmouth 官方历史回顾，2014')],
  },
  b: {
    name: 'B', fullName: 'B programming language', subtitle: '一切都是字，但每一个字都有来处。',
    origin: 'Bell Laboratories · 本馆语义锚为 1972 年手册', people: 'Ken Thompson / Dennis M. Ritchie；手册 S. C. Johnson',
    model: '无类型字机器 · lvalue / rvalue', setting: 'MH-TSS / Honeywell 6070；Naru 使用现代 64 位宿主',
    lead: 'B 处在 BCPL 与 C 之间。它用固定长度的“字”承载数值和地址，没有现代 C 那样的静态类型系统。熟悉 C 的人能认出许多外形，却也容易错读它的赋值算符、字符串和指针。本馆以 1972 年 MH-TSS 手册为考据对象，并关联实际的 b.stx 规则实现。',
    related: ['bcpl', 'c'],
    sections: [
      section('word', '读 B，先接受它的字机器', [
        p('B 的 rvalue 是定长位模式，lvalue 表示存储位置。* 将一个值作为地址间接访问，& 取得位置的地址。手册中的字长和字符打包方式带有宿主机器的痕迹：恢复语言，需要先说明恢复的是哪一台抽象机器。'),
        p('向量访问 v[n] 的语义与 *(v+n) 联系在一起。在字寻址模型中，地址加一指向下一个字；现代机器通常按字节寻址，所以规则必须在这两个单位之间转换。当前 b.stx 使用 i64，并写有指针除以 8、解引用前乘以 8 的转换。向量路径也存在缩放逻辑，仍需独立对拍，不能只依据文件注释认定正确。'),
      ], ['manual', 'rules']),
      section('assignment', '那个写成 =+ 的赋值算符', [
        code('让源代码自己说明年代', 'B · 规则库自带示例节选', 'i = 0;\nwhile (i < 10) {\n    v[i] = i + 1;\n    i =+ 1;\n}', ['=+ 是先等号、后运算符的复合赋值。', 'auto v[10] 的存储和地址行为应按 B 的向量规则理解。', '完整例子见复原记录中的 vector.b；这里没有宣称此次重新运行通过。']),
        table(['读法', 'B', '现代 C'], [['复合赋值', 'x =+ 1', 'x += 1'], ['字符转义', '*n、*t', '\\n、\\t'], ['字符串终止', '手册使用 *e（EOT）', 'NUL'], ['指针递增单位', '字模型中的下一个字', '指向类型的下一个元素']]),
        p('这些差别很适合保存在百科正文中。读者既能了解符号为什么改变，也能在版本选择时知道自己正在使用哪套规则。B 的规则不能因外形接近就直接替换成 C 的规则。'),
      ], ['manual', 'tutorial']),
      section('context', '同一个 &，要看它出现在哪里', [
        p('MH-TSS 手册 §12.4 讨论了真值环境下的 &：在 if、while 等条件中，它可以表现为逻辑组合。考古不能仅把 C 的按位与语义搬过来；这种语境相关的行为也是语言实现的一部分。'),
        p('现有 B 方言使用基础数值、管线、树和控制流规则，补充自己的词法与字语义。独立方言可以复用这些基础设施，但共享模块并不意味着 B 与其他表面语言自动互操作。规则组合出现冲突时，编译器仍应报告冲突。'),
      ], ['manual', 'rules']),
      section('fidelity', '复原语言，也要记录宿主差异', [
        p('本实现选择现代 64 位字和现代链接环境。手册中的多字符打包、库函数集合与历史机器位宽不能据此视为原样复现。为了展示一门老语言，可以先建立一种可运行的现代宿主解释，再明确写出它与原机器的差别。'),
        note('当前宿主实现的边界', '2026-10-12 调试已修复下标重复缩放、比较结果存储及字符串地址等路径，并增加 O0/O2 回归。外部向量名重绑定尚无独立地址槽，现明确拒绝；历史打包和完整运行库仍未复原。详见下方复原记录中的方言调试文档。'),
      ], ['rules', 'implementation']),
    ], references: [ref('manual', 'S. C. Johnson：Users’ Reference to B', 'b/1972/users-reference-to-b.pdf', '§3、§4.12、§6.2、§12.4；以 MH-TSS 手册为语义锚'), ref('tutorial', 'Brian W. Kernighan：B 教程', 'b/1972/b-tutorial-kernighan.pdf', '函数、表达式与程序示例'), external('rules', 'Naru B 方言规则', '/implementation/dialects/b.stx.txt', '当前工作区快照；历史行为的实现证据'), external('implementation', 'B 实现记录与已知偏离', '/implementation/docs/b.md.txt', '包含早期测试结果；与当前规则差异需重新验收')],
  },
  pascal: {
    name: 'Pascal', fullName: 'Pascal', subtitle: '类型与结构，成为教学的一部分。', origin: '1970 · ETH Zürich',
    people: 'Niklaus Wirth', model: '静态类型 · 块结构 · 过程与函数', setting: 'Wirth 报告 / Pascal-P / ISO 7185',
    lead: 'Pascal 把数据组织和程序结构放在显眼的位置。它既是一门语言，也是一段围绕教学、可移植编译器和标准化展开的历史。本馆区分早期报告谱系与 ISO 标准谱系；已有 pascal.stx 以 ISO 7185 为目标，实现了其中一部分表面语法与行为。',
    related: ['algol', 'simula', 'c'],
    sections: [
      section('structure', '声明与执行，在版面上就能分辨', [
        p('Pascal 程序在进入 begin…end 的执行部分前声明常量、变量和子程序。:= 表示赋值，= 用于比较。这样的外观让初学者较容易把“这个对象是什么”与“现在对它做什么”分开阅读。'),
        code('函数的结果写到函数名上', 'Pascal · examples/pascal/showcase.pas 节选', 'function triple(n: integer): integer;\n    begin\n        triple := 3 * n\n    end;', ['形参 n 和函数结果都声明为 integer。', 'triple := ... 设置函数结果；这不是现代 return 关键字。', '当前规则为函数建立结果槽，在函数体结束时返回。']),
        p('但不能仅凭 begin/end 就认定完整 Pascal 已经实现。子界、集合、记录、文件、指针、嵌套作用域与参数规则共同决定了真实程序能否运行。'),
      ], ['report', 'standard', 'rules']),
      section('portable', 'Pascal-P 与“带着编译器走”', [
        p('本馆的早期 Pascal 档案同时保存修订报告、P-machine 描述和 Pascal-P 实现笔记。这些资料记录了另一条复原路径：先实现一种中间机器，再把解释或生成机制带到不同宿主。它与仅仅保存一份语法表有很大区别。'),
        p('展示时应分开语言版本与编译器实现。P-machine 文档的年代不等于 Pascal 最初设计的年代；Pascal-P 也不是所有 Pascal 方言的共同运行时。'),
      ], ['report', 'pmachine']),
      section('standardization', '标准化改变了哪些边界', [
        table(['档案层次', '所保存的问题', '实现状态'], [['早期报告谱系', 'Wirth 语言设计；本馆保存 1972 修订报告', '没有独立的早期模式'], ['ISO 7185 谱系', '程序、类型、参数与文件行为的规范', 'pascal.stx 实现子集'], ['厂商扩展', '例如 halt 等约定', '现有规则接受部分扩展，不能作为 ISO 保证']]),
        p('ISO 条目标题使用标准谱系的年份，馆内原件则是 1990 年版。百科将两种年代同时列出，避免读者把“1983 年形成的标准谱系”和“这份具体 PDF 的出版时间”混为一谈。'),
        p('实除、大小写折叠、常量只读和全局声明对子程序的可见性已有修复与运行回归。当前实现仍缺少完整的集合、记录、嵌套过程及参数规则；显示“ISO 7185 目标子集”与现有验收证据相符。'),
      ], ['standard', 'implementation']),
      section('for', '一个 for 循环也有值得保存的行为', [
        p('循环上下界的求值时机是语言规则，不只是优化细节。现有 Pascal 方言把终值表达式存入私有槽，使它只求值一次，再用控制流设施构造循环。这样的例子说明：复用基础控制流不妨碍保留语言自己的语义。'),
        p('另一项是悬空 else。当前语法通过 fallback 规则让 else 与最近的 if 配对，并提供 dangling_else.pas 样例。这些可核对的小问题，比一个笼统的“支持控制流”更能说明复原到哪一步。'),
      ], ['rules', 'implementation']),
    ], references: [ref('report', 'Wirth：Pascal 修订报告', 'pascal/1970/pascal-revised-report-1972.pdf', '1972 报告；早期语言谱系'), ref('pmachine', 'P-machine 描述', 'pascal/1970/p-machine-description-1973.pdf', '1973 中间机器资料'), ref('standard', 'ISO 7185：Standard Pascal', 'pascal/iso-1983/iso7185-1990.pdf', '馆藏为 1990 版，条目记录 1983 标准谱系'), external('rules', 'Naru Pascal 方言', '/implementation/dialects/pascal.stx.txt', '程序展开、函数结果、for 与 case 规则'), external('implementation', 'Pascal 实现与偏离记录', '/implementation/docs/pascal.md.txt', '已实现语法及未完成的标准行为')],
  },
  c: {
    name: 'C', fullName: 'C programming language', subtitle: '书、机器与标准，共同塑造一门语言。', origin: '1970 年代 · Bell Laboratories', people: 'Dennis M. Ritchie / Brian W. Kernighan；ANSI / ISO 工作组',
    model: '类型化系统语言 · 指针 · 预处理', setting: 'Unix / K&R / 厂商方言 / ANSI 与 ISO 标准',
    lead: 'C 不是一份永远不变的语法。K&R 第一版、标准前的厂商实现、C89、C99 与 C11 具有不同的约束和设施。本馆把这些阶段分别立档；当前 Naru 的实现入口是 C11，没有把所有历史 C 自动宣布为可编译。',
    related: ['b', 'bcpl', 'pascal'],
    sections: [
      section('from-b', '从字机器走向类型化的地址运算', [
        p('Ritchie 对 C 发展过程的回顾把 BCPL、B 与 C 联系起来。C 的类型信息让地址运算依赖对象类型：指针加一所跨越的距离，与所指对象的大小有关。读 B 与 C 的同形表达式时，这层差别尤其重要。'),
        p('这里既保存语言的演进，也保留机器背景。PDP-11 上的 int 与指针布局不应默认为今天 Windows x64 的 ABI；现代宿主编译、历史语义复原与原机器仿真需要分别描述。'),
      ], ['history']),
      section('functions', '从旧式参数表，到带类型的接口', [
        code('相似的函数，不同年代的接口', '历史写法对照 · 自编示例', '/* K&R 风格 */\nint add(a, b)\nint a, b;\n{ return a + b; }\n\n/* 带原型的形式 */\nint add(int a, int b)\n{ return a + b; }', ['旧式定义先列形参名字，再在函数体前声明类型。', '带类型的原型为调用点提供更多检查信息。', '历史形式的展示不意味着当前 C11 方言已经支持该复原模式。']),
        p('K&R 第一版是关键的语言记录，但不是后来 ANSI / ISO 标准的替代文本。厂商在标准形成前也加入自己的特性；本馆的“1984”卡片实际关联 1986 年 Microsoft C 4.0 手册，因此年份和具体文献仍要分开。'),
      ], ['history', 'vendor', 'c89']),
      section('standards', '标准不是简单地不断增加关键字', [
        table(['版本', '值得单独阅读的变化', '本馆依据'], [['C89 / C90', '形成共同规范；原型、限定符与运行库约定', '公开草案与 Rationale'], ['C99', '声明位置、复合字面量、指定初始化、可变长数组等', 'N1256，整合勘误的委员会草案'], ['C11', '_Generic、_Static_assert、原子与线程相关设施等', 'N1570 委员会草案']]),
        p('草案与正式出版的标准不能直接划等号。本文列出文献身份，正文按主题解释变化；要验证某个边界行为，仍需回到具体条款与实现测试。尤其是标准允许的可选设施和实现定义行为，不能用版本标签代替说明。'),
      ], ['c89', 'c99', 'c11']),
      section('real-projects', '从一段表达式，到真实的 C 项目', [
        p('真实 C 项目会碰到 #include、宏、typedef、复杂声明器、结构布局、初始化和链接。当前 Naru C11 规则把词法、预处理、语法、语义、对象、布局和初始化拆成可组合模块，入口文件可以直接是 .c。'),
        p('实现使用系统头文件与系统 C 运行库，避免用一套自写简化 stdio 冒充项目兼容性。仓库的压力测试记录包含 TinyExpr 与 cJSON，并有声明器、系统 I/O、布局等用例。保存的通过数量见下方复原记录；报告明确不声称完整 C11 一致性，页面也没有重新运行这些测试。'),
        note('当前宿主', '现有规则和测试围绕 Windows x64 / LLP64。完整 C11 覆盖、其他平台 ABI 与历史 K&R 行为仍须分别验收。百科不会用“有 C11”替代这些边界。'),
      ], ['rules', 'stress']),
    ], references: [ref('history', 'Dennis M. Ritchie：The Development of the C Language', 'c/kr/1978/dmr-the-development-of-the-c-language.pdf', '1993 回顾；BCPL、B、C 谱系与设计动机'), ref('vendor', 'Microsoft C 4.0 Language Reference', 'c/kr/1984/msc40-language-reference-1986.pdf', '1986 厂商实现资料'), ref('c89', 'ANSI C89 公开草案', 'c/89/c89-draft.txt', '草案文本，非正式出版标准'), ref('c99', 'WG14 N1256', 'c/99/n1256.pdf', 'C99 与技术勘误的整合草案'), ref('c11', 'WG14 N1570', 'c/11/n1570.pdf', 'C11 委员会草案'), external('rules', 'Naru C11 规则入口', '/implementation/dialects/c11.stx.txt', '导入模块、原始文件前端与整程序关系'), external('stress', 'C11 已保存压力测试报告', '/implementation/target/c11-stress-current.json', '记录结果；不声称完整标准一致性')],
  },
  fortran: {
    name: 'FORTRAN', fullName: 'Formula Translation', subtitle: '纸上的算式，成为机器上的工作。', origin: '1950 年代 · IBM', people: 'John Backus 与 IBM 团队',
    model: '数值计算 · 数组 · 子程序', setting: 'IBM 704 / FORTRAN II / FORTRAN 66 / FORTRAN 77',
    lead: 'FORTRAN 将工程与科学计算中的公式变成可编译的程序。本馆以 FORTRAN II 的 IBM 704 手册为起点，再关联 1966 与 1978 年的标准谱系。固定格式、共享数据和子程序接口需要按版本理解，不能把现代 Fortran 的写法倒置到早期语言。', related: ['basic', 'algol', 'pli'],
    sections: [
      section('formula', '公式翻译，同时也是编译器的承诺', [p('早期 FORTRAN 的价值不仅在于用算式代替机器指令，还在于编译出的程序是否足够有效率。馆藏的 Backus 1957 年论文与 FORTRAN II 手册分别提供设计背景和使用层面的证据。两份文献的年代与对象不同，阅读时应彼此补充。'), p('FORTRAN II 的子程序与 COMMON 让较大的数值程序可以分工组织。共享存储把接口、布局和机器习惯联在一起；复原时不能只重建表达式的语法。')], ['manual', 'backus']),
      section('columns', '一行纸，真的有语法', [p('固定格式源文件把标号、续行和正文安排在不同列。列位置本身是词法信息，不能先把空白全部压缩，再期待恢复同一程序。卡片时代留下的限制，需要在前端扫描规则中明确保存。'), note('固定格式前端仍待实现', '现有 text.* 和扫描设施可以成为工具，但仓库尚无 FORTRAN 独立方言。列规则、续行、隐式类型、DO 与历史 I/O 的行为都需要专门的验收。')], ['manual']),
      section('continuity', '从机器手册，到共同标准', [table(['版本', '档案重心', '馆藏状态'], [['FORTRAN II · 1958', 'IBM 704 使用与子程序模型', '手册原件'], ['FORTRAN 66', '首个正式标准谱系', '引用卡'], ['FORTRAN 77 · 1978', '字符类型与结构化控制等标准演进', '引用卡']]), p('66 与 77 的条目目前提供文献线索，尚未收藏标准正文。本馆会保留这一事实。标准版本对应的复原不能由 II 手册自动外推，也不能仅因为通用数组规则存在就视为完成。')], ['standards']),
    ], references: [ref('manual', 'IBM 704 FORTRAN II Reference Manual', 'fortran/ii-1958/c28-6000-2-fortran-ii-reference-manual.pdf', '1958 使用手册；子程序、COMMON 与源格式'), ref('backus', 'Backus：FORTRAN 自动编程系统', 'fortran/ii-1958/backus-fortran-automatic-programming-1957.pdf', '1957 系统论文'), external('standards', 'Software Preservation Group：FORTRAN 文献项目', 'https://www.softwarepreservation.org/projects/FORTRAN/', '本馆 66 / 77 引用卡所列文献线索')],
  },
  algol: {
    name: 'ALGOL', fullName: 'Algorithmic Language', subtitle: '让算法拥有可以讨论的结构。', origin: '1958 / 1960 · 国际委员会', people: 'Peter Naur（报告编辑）与 ALGOL 委员会',
    model: '块结构 · 词法作用域 · 过程', setting: 'IAL / ALGOL 58 / ALGOL 60 报告',
    lead: 'ALGOL 的报告把语言当作可以严密描述、共同讨论的对象。begin/end、嵌套块、过程参数以及语法记法都成为后世语言的重要参照。本馆分开 ALGOL 58 的初步报告与 ALGOL 60 的修订报告，避免把它们合并成一个没有变化的标签。', related: ['pascal', 'simula', 'basic'],
    sections: [
      section('block', '块把名字放回它所属的地方', [p('ALGOL 60 的块结构把声明与语句组织在一个范围内。嵌套块使同一个名字可以在不同范围具有不同含义；这要求实现处理作用域，而不只是把 begin/end 换成另一种括号。'), p('报告区分参考语言、出版表示与硬件表示。印在论文里的下标、字体或分隔形式，未必直接等于某台计算机接受的输入。这对数字档案馆很有意义：保存排版与恢复输入规则，是两个互相联系的工作。')]),
      section('name', '按名调用，不能简单理解为按值', [p('ALGOL 60 的过程参数包括按值与按名的区别。按名参数的效果与调用处表达式、替换和环境相关，复原时需要认真处理绑定和重复求值；不能用普通 C 函数调用直接替代。'), note('语义复原的下一步', '通用闭包、作用域和控制流设施可以提供基础，但目前没有 ALGOL 前端与按名参数验收。共享基础设施的存在，不等于该语义已经完成。')]),
      section('reports', '报告本身也有版本', [table(['档案', '文献身份', '阅读重点'], [['58 / IAL', '1958 初步报告，馆内为引用卡', '共同语言的早期构想'], ['60 / Revised Report', '馆藏 1963 修订报告', '块、过程、参数与正式语法'], ['Modified Report', '馆藏 1976 修改报告', '后续澄清；不能默默覆盖旧报告']]), p('一个百科条目应告诉读者当前解释依据哪份报告。修改稿可以用于比较，但不应让历史上的模糊或分歧从页面中消失。')], ['manual', 'modified', 'ial']),
    ], references: [ref('manual', 'Revised Report on ALGOL 60', 'algol/60/revised-report-algol60-1963.htm', '§1 语言表示；§4.7 过程语句；§5 块与声明'), ref('modified', 'Modified Report on ALGOL 60', 'algol/60/modified-report-algol60-1976.htm', '1976 修改报告'), external('ial', 'IAL 初步报告', 'https://dl.acm.org/doi/10.1145/368976.368999', '1958，馆内保留引用卡')],
  },
  cobol: {
    name: 'COBOL', fullName: 'Common Business-Oriented Language', subtitle: '在业务数据中，语言长出另一种形状。', origin: '1959–1960 · CODASYL', people: 'CODASYL 委员会', model: '记录与字段 · 业务处理 · 十进制数据', setting: '1960 原始报告',
    lead: 'COBOL 为业务处理而设计，数据记录、字段描述与面向业务的语句都占据显著位置。它与数值计算语言关注的对象不同。本馆当前以 1960 年原始报告为语义资料，未将现代 COBOL 的功能集合归入这一早期版本。', related: ['pli', 'fortran'],
    sections: [
      section('data-first', '先描述业务数据，再描述业务动作', [p('COBOL 的程序以分部组织内容。DATA DIVISION 描述记录与字段，PROCEDURE DIVISION 组织操作。这样的结构回应了文件处理、工资和账务等任务：数据格式本身就是程序的重要部分。'), p('字段的 PICTURE 不是界面标签。它描述字符或数值形态，也影响存储、转换与输出。真实的复原需要处理十进制、记录布局、文件组织和字段操作，而不仅是把英语式语句翻译成算术。')]),
      section('procedure', '接近叙述的外表，也有精确规则', [p('MOVE、ADD 与 PERFORM 等形式让业务操作更接近书面叙述，但仍是有严格约束的编程语言。句子终结、段落与控制转移的历史形式不能直接套上现代块结构的直觉。'), note('当前复原缺口', 'records 与 numbers 可作为底层组合候选，尚无 COBOL 词法、PICTURE、十进制业务行为或文件前端。页面因此展示文献与自编解说，不提供虚假的运行按钮。')]),
      section('living', '保存早期报告，不等于宣布语言消失', [p('数字档案馆收藏一种语言的历史版本，并不意味着这门语言已经退出使用。COBOL 条目的重点是 1960 年的定义、当时的问题与后来版本的差异；现代实现与早期报告必须分开考据。')]),
    ], references: [ref('manual', 'CODASYL COBOL 原始报告', 'cobol/60/cobol-report-apr1960.pdf', '1960 年 4 月；数据描述与过程分部')],
  },
  lisp: {
    name: 'LISP', fullName: 'List Processing', subtitle: '程序与数据，在括号里相遇。', origin: '1960 · MIT 论文谱系', people: 'John McCarthy；LISP 1.5 手册团队', model: '符号计算 · S 表达式 · 递归', setting: '1960 论文 / LISP 1.5',
    lead: 'LISP 以符号表达式、列表和递归描述计算。1960 年论文与 1962 年 LISP 1.5 手册分别展示理论构想和实际系统。本馆保留这两层记录；不能把今天某个 Lisp 的作用域、宏系统或对象设施默认算作 LISP 1.5 的特性。', related: ['algol', 'apl'],
    sections: [
      section('sexpr', '一种结构，既能写数据，也能写程序', [p('S 表达式可以是原子，也可以通过成对结构组成列表。CAR、CDR 与 CONS 让程序能够拆解和构造这样的对象；QUOTE 则让表达式被当作数据保留下来。'), code('一个带引用的列表', 'LISP 1.5 风格 · 自编示例', '(CAR (QUOTE (ALPHA BETA)))', ['QUOTE 保留列表，不把 ALPHA 当成一次变量求值。', 'CAR 取得列表的首项。', '仅用于解释表达式结构；当前仓库没有 LISP 前端。'])], ['paper', 'manual']),
      section('evaluation', 'eval 的背后，还有环境和存储', [p('论文中的求值构想与实际 LISP 1.5 系统并非只有一行 eval 的差别。符号表、属性表、函数表示、作用域与存储管理都影响程序行为。动态环境与现代词法闭包也不能互相代换。'), p('原始文献同时使用不同表达记法。复原界面需要说明接受的是哪种写法，并保留文献中的理论表示与机器输入表示之间的关系。')]),
      section('storage', '列表会生长，也需要被回收', [p('不断构造列表的程序需要存储管理。LISP 1.5 手册记录了系统层面的表示和垃圾回收；因此把 S 表达式解析出来只完成了前端的一小部分。'), note('实现边界', '当前 Naru 的 tree / patterns 是编译期规则工具，不能直接当作 LISP 运行时堆与垃圾回收。历史语言的 runtime 仍需独立实现和验证。')]),
    ], references: [ref('paper', 'McCarthy：Recursive Functions of Symbolic Expressions', 'lisp/1960-recursion/mccarthy-recursive-functions-1960.pdf', '1960 论文；S 表达式与求值'), ref('manual', 'LISP 1.5 Programmer’s Manual', 'lisp/1.5/1962/lisp1.5-programmers-manual-1962.pdf', '1962 手册；系统、环境与存储管理')],
  },
  pli: {
    name: 'PL/I', fullName: 'Programming Language One', subtitle: '当科学计算与业务处理进入同一间房。', origin: '1960 年代 · IBM', people: 'IBM 与语言设计委员会', model: '多种数据属性 · 条件处理 · 多存储类', setting: '1966 IBM Language Specifications',
    lead: 'PL/I 试图在一种语言中容纳科学与业务计算的不同需要。本馆保存 1966 年 IBM 语言规范，以数据属性、存储和条件处理为阅读入口。它的历史不能用“功能很多”一句话概括，也不能只恢复几个关键字便称为兼容实现。', related: ['fortran', 'cobol', 'algol'],
    sections: [
      section('attributes', '声明是属性的组合', [p('PL/I 的声明把数据类型、精度、结构与存储属性组合起来。理解一个变量的行为，需要同时阅读这些属性。数值转换与存储安排因此也是语言定义的重要部分。'), p('这种组合体现了语言试图覆盖多种任务的方向。科学计算与业务处理需要的数值形态不同，统一它们意味着实现必须准确处理属性相互作用。')]),
      section('conditions', '把异常情况纳入程序', [p('ON 条件处理让程序能够为某些运行条件指定行为。它关联作用范围、处理器激活与控制转移，不能直接换成一个现代 try/catch 的外壳。复原需要按 1966 规范逐项核对可处理的条件及恢复方式。')]),
      section('reconstruction', '为什么适合做组合规则的压力测试', [p('PL/I 的属性组合、存储类和条件机制要求规则之间能够合作，也要求冲突得到明确报告。Naru 已有数字、布局、资源与控制流设施，但没有 PL/I 独立前端。它们可以降低未来实现成本，不能替代 PL/I 的语言规范。'), note('本馆范围', '当前条目仅对应 1966 年规范。其他 IBM 编译器版本、运行库和厂商扩展需要独立的版本条目与测试。')]),
    ], references: [ref('manual', 'IBM PL/I Language Specifications', 'pli/1966/c28-6571-3-pli-language-specifications-jul66.pdf', '1966 年 7 月，C28-6571-3')],
  },
  bcpl: {
    name: 'BCPL', fullName: 'Basic Combined Programming Language', subtitle: '一台抽象机器，可以抵达许多真实机器。', origin: '1967 · Martin Richards', people: 'Martin Richards', model: '字模型 · 向量 · 系统编程', setting: 'BCPL Reference Manual / OCODE / INTCODE',
    lead: 'BCPL 用简约的字模型构造系统程序，也是 B 和 C 谱系的重要前史。它的参考手册记录语言与中间表示之间的联系。本馆把语言层和机器层并排呈现，但没有把 B 方言误认为 BCPL 的实现。', related: ['b', 'c'],
    sections: [
      section('words', '用字组织系统', [p('BCPL 的数值与地址围绕机器字组织，向量访问与存储布局都带有这种模型的印记。没有现代类型系统，不意味着没有精确的规则；表示、地址单位与运算的解释仍然需要定义。')]),
      section('machine', '语言可移植，还需要一座桥', [p('OCODE 与 INTCODE 等中间机制展示了编译器如何跨越宿主差异。阅读手册时，可以分别追踪源语言、编译产物和执行机器：迁移工作通常发生在这些层次的边界上。'), p('Naru 的 MLIR 后端也提供分层空间，但历史中间机器的行为不会因此自动出现。若要运行旧的中间代码，需要另行实现它的机器契约。')]),
      section('lineage', '与 B 相连，也保留自己的语言', [p('BCPL、B 与 C 可以互相参照，但关键字、表达式和机器模型不能靠名字相近就共享同一解释。现有 B 方言中的字转换设施可供复用评估，BCPL 前端仍未建立。')]),
    ], references: [ref('manual', 'BCPL Reference Manual', 'bcpl/bcpl-reference-manual.pdf', '语言、向量与中间机制；具体手册修订年代须以原件为准')],
  },
  simula: {
    name: 'SIMULA', fullName: 'SIMULA 67', subtitle: '对象开始带着状态，参与一个运行中的世界。', origin: '1967 · Norwegian Computing Center', people: 'Ole-Johan Dahl / Bjørn Myhrhaug / Kristen Nygaard', model: '类 · 对象引用 · 准并行执行', setting: 'SIMULA 67 Common Base 报告谱系',
    lead: 'SIMULA 67 以类、对象和运行过程描述一个有状态的世界。它延续 ALGOL 的语言背景，又引入自己的对象与执行机制。本馆目前保留 Common Base 文献引用卡，尚未收藏报告正文；这里的解说是阅读入口，详细条款仍待原文考据。', related: ['algol', 'pascal', 'c'],
    sections: [
      section('objects', '一个类，保存状态与行为', [p('SIMULA 的类与对象不能仅用“带方法的结构体”理解。对象引用、类之间的关系和执行状态共同影响行为；现代对象语言的习惯需要逐项与历史资料核对。')], ['history']),
      section('process', 'detach 与 resume 指向另一种控制经验', [p('准并行机制允许运行过程保存状态、挂起并恢复。它不等于让操作系统同时启动多个线程。实现时需要明确栈、对象与恢复点之间的关系，而不是只把两个名字加入关键字表。')], ['history']),
      section('documents', '让尚未入库的原件也有位置', [p('馆藏引用卡保留了报告名称、作者和获取线索。文末另列可检索的 Common Base 报告镜像；它尚未复制到馆藏，具体版本与许可仍需核对。'), note('下一份关键材料', '报告版本核对、本地入库、具体实现手册与许可考据仍是主要工作。当前 Naru 没有 SIMULA 前端、对象运行时或准并行验收。')], ['history']),
    ], references: [external('history', 'SIMULA Common Base Language · 1970 修订版镜像', 'https://softwarepreservation.computerhistory.org/ALGOL/manual/Simula-CommonBaseLanguage.pdf', '1970 年 10 月，NCC S-22；§1.3 类与准并行机制。未复制到馆藏，入库许可仍待核对')],
  },
  apl: {
    name: 'APL', fullName: 'A Programming Language', subtitle: '把整个数组，当作一句话来思考。', origin: 'Iverson 记法 / IBM APL\\360', people: 'Kenneth E. Iverson 与 IBM 团队', model: '数组 · 专用符号 · 归约', setting: 'APL\\360 · 1969 Reference Manual',
    lead: 'APL 将数组运算浓缩成独特的符号语言。本馆关注 IBM APL\\360 手册所描述的环境：符号、数组维度、求值顺序与工作区一起构成使用经验。现代 APL 扩展不能默认属于 1969 年的这一版本。', related: ['fortran', 'lisp', 'basic'],
    sections: [
      section('arrays', '从逐个元素，到整个数组', [p('APL 把数组作为基本计算对象。形状、标量扩展与运算符的组合让很短的表达式完成一组数据的工作。复原时需要明确数组维度与元素行为，只有加减乘除的标量后端并不够。'), code('归约把一组值折叠为一个值', 'APL 风格 · 自编说明式', '+/ 1 2 3 4', ['+ 是求和所用的函数，/ 形成归约。', '这段表达式用于展示符号组合，不代表当前 Naru 已支持 APL。', '完整语言的求值与数组规则须按 APL\\360 手册验证。'])]),
      section('symbols', '字体、输入与语义的交界', [p('APL 的专用符号把键盘和显示设备也带进档案。扫描器需要辨认符号与组合，页面则需要能正确显示它们；如果只保存乱码文本，重要的语法信息就丢失了。'), p('求值顺序与现代常见的算术优先级也需要区别。读者应按手册理解表达式，不能仅凭外观把它解释成另一门语言的中缀运算。')]),
      section('workspace', '工作区也是语言生活的一部分', [p('APL\\360 的工作区与系统命令保存交互状态。数组语言本体可以成为独立规则组，终端、名称管理和工作区保存则需要环境设施。现有数组与 affine 规则提供底层工具，但尚无 APL 前端与运行时。')]),
    ], references: [ref('manual', 'APL\\360 Reference Manual', 'apl/360/apl360-reference-manual-aug69.pdf', '1969 年 8 月；数组、符号与工作区')],
  },
}

const version = (name, lead, focus, boundary, features, implementation, sections = []) => ({ name, lead, focus, boundary, features, implementation, sections })
export const versions = {
  'basic/1964': version('Dartmouth · 1964', '这份条目对应 1964 年 10 月的 Dartmouth BASIC 手册。它从数值问题讲起，用行号、LET、READ、DATA 和控制转移把程序带入分时终端。1964 是语言诞生的年份，本馆原件则是一份同年 10 月的具体手册。', '早期程序与分时学习环境', '不可自动等同后来的微机 BASIC。', ['行号与跳转', '数值算式', 'FOR / NEXT'], undefined, [section('early-reading', '1964 手册，如何带读者写第一段程序', [p('手册先用日常的步骤和配方解释程序，再引入解二元一次方程组的完整例子。这个入口说明 BASIC 的“初学者”定位并非只靠少几个关键字：教材叙事与终端环境也是设计的一部分。'), p('本馆的讲解示例采用重新编写的循环求和程序。仓库另有 historical-basic64.bas，但它尚未关联 BASIC 方言，不能作为已可运行项目展示。')], ['early'])]),
  'basic/1968': version('Dartmouth · 第四版 / 1968', '1968 年 1 月 1 日第四版把 BASIC 分成入门与高级两部分。矩阵、字母数字信息、函数与子程序有了专门的讲述；同时，附录仍记录尚在规划中的系统设施。', '基础语言如何扩展为更完整的工具', '目录的 Future Plans 不应列成已完成特性。', ['矩阵章节', '字母数字信息', '函数与子程序'], undefined, [section('fourth-reading', '第四版：读目录，也要读时态', [p('§2.6 Matrices 与 §2.7 Alphanumeric Information 出现在高级 BASIC 部分，适合与 1964 手册逐项比较。本文不把第四版的所有能力回填到早期版本。'), p('附录 E 列出的 data files、chaining of programs 等是未来计划。保存原文的这种区分，比用一张统一“支持功能”表更能还原当时的语言状态。')], ['fourth'])]),
  'b/1972': version('B · MH-TSS / 1972', '这份条目以 S. C. Johnson 的 MH-TSS B 手册为语义锚，同时展示 b.stx 和仓库样例。现代 64 位宿主的映射与手册行为分开记录，未把当前规则存在等同于完整历史一致性。', '字寻址、复合赋值与历史字符串', '宿主位宽、打包与库函数覆盖仍有差异。', ['字模型', '=+ 赋值', '* 转义'], 'b'),
  'pascal/1970': version('Wirth 报告谱系 · 1970', '1970 表示 Pascal 的早期语言谱系，馆内实际收藏 1972 修订报告、1973 P-machine 描述与 Pascal-P 实现笔记。年代标签不会替代各原件的身份。', '语言报告与可移植编译器', '目前没有独立的 Wirth 早期行为模式。', ['修订报告', 'P-machine', 'Pascal-P']),
  'pascal/iso-1983': version('ISO 7185 谱系 · 1983', '这个版本页关联标准 Pascal 谱系。馆藏正文是 ISO 7185:1990；现有 pascal.stx 以该标准为目标实现子集，并保留少量扩展和未完成行为的记录。', '标准语义与当前实现的边界', '不能把目标标准写成已通过完整一致性测试。', ['类型与参数规则', '程序与文件', '标准目标子集'], 'pascal'),
  'c/kr/1978': version('K&R · 第一版 / 1978', 'Kernighan 与 Ritchie 第一版记录了标准形成前的 C。本馆未收录该版权书籍原件，收藏的是 Ritchie 的发展回顾论文，并用条目记录旧式函数和历史机器语境。', '旧式参数表与书籍规范', '现有 C11 前端不是 K&R 独立复原模式。', ['旧式函数', 'Unix 背景', '书籍规范']),
  'c/kr/1984': version('标准前的厂商 C · 1984', '这一条目追踪标准形成前的厂商 C。当前具体原件为 1986 年 Microsoft C 4.0 语言参考手册；它展示一种实现，不能代表所有同年代编译器。', '厂商行为与向标准的过渡', '版本年标与手册出版年分开记录。', ['Microsoft C 4.0', '厂商扩展', '过渡阶段']),
  'c/89': version('ANSI C89 / ISO C90', 'C89 建立了共同的语言与运行库规范。本馆收藏公开草案及 Rationale 文本，用于核对标准化时的选择；它们不冒充正式出版的标准。', '共同约定与设计理由', '没有独立 C89 方言配置或一致性验收。', ['函数原型', '限定符', 'Rationale']),
  'c/99': version('ISO C99 · N1256', '这份条目以 N1256 为主要原件。该委员会草案整合了 C99 与后续技术勘误，适合核对指定初始化、复合字面量等设施，但不是 1999 年标准原件本身。', '语言扩展与技术勘误', '不能从 C11 模块的存在推断全 C99 兼容。', ['指定初始化', '复合字面量', '可变长数组']),
  'c/11': version('ISO C11 · N1570', '本条目同时关联 N1570 文献与实际 C11 规则实现。读者可以沿词法、预处理、语义、布局和初始化模块追踪实现，也能查看保存下来的真实项目压力测试结果。', '模块化实现与真实项目', '记录通过的用例，不宣称完整 C11。', ['_Generic', '静态断言', '系统头文件与 CRT'], 'c11'),
  'fortran/ii-1958': version('FORTRAN II · IBM 704 / 1958', 'IBM 704 手册记录了 FORTRAN II 的源格式、子程序与共享数据。这里的机器背景具体而明确；现代 Fortran 的自由格式与新特性并不属于这一档。', '子程序、COMMON 与卡片格式', '尚无 FORTRAN 前端。', ['固定格式', '子程序', 'COMMON']),
  'fortran/66': version('FORTRAN 66 · X3.9', '1966 标准谱系使 FORTRAN 从机器手册走向共同约定。当前馆藏为引用卡，正文尚未收藏；条目保留文献线索和与 II、77 的阅读关系。', '首个正式标准谱系', '无原件，也无专用方言。', ['标准化', '数值计算', '版本边界']),
  'fortran/77': version('FORTRAN 77 · 1978', 'FORTRAN 77 条目对应 1978 年标准谱系，关注字符与控制结构等演进。馆内目前只有引用卡，不能用现代编译器的默认行为替代原文。', '旧程序与新标准的连接', '尚无原件及独立版本配置。', ['字符类型', '结构化控制', '标准演进']),
  'algol/58': version('ALGOL 58 / IAL', '1958 初步报告是共同算法语言的一次早期约定。本馆保留出版引用；ALGOL 60 的后续报告不能直接作为这份语言的完整定义。', '国际共同语言的早期构想', '初步报告正文未入库。', ['IAL', '初步报告', '委员会设计']),
  'algol/60': version('ALGOL 60 · 修订报告', '本页关联 1963 修订报告与 1976 修改报告。块、过程、按名参数和语言表示是主要阅读主题；后续澄清与历史定义并排保存。', '块结构与按名参数', '尚无 ALGOL 前端或按名调用验收。', ['词法作用域', '按名调用', '报告修订']),
  'cobol/60': version('COBOL · 1960 原始报告', '这一页保留 CODASYL 1960 原始报告所面对的业务计算问题。记录、字段与过程组织分别讲解，现代 COBOL 的扩展不回填到这个版本。', '业务数据描述', '尚无 COBOL 方言。', ['PICTURE', '分部', '业务处理']),
  'lisp/1960-recursion': version('LISP · 1960 论文', 'McCarthy 的论文提供符号表达式与递归计算的理论入口。本文将它与实际 LISP 1.5 系统区分，不把论文中的记法自动当作某个编译器的输入格式。', 'S 表达式与求值构想', '论文模型与系统实现分开考据。', ['递归函数', 'S 表达式', '求值']),
  'lisp/1.5/1962': version('LISP 1.5 · 1962', 'LISP 1.5 手册把符号、环境、存储与程序运行放入一个实际系统。馆内有 PDF 原件和 OCR 文本；OCR 用于检索，原件用于复核。', '实际系统、符号表与存储', '编译期 tree 工具不等于 LISP runtime。', ['符号表', '动态环境', '垃圾回收']),
  'pli/1966': version('PL/I · IBM / 1966', '1966 年 IBM 规范记录了 PL/I 对科学与业务计算的综合。数据属性、存储与条件机制需要一起阅读，而非只看一份关键字列表。', '属性组合与条件处理', '尚无 PL/I 前端。', ['数据属性', 'ON 条件', '存储类']),
  bcpl: version('BCPL · 1967 谱系', '本馆以 BCPL 参考手册为阅读依据，关注字模型、向量与中间机器。1967 表示语言谱系起点，具体手册修订信息以原件为准。', '语言与中间机器', 'B 实现不能替代 BCPL。', ['字模型', 'OCODE', 'INTCODE']),
  'simula/67': version('SIMULA 67 · Common Base', '这份版本页以 Common Base 报告谱系为线索。目前馆内是引用卡，尚无报告正文；类、引用和准并行行为需要进一步按原文考据。', '对象与执行状态', '无原件及独立实现。', ['class', '引用', 'detach / resume']),
  'apl/360': version('APL\\360 · 1969 手册', '这份 IBM 手册记录的是 APL\\360 的数组语言与交互环境。符号、求值顺序和工作区具有版本身份，不能把后来的 APL 扩展一并归入。', '数组、符号与工作区', '尚无 APL 前端和数组运行时。', ['数组', '归约', 'workspace']),
}

// Version-specific reading notes supplement, rather than replace, the family article.
versions['c/kr/1978'].sections = [section('kr-interface', 'K&R 的接口，要连同调用点一起读', [p('旧式函数定义把参数名和类型声明分开。阅读旧代码时，还要核对是否存在函数声明、调用点如何提升实参，以及所依赖的编译器与机器。仅把参数表改成现代写法，不足以证明程序行为已经保持。'), p('本馆保存发展论文，书籍第一版保留引用身份。当前没有 kr.frontend 这样的独立入口；关于历史隐式规则的考据不作为现有 C11 能力展示。')], ['history', 'c89'])]
versions['c/kr/1984'].sections = [section('vendor-c', '厂商手册把“那个年代的 C”变得具体', [p('这一档的价值在于观察一种实际编译器如何解释语言。要复原旧项目，编译器版本、数据模型、预处理习惯与库接口往往和语法同样重要。'), p('1984 是本馆的阶段标签，原件是 Microsoft C 4.0 的 1986 手册。未来若加入其他厂商实现，应各自立档；不能从这一份手册推断所有标准前的 C。')], ['vendor'])]
versions['c/89'].sections = [section('c89-rationale', '标准正文规定行为，Rationale 解释选择', [p('C89 的公开草案与设计理由文档提供两种阅读方式：前者描述约束与行为，后者解释委员会如何面对既有实践。Rationale 适合帮助理解标准，但不能替代规范文本。'), p('馆内按章节保存的 Rationale 也可从文末原件区取得。草案、设计理由与正式标准具有不同文献身份；旧式函数等历史遗留问题需要结合具体条款阅读。')], ['c89', 'rationale'])]
versions['c/99'].sections = [section('c99-initializers', '初始化开始能直接表达数据的形状', [code('指定要初始化的字段', 'C99 起的形式 · 自编讲解示例', 'struct Point { int x; int y; };\nstruct Point p = { .y = 8, .x = 3 };', ['字段设计符让初值明确关联到成员。', '这项语法有版本身份，不属于 K&R 第一版。', '是否支持任意真实初始化场景，需要单独查看方言与测试。']), p('N1256 是整合技术勘误的委员会草案。它适合核对 C99 规则，但百科仍保留它的文献身份，而不是把文件名直接改写为正式标准。')], ['c99'])]
versions['c/11'].sections = [section('c11-selection', '语法之后，还有类型驱动的选择', [p('_Generic 根据控制表达式的类型选择关联项。这样的机制说明语言扩展不只发生在解析阶段：语法、类型检查和后续生成要共同定义行为。'), p('当前 C11 入口由许多规则模块组合而成。初始化和布局等设施既有独立文件，也有实际项目压力测试；下方复原记录展示已保存的结果，完整标准一致性仍是另一个需要验证的问题。')], ['c11', 'rules', 'stress'])]
versions['pascal/1970'].sections = [section('wirth-reading', '报告与 P-machine，是两条相连的阅读线', [p('报告描述语言，P-machine 与实现笔记描述如何把语言带到机器上。本馆分别保留这些原件，避免把一个编译器实现的习惯当作所有早期 Pascal 的共同规定。'), p('现有 pascal.stx 以 ISO 7185 为目标，尚无可切换的 Wirth 早期语义档。这个版本页展示文献谱系，不以现代规则替代原定义。')], ['report', 'pmachine'])]
versions['pascal/iso-1983'].sections = [section('iso-reading', '标准目标，与已实现子集之间', [p('标准规定的参数、类型与文件行为比一套 begin/end 语法广得多。现有方言提供函数、过程、基础类型和控制语句，仍需补齐集合、记录、嵌套过程等设施。'), p('馆藏为 1990 年 ISO 文本，页面按 1983 标准谱系归类。记录标准年份、原件年份、规则目标和偏离，能让未来的验收知道自己正在对齐哪一层证据。')], ['standard', 'implementation'])]
families.c.references.push(ref('rationale', 'ANSI C Rationale · 章节存档', 'c/89/rationale/title.html', '馆藏按章节保存；设计理由不替代标准正文'))


