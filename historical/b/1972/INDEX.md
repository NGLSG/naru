# B 语言参考与教程(1972–1973)

- 类型: 手册 + 教程(PDF 原件,文字版扫描)
- 主体/作者: S. C. Johnson, B. W. Kernighan(Bell Laboratories,MM 72-1371-1);K. Thompson(语言设计)
- 年份: 1972(参考);1973(教程)
- 考据对象: 《Users' Reference to B》——无类型字机器模型、BCPL 派生语法、
  函数与向量语义;Kernighan《A Tutorial Introduction to the Language B》
- 许可: 自由流传(dmr 站点原发布;经 Internet Archive 快照获取)
- 来源: http://cm.bell-labs.com/cm/cs/who/dmr/bref.pdf 、btut.pdf(原站已下架,
  取自 web.archive.org 2015-03-11 快照)
- 获取日期: 2026-10-11
- 文件清单:
  - `users-reference-to-b.pdf` — 49 KB
  - `b-tutorial-kernighan.pdf` — 44 KB
- 与 Naru 方言的关系: **方言已实现里程碑 1+2**(`dialects/b.stx` + `docs/b.md`):字机器模型(64 位字、字节地址、向量索引缩放)、无类型表达式、lvalue/rvalue 算符 * 与 &、17 个赋值算符、auto/extrn/外部定义、if/while/return、putchar/char/lchar 内在函数,十个示例程序原生运行验证(含递归 fact(5)=120)。goto/标签(§5.5-6.3)、条件逻辑 &(§12.4)、向量外部定义(§7.2)已实现;switch(§5.4)、printf、向量高索引寻址修复在里程碑 3
- 备注: B 依赖 BCPL 运行时概念;BCPL 条目(bcpl/)提供其上游语义
