# C11 全量支持计划

目标平台为 Windows x86_64 LLP64，范围包括 C11 语言、VLA、原子、复数、线程及系统标准库接口。基准为 [WG14 N1570](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf)，适用的缺陷报告单独记录。

机器可读计划位于 `tests/c11/support-plan.json`，分发包副本为 `docs/c11-support-plan.json`，共 30 个工作项，计划仍在进行。实现模块见 [C11 方言](c11.md)，最近测试结果见 [实现状态](status.md)。

## 工作范围

| 范围 | 内容 | 完成条件 |
| --- | --- | --- |
| 声明与作用域 | 说明符、声明点、标签、枚举、链接、旧式函数与无原型调用 | 必需诊断、复合类型和跨单元链接通过审核 |
| 表达式与 ABI | 转换、值类别、inline、_Noreturn、聚合调用 | 副作用和独立编译器双向 ABI 测试通过 |
| 初始化与存储期 | 花括号省略、指定链、覆盖、地址常量与字面量 | 初始化约束、对象身份和生命周期正确 |
| VLA 与布局 | 变长类型、跳转、位域、对齐和 packing | 动态 sizeof、存储清理、布局及访问约束通过 |
| 翻译过程 | 预处理、源位置、字符集、UCN/UTF 和翻译限额 | 阶段顺序、宏重扫描、位置和最低限额符合要求 |
| 并发与数值 | 原子、TLS、线程、复数和浮点环境 | 内存序、系统接口、数值边界和能力宏一致 |
| 库与集成 | 标准头、库函数、真实项目、规则组合和动态/AOT | 同一源码快照通过全部验收，条款审核完成 |

每个工作项记录条款、实现文件、剩余问题和验收报告。用例通过后仍需检查对应条款的约束、必需诊断及实现定义选择。

## 尚待完成

- 大型初始化和真实系统头的编译内存控制。
- 全部标准库接口、目标 ABI、原子跨编译器协议与 DLL 边界测试。
- UCRT `fwide` 的流方向语义适配。
- 浮点原子 CAS 的确定性失败注入、陷阱及极端复数输入。
- 翻译限额、物理源位置和缺陷报告的逐段审核。
- 最终规则组的动态与冻结编译器一致性验收。

各专项的具体约束见 [原子](c11-atomics.md)、[ABI](c11-abi.md)、[宽字符](c11-sdk-wide.md)、[浮点环境](c11-fenv.md) 和 [预处理](c11-preprocessor.md)。

## 总验收

动态模式：

```powershell
python tests/c11_full_support.py --jobs 4
```

动态与冻结模式：

```powershell
python tests/c11_full_support.py --compiler target/naru.exe `
  --frozen-compiler target/specialized-c11/target/naru.exe --jobs 4
```

工程入口：

```powershell
.\test.ps1 -C11Full -Jobs 4
```

队列包含正例、必需诊断、未完成特性探测、系统头及固定真实项目。报告默认写入 `target/c11-full-support.json`。任一套件失败、工作项未关闭或冻结清单过期时，总验收返回非零。

动态报告可复用，要求输入、调用参数、报告和日志哈希一致：

```powershell
python tests/c11_full_support.py --jobs 4 --report target/c11-full-support-dynamic.json
python tests/c11_full_support.py --frozen-compiler target/specialized-c11/target/naru.exe `
  --reuse-dynamic-report target/c11-full-support-dynamic.json --jobs 4
```

## GCC 构建

GCC 源码构建作为独立工程测试，需固定源码、依赖、配置和构建阶段。历史 C bootstrap 与现代 GCC 的 C++、GNU 扩展和构建工具要求分别处理。C11 验收完成后再接入对应构建目标。
