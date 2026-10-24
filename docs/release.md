# 发布预览包

预览包版本为 `0.2.0-preview.1`，编译器项目版本为 `0.2.0`。

## 打包

先按 [构建说明](building.md) 生成 Release 编译器，再执行：

```powershell
python tools/release/prepare.py check --report target/release-preflight.json
python tools/release/prepare.py source --output target/release
.\package.ps1 -VyxSdk $env:VYX_SDK_ROOT -Output target\release\naru-0.2.0-preview.1-windows-x86_64
python tests/distribution.py --package target/release/naru-0.2.0-preview.1-windows-x86_64
```

源码 ZIP 使用固定条目时间和排序路径，清单保存文件 SHA-256、Git 提交及工作区修改状态。二进制包包含编译器、后端、规则、示例、运行库、包管理器和许可证。两种归档均生成 `.sha256` 文件。

源码检查排除网站、SDK、缓存、构建产物和凭据类文件。历史材料只包含条目卡和原创注记，原件及提取副本单独管理。

## 发布检查

- 附上 [实现状态](status.md) 中的已知问题和实际测试结果。
- 保留 MIT、Apache-2.0、NOTICE 和依赖许可证，见 [第三方说明](../THIRD_PARTY.md)。
- 发布 Git 历史前审查其中的史料原件；源码 ZIP 的排除规则不会清理历史提交。

GitHub Actions 的 `Source checks` 在 Linux 和 Windows 检查源码发布工具。原生编译器构建和分发测试需在具备 Vyx SDK 与 Windows 工具链的环境中运行。
