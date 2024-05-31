# compliance_license_compatibility

#### 介绍

开源许可证兼容性分析工具，基于结构化的许可证信息和具体场景的依赖行为与构建设置，对目标中引入的开源许可证进行兼容性分析。

尽管我们会尽力确保该工具的准确性和可靠性，但**本项目的检查结果不构成任何法律建议**。使用者应自行审查和判断，以确定所采取的行动是否符合法律法规以及相关许可证的规定。

**注意：本项目当前仍处于早期版本，相关结果的准确性未进行验证，且迭代过程中各模块接口将会发生较大变化。**

#### 软件架构

*待补充*

#### 安装教程

0. 确保已经安装 `python 3.11^`
1. clone 仓库
2. 进入仓库根目录 `pip install .`

#### 使用说明

确保工具安装后，终端输入指令 `lict --help`

```shell
usage: lict [-h] (--sbom SBOM | --sbom_file SBOM_FILE) [--output OUTPUT] [--log-level LOG_LEVEL] [--beauty] [--reinfer]

部件兼容性分析工具

options:
  -h, --help            show this help message and exit
  --sbom SBOM           部件sbom参数JSON字符串
  --sbom_file SBOM_FILE
                        部件sbom参数JSON文件清单路径
  --output OUTPUT       输出文件路径
  --log-level LOG_LEVEL
                        日志级别
  --beauty              美化输出
  --reinfer             强制更新知识库
```

#### 已知问题

1. `poetry install` 无响应或者报错提示包括 `Failed to unlock the collection`.

```shell
export PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring
```

#### 参与贡献

参见[设计文档](doc/设计文档.md#开发手册)

