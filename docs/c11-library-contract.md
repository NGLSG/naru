# C11 系统头与库接口

当前配置为 Windows x86_64 MSVC/UCRT。头文件由目标策略选择，库函数链接系统运行库。

## 头文件来源

`headers.header_exclusions` 按头文件名排除提供目录，保留其余搜索顺序。include、include_next、__has_include 和 __has_include_next 使用同一视图，项目包装头仍可优先处理。

`c11.system_headers` 的选择为：

- `tgmath.h` 使用 UCRT 的 `_Generic` 实现；LLVM 资源头的复数接口与 UCRT 记录载体 ABI 不匹配。
- `stdatomic.h` 使用 LLVM 资源头，并排除 VC 目录作为其后续提供方；VC 头使用另一套编译器接口，且缺少 `ATOMIC_VAR_INIT`。

frontend option `target_header_policy=raw` 可查看原始搜索链。安装的头文件保持原样。

## 复数

`c11.complex_crt` 检查三个 UCRT 保留载体的 `_Val[2]` 布局，将 66 个 ISO 函数的声明映射为原生复数类型。声明点发布后，重声明、函数指针和调用共用同一类型。

包含 `complex.h` 后补充其缺少的 `complex`、`CMPLX`、`CMPLXF`、`CMPLXL` 宏，保留负零和单次求值；`I` / `_Complex_I` 沿用原定义。`_Generic` 识别已检查的目标载体，用户结构体仍按名义类型匹配。

UCRT `__cpow*` 辅助函数保留原函数体，目标头的 inline 包装用 COMDAT 发射。用户 ISO inline 由 `c11.functions` 处理。

## 原子可取地址函数

资源头声明两个 fence、两个 flag test/set 和两个 flag clear 普通函数。`c11.atomic_api` 复用原子规则生成定义，通过 linkonce COMDAT 合并跨翻译单元函数地址。已有用户定义时不重复生成。

flag 布局检查单个 `_Atomic _Bool` 字段、大小和对齐，指针限定符保留到成员访问。不完整类型指针声明无须提前完成布局，错误的保留函数签名报告诊断。

## 测试

```powershell
python tests/c11_library_contract.py
python tests/c11_abi_interop.py
```

用例覆盖原子函数的括号调用、取消宏、函数指针、内存序、volatile、跨文件身份，以及复数函数类型、构造宏和 tgmath 选择。

Clang 对照通过 VFS 选择实际 UCRT `tgmath.h`。需要目标载体适配或原子支持 TU 时，报告单列参考源码及哈希；Naru 编译输入保持原样。最终 ABI 由独立对象套件检查。
