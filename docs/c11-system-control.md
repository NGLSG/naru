# C11 类型对齐与非局部跳转

## 记录对齐

`c11.aggregate_alignment` 处理 MSVC `struct __declspec(align(16))` 等声明，在标签身份上附加布局策略。typedef、数组、嵌套成员、位域和函数 ABI 使用相同事实。

对象 `_Alignas` 不改变类型大小；记录类型对齐则通过 `layout.with_alignment` 增加尾部填充，保持数组步长和成员偏移正确。物理表示复用 `c11.members` 和 `storage`。

MSVC 注解接受定义上的 1..8192 二次幂。带注解的前向声明及其他未支持类型属性报告诊断。

## setjmp ABI

系统 `setjmp.h` 将 setjmp 展开为 `_setjmp`，`setjmpex.h` 选择 `_setjmpex`。x64 物理调用另需调用者帧地址。`c11.nonlocal_jumps` 在单参数源声明与物理接口间适配，声明和调用设置 `returns_twice`，longjmp 设置 `noreturn`。

`c11.abi` 的 `prototype_interface` / `call_interface` 描述接口适配，`machine_context.frame_address` 提供 LLVM intrinsic。jmp_buf 和实际跳转实现来自系统库。参考 [Clang MSVCRT setjmp lowering](https://github.com/llvm/llvm-project/blob/main/clang/lib/CodeGen/CGBuiltin.cpp)。

目标词法规则单独定义 `__restrict`、`__cdecl`、`__declspec` 等保留字，其他双下划线名字照常参与声明。

## 测试与限制

```powershell
python tests/c11_system_control.py
```

输入覆盖缓冲区布局、记录 ABI、返回值转换、跨函数和跨单元、多次恢复、单次参数求值及 VLA。异常展开、volatile 局部和恢复点组合仍需完整验证。SEH 属于单独的目标扩展。
