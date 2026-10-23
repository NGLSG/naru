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
- 与 Naru 方言的关系: `dialects/c11/` 的历史基准;K&R 特有行为(默认 int、旧式函数声明、隐式声明)
  对应 C89 中的 obsolescent 特性,重构 K&R 方言时以本条目为准
- 备注: C 语言在 1978 年是"书即规范";K&R 1 版与 V7 手册间存在已知细节差异(K&R 承认其示例
  按 PDP-11 语境书写)。重构需在 notes.md 中逐步记录这些分歧。
