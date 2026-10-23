# C11 浮点环境

`c11.fenv` 为 Windows x86_64 MSVC/UCRT 选择动态舍入、严格异常和 LLVM `strictfp`。默认 `FENV_ACCESS ON`、`FP_CONTRACT OFF`；开启后者目前仍不生成隐式融合。`CX_LIMITED_RANGE ON` 沿用保守复数算法。静态常量由 APFloat 求值。

## 严格运算

`floating.stx` 通过 `base.emit_binary`、`emit_comparison`、`emit_cast` 的 fallback 接口读取 lowering 策略。整型运算跳过该路径；其他语言可选择自己的策略。复数分量同样使用 constrained 指令，所属函数需设置 `strictfp`。

C 的 `!=` 和真假转换使用 unordered-not-equal，NaN 因而不被视为零。

捆绑 MLIR 将 constrained 浮点操作标为 Pure，单靠异常属性无法阻止通用 DCE/CSE。`ir_effects.ordered` 使用有序区域包围可翻译的无子区域、无跳转操作。后端检查结构和类型，在 LLVM 导出时就地翻译内部操作，不生成运行时辅助调用。

## 原子复合赋值

CAS 路径在地址与 RHS 求值后调用 UCRT `feholdexcept`。失败重试用 `feclearexcept` 清除该次计算的异常，成功后读取异常、用 `fesetenv` 恢复环境，再传播成功计算的异常。RHS 和此前的状态保留。

环境缓冲区在函数入口分配并复用。目标 ABI 使用实际 UCRT `fenv_t` 的 8 字节存储、16 字节对齐及异常位映射。大对象锁路径只计算一次，无需重试。

支持代码调用 UCRT 导出的 hold/clear/test/set 接口。用户调用 `feupdateenv`、`feraiseexcept` 时编译真实 `fenv.h` 的内联实现；`selectany` 对象使用 COMDAT。

## 测试

```powershell
python tests/c11_fenv.py
```

覆盖舍入、未使用结果的异常、环境清除、转换、NaN、原子和复数组合。确定性 CAS 失败、硬件陷阱、并发及 Annex F/G 的逐条审核仍待完成。

浮点模型见 [LLVM constrained intrinsics](https://llvm.org/docs/LangRef.html#constrained-floating-point-intrinsics)。
