# C11 预处理与 pragma

预处理规则位于 `c11.pp`、`c11.pp_macros` 和 `c11.pragmas`。

## 展开状态

`c11.pp.expand_result` 返回 token 及最终状态。普通源码在指令边界和文件结束时刷新；include、line 和条件表达式保存展开后的状态，使 pragma once 和链接事实跨扫描保留。

展开使用持久 cursor 工作栈和反向输出块。替换只压入新 token 块，结束时一次展平，避免复制剩余源码。

## 参数与重扫描

参数 token 保留抑制集合和关闭括号事实。参数按需预展开，每次宏调用缓存一次；仅用于字符串化、粘接或未使用的参数不预展开。

`#` 使用原始参数，`##` 保留 placemarker 及替换表来源。宏展开产生的同名 `##` 不作为粘接操作符，参见 [WG14 DR 017 问题 22](https://www.open-std.org/jtc1/sc22/wg14/www/docs/dr_017.html)。

重扫描保留空白边界和源位置。非法 `#`、首尾 `##` 及非 variadic 宏中的 `__VA_ARGS__` 在定义时诊断。

## pragma 与行号

`_Pragma` 接受普通或 L 前缀字符串，只解码转义引号和反斜线，然后从翻译阶段 3 扫描。目标扩展 `__pragma` 接受 token 参数，可展开宏。两者与 `#pragma` 共享处理规则，包括浮点策略、once、链接元数据及 [packing](c11-packing.md)。未知 pragma 忽略，已识别但格式错误的 pragma 报错。

`defined`、ifdef/ifndef、undef 要求标识符。`#line` 使用十进制数字，前导零不表示八进制；拒绝后缀、十六进制、零和越界值，文件名须为普通字符串。

`__DATE__` / `__TIME__` 的快照及 `SOURCE_DATE_EPOCH` 见 [翻译时间](c11-packing.md)。

## 测试与限制

```powershell
python tests/c11_preprocessor.py
```

覆盖 pragma、include 状态、未求值参数、递归抑制、缓存、placemarker、生成的 `##`、空白、variadic、定义点诊断和 line 映射。物理源位置、最低翻译限额及 6.10 的逐段审核仍待完成。
