# C11 目标布局与翻译时间

## packing

`c11.packing` 在预处理流中维护 packing 值和带标签的 push/pop 栈。`#pragma pack`、`_Pragma`、`__pragma` 共用状态，跨 include、块及宏生成的聚合定义保留。

支持 1、2、4、8、16，空参数恢复默认自然布局。push/pop 支持标签及可选新上限；找不到标签时保留原栈，`pop,label,n` 仍应用 n。`show` 保留状态但尚无提示输出。这些属于 [Windows 扩展](https://learn.microsoft.com/en-us/cpp/preprocessor/pack?view=msvc-170)。

上限记录在聚合定义元数据中，后续引用和前向声明不改变已有布局。元数据在最终预处理输出时进入解析 token，不参与字符串化、粘接及 include 文件名。

成员偏移、数组步长、初始化、访问和 ABI 使用同一布局。显式成员对齐在 packing 后保留，聚合显式对齐扩展尾部。位域采用 Microsoft 分配单元策略，参考 [Clang RecordLayoutBuilder](https://github.com/llvm/llvm-project/blob/main/clang/lib/AST/RecordLayoutBuilder.cpp)。

物理 record 使用 `storage.packed_layout` 保存完整字段和显式 padding，指针保留重定位。普通访问使用 alignment=1，[原子访问](c11-atomic-alignment.md) 单独选择对齐或锁路径。联合体中的非整窗口指针由 [静态镜像](c11-static-images.md) 处理。

## 翻译时间

`c11.translation` 从 `source.clock_snapshot()` 生成 `__DATE__` / `__TIME__`。每个 Engine 缓存一次快照，include 和重复展开一致，冻结规则不保存构建时日期。

默认使用本地时间。设置非负十进制 `SOURCE_DATE_EPOCH` 时使用 UTC；空值、非法字符、溢出及不可表示日期报错。日期使用英文月份和空格补齐的日，时间为 `hh:mm:ss`。

## 测试

```powershell
python tests/c11_packing.py
python tests/c11_abi_interop.py
```

独立参考和 Naru 使用相同翻译环境。packed ABI 在两个调用方向及 O0/O2 下检查，未对齐原子的外部协议见 [原子限制](c11-atomics.md)。
