# C11 宽字符与 SDK 接口

当前字符策略使用 UTF-8 源文件和普通执行字符、UTF-16 的 u/L 字面量、UTF-32 的 U 字面量。Windows LLP64 对应 unsigned short 和 unsigned int 码元。

## 名字与字符

`wchar_t` 由系统头声明为 typedef。UCN 与 UTF-8 标识符归一化后使用同一身份，预处理 token 保留原始拼写。数值转义保留目标码元；不同非空字符串前缀的拼接目前拒绝。

普通多字符常量按源字节从左至右装入低 32 位，无法用单个宽码元表示的宽字符常量使用 U+FFFD。UCN 标识符字符串化保留反斜线，选择依据见 [WG14 N1516](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1516.pdf)。

引用 `__func__` 时，`c11.scopes` 在函数最外层块加入 `static const char[]`，复用静态对象和地址规则。

目标定义 `__STDC_UTF_16__` 与 `__STDC_UTF_32__`。wchar_t 使用 UTF-16 码元，因此不定义 `__STDC_ISO_10646__`。基本执行字符值相同，不定义 `__STDC_MB_MIGHT_NEQ_WC__`，参见 [DR 333](https://www.open-std.org/jtc1/sc22/wg14/www/docs/dr_333.htm)。

## SDK intrinsic

UCRT `wchar.h` 的内联代码使用位扫描、128/256 位 SIMD 载体和链接别名。目标策略选择对应的 VC 头，`c11.sdk_intrinsics` 为所需的 4 个位扫描和 10 个整数 SIMD 入口提供检查及 lowering。

位扫描仅在掩码非零时写索引，低 64 位读取保持原读取范围。载体保留头中的成员表示，各实参只 lowering 一次。

共享 `simd_bits` 提供 splat、load、逐 lane 比较、sign mask 和位扫描，`storage.bits` 负责向量与对象布局之间的位重解释。指令选择由 LLVM 目标决定。其他 VC intrinsic 和外部向量 ABI 尚未覆盖。

## 系统库

`wchar.h`、`wctype.h`、`uchar.h` 使用实际 UCRT 声明，mbstate_t、转换、locale、errno、字符串和分类函数链接系统库。

宽 printf/scanf 默认定义 `_CRT_STDIO_ISO_WIDE_SPECIFIERS=1`，链接官方 `iso_stdio_wide_specifiers.lib`。`c11.link_directives` 保存头中的 lib/linker pragma，由共享 `linker` 发射元数据，也支持 `/alternatename` 和 `/include`。

UCRT `fwide` 只返回请求参数，不保存 FILE 流方向，C11 7.21.2 / 7.29.3.5 的语义尚未补齐。后续适配需覆盖首次读写、查询、freopen、关闭重用和跨文件/线程访问。

## 测试

```powershell
python tests/c11_sdk_wide.py
```

输入包括隐式函数名、类型和状态布局、intrinsic、链接 pragma、宽字符串、重启转换、UTF surrogate、ISO 格式、varargs、跨单元及 fwide 反例。
