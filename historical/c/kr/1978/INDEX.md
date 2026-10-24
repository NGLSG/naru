# C 谱系 · K&R 时代(1978 年第 1 版及其前史)

- 类型: 混合条目(论文原件 + 版权著作引用)
- 主体/作者: Dennis M. Ritchie; Brian W. Kernighan
- 年份: 1974–1978(回顾论文 1993)
- 考据对象: K&R C 的语言行为以《The C Programming Language》第 1 版(1978)附录参考手册为准
- 许可: 版权保留-仅引用(书籍);自由流传(论文、Unix 手册)
- 来源: https://port70.net/~nsz/c/c89/ (回顾论文镜像,原站 dmr 已下架)
- 获取日期: 2026-10-11
- 文件清单:
  - `dmr-the-development-of-the-c-language.pdf` — Ritchie《The Development of the C Language》(CHM 1993),谱系与设计动机的权威回顾
- 版权著作(不收原件):
  - Kernighan & Ritchie《The C Programming Language》1st ed., Prentice-Hall 1978, ISBN 0-13-110163-3
  - Ritchie《C Reference Manual》5th/6th ed.(1974–1976)——权威电子文本为 Unix V7
    手册第 2 卷,TUHS utree 路径 `V7/usr/doc/cman`、`V7/usr/doc/ctour`;
    注意 utree 因版权原因屏蔽了这两个文件的直接读取(2026-10-11 实测),
    获取途径为纸质 V7 手册或待授权的数字化副本
  - Kernighan《Programming in C: A Tutorial》(1974),同见 V7 手册第 2 卷
- 与 Naru 方言的关系: **方言已实现里程碑 1-7(全覆盖)**(`dialects/kr.stx` + `docs/kr.md`):整型/指针机器、
  K&R 转换全套、旧式函数定义、隐式声明、默认 int、goto/do-while/for(精确 continue 语义)、
  可写字符串字面量、sizeof、float/double、switch(落空穿透)、逗号算符、数组初值列表、
  char[]=字符串、static/extern 数据、struct/union(无结构赋值档)、case 常量表达式、
  局部 static、#define/#undef(位置语义)、typedef、函数指针(间接调用、函数名退化),
  位域(符号提取/RMW/零宽/无名填充/char 与 long 容器)、成员与全局函数指针、
  指向数组的指针、register/auto、前向声明、条件编译(#ifdef 族/#line)、
  多维数组(行主序/子数组衰减/sizeof 不退化)、函数指针数组,
  33 个示例程序原生运行验证(power/swap/fahr 为原书程序重写)。
  K&R 1 版语言面全覆盖(刻意缺口仅 entry/#include/多字符常量,均为忠实性记录)。
- 备注: C 语言在 1978 年是"书即规范";K&R 1 版与 V7 手册间存在已知细节差异(K&R 承认其示例
  按 PDP-11 语境书写)。重构需在 notes.md 中逐步记录这些分歧。
