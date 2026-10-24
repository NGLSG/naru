# 方言库与 JSON 注册表

方言库使用 `Naru.toml` 声明导出、依赖与示例。JSON 注册表保存包名、版本和源码位置；包安装后以本地依赖参与编译。项目可以选用多个方言，规则冲突由编译器报告。

## 入口与自动获取

当前包管理入口是仓库根目录的 `naru.ps1`，实现位于 `tools/pkg/naru.py`。
需要 Python 3.11+，获取 Git 仓库还需要 Git。分发包也包含这一入口。
`naru.exe` 负责原生编译；包获取不执行安装或构建脚本。

```powershell
# 创建一个可运行、可发布的方言库。
.\naru.ps1 pkg init target\my-language --name my-language --module my_language
.\naru.ps1 pkg fetch --project target\my-language
.\naru.ps1 resolve --project target\my-language
.\naru.ps1 build --project target\my-language --locked
& .\target\my-language\target\my-language.exe # 返回 42

# 查询 JSON 注册表；内置表提供当前 SDK 的 naru-stdlib。
.\naru.ps1 pkg search naru

# 给已有项目配置其他注册表（位置可以是本地 JSON 或 HTTPS URL）。
.\naru.ps1 pkg registry community https://example.invalid/naru/index.json --project my-app
.\naru.ps1 pkg search pascal --registry community --project my-app
.\naru.ps1 pkg add 'archive-pascal@^1.0.0' --registry community --name history --project my-app

# 也可以直接指定 Git 仓库，以及 monorepo 内的包目录。
.\naru.ps1 pkg add https://example.invalid/team/archive.git --rev v1.0.0 --subdir languages/pascal --name history --project my-app

# add 不推断语言的前端/后端。可明确追加导出的模块名，也可编辑 language.dialects。
.\naru.ps1 pkg add my-rules --name rules --dialect my_language --project my-app
.\naru.ps1 pkg list --project my-app
.\naru.ps1 pkg update --project my-app
.\naru.ps1 pkg fetch --locked --offline --project my-app
```

示例中的 `example.invalid` 是需要替换的仓库或注册表地址，没有部署公共服务。
相同包名同时出现在多个配置注册表中时，必须通过 `--registry` 指定来源。
直接仓库方式也支持 `ssh://...`、`git@host:team/repo.git` 和
`--git E:\repos\my-library`。包身份读取自仓库的 `Naru.toml`；`--name` 仅是
应用依赖别名，不能重命名方言模块身份。

通过 `naru.ps1 build/resolve/freeze/check/parse/emit` 运行时，会先自动获取和验证
项目的包依赖，再把原始编译选项交给 `naru.exe`。取得包后可直接用
`naru.exe build --project ... --locked`；原生编译器自身不会联网。
冻结构建脚本也可在 `pkg fetch --locked` 后使用现有项目配置。

## 注册表

`registry/index.json` 是内置注册表，`registry/schema.json` 描述格式。
每个稳定版本指向一个 Git 源或本地路径：

```json
{
  "format": 1,
  "packages": {
    "archive-pascal": {
      "description": "Pascal 历史方言与复原规则",
      "homepage": "https://example.invalid/team/archive",
      "versions": {
        "1.0.0": {
          "source": {
            "git": "https://example.invalid/team/archive.git",
            "rev": "v1.0.0",
            "subdir": "languages/pascal"
          }
        }
      }
    }
  }
}
```

注册表版本、包名必须与源清单匹配。建议注册不可变提交；即便表中填写标签或
分支，客户端也会把解析结果锁到完整提交。`subdir` 可省略。
本地表的 `source: {"path": "../dialects"}` 相对于该 JSON 文件，远程表不能
访问客户端的本地路径。远程注册表使用 HTTPS；本机回环 HTTP 用于测试。

支持 `major.minor.patch` 稳定版本、精确版本、`*`、`^` 和 `~`，与编译器现有
版本规则一致。先尝试最高兼容版本，依赖约束冲突时回溯，以寻找全图一致的版本。
一个安装图仍只允许同名包的一份版本；不同名字的包可以共存。
暂不支持 prerelease、比较符范围、平台条件依赖或自动发布服务。

## 来源、安装与编译锁

`Naru.packages.json` 声明可获取的源码来源和版本约束：

```json
{
  "format": 1,
  "registries": {
    "default": "builtin",
    "community": "https://example.invalid/naru/index.json"
  },
  "dependencies": {
    "std": {"package": "naru-stdlib", "version": "^0.2.0", "registry": "default"},
    "history": {"package": "archive-pascal", "version": "^1.0.0", "registry": "community"},
    "custom": {"git": "https://example.invalid/team/custom.git", "rev": "main", "subdir": "rules"}
  }
}
```

包自身也可以提供该文件，因此传递依赖可以继续来自注册表、Git 或本地路径。
子包没有另行声明的注册表会继承使用者的配置。Git 仓库内的相对 path 依赖，
包括 monorepo 中的兄弟包，会转换为同一提交下的包来源。

`Naru.packages.lock` 记录整个获取图的包版本、完整 Git 提交、原始文件 SHA256、
安装文件树 SHA256 与依赖边。`fetch` 和自动构建优先使用已有锁，即使注册表、
HEAD 或标签变化也不升级；只有 `update` 明确重新选择版本和提交。
`--locked` 拒绝缺失或过期的来源锁。离线获取直接验证缓存并恢复安装目录，
不查询远程表、不执行 Git 获取；缺少缓存会报错。

`Naru.toml` 描述编译项目和模块选择。安装器将其依赖物化为
`.naru/packages/<package-name>` 的普通 path 项目：

```toml
[dependencies]
std = { path = ".naru/packages/naru-stdlib", package = "naru-stdlib", version = "0.2.0" }
history = { path = ".naru/packages/archive-pascal", package = "archive-pascal", version = "1.0.0" }

[language]
dialects = ["std/base", "std/ownership", "history/pascal"]
# 按该语言提供的关系设置 frontend、entry、relation、unit 与 MLIR pipeline。
```

同一个包通过多个别名或菱形依赖引用时，只物化一次。首次接入包管理时，已有
path 依赖也会登记其原始来源并生成快照，避免它与远程包依赖出现两份相同包身份。
修改这些本地来源后，执行 `pkg update` 才会采用新内容；普通 `fetch` 保持锁中的
快照。应用自身的规则和用户源码仍在原位置编辑。

编译器原有的 `Naru.lock` 则记录清单和实际参与链接的规则指纹。两个锁各管一层：
先 `pkg fetch` 锁定来源图，再 `naru resolve` 更新编译输入锁，然后
`naru build --locked`。更新来源图后，应重新 `resolve` 再做锁定构建。
提交两个 JSON 来源文件、`Naru.toml` 和 `Naru.lock`；不要提交 `.naru`。

## 模板与安装验证

`templates/dialect` 包含导出清单、规则、依赖来源、示例、README 和忽略规则。
默认模板通过组合 `base` 添加 `answer` 表达式，并实际编译为返回 42 的程序。
新语言可替换语法、前端、语义关系和 MLIR 管线，不要求它采用模板中的 base 语法。

包缓存按原始内容树的 SHA256 存储；`NARU_PACKAGE_CACHE` 或 `--cache` 可以选择
共享缓存。已安装文件和缓存内容在使用前验证；修改托管副本会报错，避免覆盖编辑。
包获取不执行库内的 hooks/install/build 脚本，符号链接、路径逃逸、重复或大小写
冲突的包路径，以及错误导出身份会拒绝。每包限制 20,000 文件和 256 MiB；图最多
256 包、64 层，版本回溯最多 2048 次。大文件散列使用流式读取。

安装在独立目录内准备，替换目录和来源文件时保留回滚副本；进程内出现读取、
验证或写入错误会恢复已有安装。断电/进程被强杀的跨文件事务恢复尚未实现。
同一项目使用排他 guard；异常中止留下的 guard 需要确认 PID 后清理。
包管理入口拒绝输出或报告覆盖来源 JSON、来源锁、托管包与缓存；元数据文件的
硬链接别名也受保护。SDK 移动后，本地注册表可恢复完全相同的锁定内容，散列
不匹配时不会采用新的内容。

```powershell
python tests/packages.py
```

验收包含真实 Git 仓库、标签/提交、子目录、JSON 注册表、约束回溯、菱形依赖、
离线恢复、篡改检测、失败回滚，以及模板实际编译和运行。传输层测试使用隔离
本地仓库和回环 HTTP，不依赖外部托管服务。
