# examples/basic

Dartmouth BASIC(1964)方言的验收程序。方言:`dialects/basic.stx`;说明:`docs/basic.md`;
考据:`historical/basic/1964/`。

## 运行

```powershell
.\target\naru.exe build examples\basic\sum.bas --rules dialects\basic.stx --frontend basic.frontend --unit program --relation emit_program --runtime crt-static --target exe -o target\basic-sum.exe
.\target\basic-sum.exe

# 或整程序项目
.\target\naru.exe build --project examples\basic --target exe -o target\basic-project.exe
```

INPUT 程序从标准输入读取(每变量一行):

```powershell
.\target\basic-guess.exe < input.txt
```

## 程序

| 程序 | 验证 | 输出 |
| --- | --- | --- |
| hello.bas | PRINT 字符串 | HELLO WORLD |
| sum.bas | FOR/NEXT 求和 1..10 | 55 |
| countdown.bas | GOTO + IF-THEN 倒计数 | 5,4,3,2,1,LIFTOFF |
| table.bas | 嵌套 FOR | 3×3 乘积 |
| step.bas | FOR ... STEP 2 | 30 |
| equations.bas | Cramer 法则解二元一次方程组 | 1,2 |
| arrays.bas | DIM + 数组元素 | 55 |
| readdata.bas | DATA/READ | 12 |
| subroutine.bas | GOSUB/RETURN(嵌套) | 42 |
| functions.bas | DEF FN + SQR/INT + 幂 | 49,4,9,32 |
| guess.bas | 手册猜数游戏(INPUT/RND/IF-THEN/GOTO) | 猜中提示 |
| normal.bas | 手册正态分布图(DEF FN/EXP/SQR/STEP .1) | 40 行星号钟形曲线 |

`guess.bas` 的 `RND(0)` 为占位常量(见 docs/basic.md),故 `X` 恒为 51;输入 51 即猜中。
