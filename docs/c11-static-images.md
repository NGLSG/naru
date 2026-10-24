# C11 静态对象镜像

联合体运行时通常使用整数窗口表示，但符号指针需要完整重定位。packed 记录中的指针若从第 1 字节开始，会跨越两个 8 字节窗口，无法拆为整数片段后直接发射 COFF 重定位。

`c11.static_image` 从已检查的初始化树规划物理全局存储。每个联合体保留最终生效成员，数组元素可选择不同成员；记录、数组步长、位域和尾部 padding 使用目标布局。源类型、ABI、符号名、链接、TLS、对齐和总大小保持一致。

普通 C 访问按源布局偏移使用 opaque pointer。镜像在语义检查后建立，依赖 [MLIR 全局初始化区](https://mlir.llvm.org/docs/Dialects/LLVM/#llvmmlirglobal-llvmglobalop) 和 [LLVM opaque pointer](https://llvm.org/docs/OpaquePointers.html)。被覆盖的初始化输入仍需通过静态常量约束。

## 规划与发射

整对象初值和子对象覆盖组合成最终计划。切换联合体成员时清除旧成员计划，同一成员的局部覆盖保留其余字段。位域在完整整数单元中累积掩码，普通指针单独保存，padding 从零开始。

`storage` 提供以下接口：

- `Image(shape, producer)`：保存布局及延迟构造器。
- `image_zero`、`image_project`、`image_record`：组合、投影和补零。
- `image_lower`：在全局初始化区执行发射。
- `storage.image_value(payload, environment)`：语言库提供的叶值发射关系。

producer 只构造常量。子窗口按位偏移索引，嵌套投影合并偏移，避免每个位域重复发射父对象。

显式对象对齐独立于类型自然对齐。TLS 声明和定义统一使用 `tls_mode = 1`（GeneralDynamic）。

## 测试与限制

```powershell
python tests/c11_static_images.py
python tests/c11_abi_interop.py
```

待检查重点包括完整静态初始化约束、LLVM/COFF 重定位、跨单元对象布局和 TLS 线程隔离。
