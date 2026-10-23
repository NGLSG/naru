# C11 复数

`c11.complex` 将 `_Complex` 接入声明说明符、类型转换、表达式、存储和常量求值。支持 float、double 及目标 long double；Windows 配置中 long double 使用 binary64。

## 运算与表示

值按两个相邻实分量存储，临时加减、负号和比较使用 MLIR Complex 操作。进程内后端注册 Complex 到 LLVM 的转换接口。

实数与复数混合乘除保留操作数的原始域，避免凭空引入零虚部与无穷实部相乘。表达式只 lowering 一次，后续分量操作复用 SSA 值。实数负号使用 `arith.negf` 保留负零。

通用库 `complex_numbers` 按浮点格式实现算法：乘法处理无穷及中间溢出导致的双 NaN，有限除法分别缩放分子和分母，纯实或纯虚除数直接逐分量相除。静态乘除使用 APFloat binary128 中间值，再转换为声明的 binary32/binary64。

有序比较、整数运算符、指针转换及自增不接受复数。默认实参提升保留 float complex 类型。

## UCRT 接口

`c11.complex_crt` 检查 UCRT 三个保留记录的 `_Val[2]` 布局，将其声明和原生复数类型衔接。用户结构体仍保留名义类型。

66 个 ISO 复数函数使用声明适配，缺少的构造宏在包含实际头后补充。库函数继续链接系统数学库，详见 [库接口契约](c11-library-contract.md)。

## 测试与限制

```powershell
python tests/c11_complex.py
```

输入覆盖转换、单次求值、大小数除法、静态常量、对象表示、直接/间接和跨单元调用、原子组合及真实 UCRT 调用。

仍需验证极端分量比例、IEEE 异常、符号零、动态舍入、`FENV_ACCESS`、全部库接口及独立编译器 ABI。完整 Annex G 审核尚未完成，能力宏保持保守配置。
