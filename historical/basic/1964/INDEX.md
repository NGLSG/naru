# Dartmouth BASIC 原始手册(1964-10)

- 类型: 手册(扫描原件 ×2)
- 主体/作者: J. G. Kemeny, T. E. Kurtz(Dartmouth College,DTSS)
- 年份: 1964(4th ed. 1968 另列)
- 考据对象: 1964 年 10 月版《BASIC》手册——LET/PRINT/INPUT/READ/GOTO/IF-THEN/FOR-NEXT/
  DIM/DEF FN/MAT 语句与 DTSS 交互环境的原始定义
- 许可: 自由流传(bitsavers 收录)
- 来源: https://bitsavers.org/pdf/dartmouth/dtss/
- 获取日期: 2026-10-11
- 文件清单:
  - `dtss-basic-manual-196410.pdf` — 196410_BASIC.pdf(2.15 MB)
  - `dtss-basic-summary.pdf` — BASIC_summary.pdf(语言摘要,114 KB)
- 与 Naru 方言的关系: **方言已实现里程碑 1 + 2**(`dialects/basic.stx` + `docs/basic.md`):
  行号程序(行号→CFG 标签)、LET/隐式赋值、PRINT(逗号分区/分号)、INPUT、
  READ/DATA/RESTORE、DIM(一维/二维)、GOTO、IF-THEN <行号>、GOSUB/RETURN(嵌套)、
  FOR/NEXT(含 STEP 与负步长)、DEF FN(单参数)、标准函数(ABS…TAN)、幂 `^`、
  END/STOP、REM、f64 变量与字符串字面量;12 个示例程序(含手册的猜数游戏与
  正态分布图)原生运行验证。MAT 与多语句行在里程碑 3;分时终端语义归"档案控制台"方言
- 备注: 手册含 DTSS 系统命令(BYE/NEW/OLD/SAVE),重构时按"环境方言"与"语言方言"分层。
  第 4 版(1968)已另列: ../1968/
