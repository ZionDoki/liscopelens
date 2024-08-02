# compliance_license_compatibility


1. [compliance\_license\_compatibility](#compliance_license_compatibility)
   1. [介绍](#介绍)
      1. [目录结构](#目录结构)
   2. [安装教程](#安装教程)
   3. [使用说明](#使用说明)
      1. [基于sbom文件分析兼容性](#基于sbom文件分析兼容性)
         1. [参数列表](#参数列表)
      2. [分析代码仓库的兼容性(请确保存在gn工具或者gn解析文件)](#分析代码仓库的兼容性请确保存在gn工具或者gn解析文件)
         1. [参数列表](#参数列表-1)
   4. [已知问题](#已知问题)
   5. [参与贡献](#参与贡献)


## 介绍

开源许可证兼容性分析工具，基于结构化的许可证信息和具体场景的依赖行为与构建设置，对目标中引入的开源许可证进行兼容性分析。

尽管我们会尽力确保该工具的准确性和可靠性，但**本项目的检查结果不构成任何法律建议**。使用者应自行审查和判断，以确定所采取的行动是否符合法律法规以及相关许可证的规定。

**注意：本项目当前仍处于早期版本，相关结果的准确性未进行验证，且迭代过程中各模块接口将会发生较大变化。**

### 目录结构
```
|-compliance_license_compatibility
|  |─doc #设计文档
|  |─poetry.lock #依赖管理文件
|  |─pyproject.toml #依赖管理文件
|  |─lict
|       ├─config
|       │  ├─default.toml #许可证传播规则配置文件
|       ├─parser #根据传入参数解析sbom文件或者gn文件
|       │  ├─base.py #定义抽象基类，构建解析器框架
|       │  ├─compatible.py #实现用于检查许可证兼容性的逻辑
|       │  ├─echo.py #用于输出兼容性检查结果
|       │  ├─exception.py #异常处理
|       │  ├─scancode.py #解析scancode输出的json文件
|       │  ├─c_parser 
|       │    ├─entry.py #C/C++代码仓库许可证检测程序的入口文件，该文件依次调用所需解析器执行检测
|       │    ├─build_gn_parser.py #gn文件解析器
|       │    ├─include_parser.py #构建代码之间的依赖关系
|       │  ├─sbom_parser #解析sbom文件检测许可证兼容性
|       │    ├─entry.py #sbom文件解析入口文件
|       │    ├─sbom_parser.py #sbom文件解析器
|       ├─resources
|       │  ├─exceptions
|       │  ├─licenses #定义不同许可证条款的规则与约束
|       │  ├─schemas.toml #定义不同动作（actions）的规则和约束
|       ├─utils
|       │  ├─graph.py #图数据结构，存储依赖关系
|       │  ├─scaffold.py  #存放工具函数
|       │  ├─structure.py #许可证合规分析工具核心功能，包括定义许可证属性、解析许可证表达式、以及数据加载
|       ├─app.py #入口文件
|       ├─constants.py #常量定义文件
|       ├─infer.py #使用结构化信息来推断不同许可证之间的兼容性，并生成知识图谱以供进一步使用
|       ├─checker.py 
|  |─examples
|  |─tests
```

## 安装教程

0. 确保已经安装 `python 3.11^`
1. clone 仓库
2. 进入仓库根目录 `pip install .`

## 使用说明

确保工具安装后，终端输入指令 `lict --help`

```shell
usage: lict [-h] [-c CONFIG] {sbom,cpp} ...

部件兼容性分析工具

positional arguments:
  {sbom,cpp}
    sbom                Software Bill of Materials (SBOM) parser, this parser only support for OH sbom format.
    cpp                 This parser is used to parse the C/C++ repository and provide an include dependency graph
                        for subsequent operations

options:
  -h, --help            show this help message and exit
  -c CONFIG, --config CONFIG
                        配置文件路径
```

### 审查结果

```shell
lict query /path/to/output_dir
```

[query演示](assets/example.gif)

### 基于sbom文件分析兼容性

目前仅支持OH SBOM文件，文件应符合如下格式

```json
{
    "spdxId": "0eedfd2b-5a20-4cad-adf8-371197d0cd27",
    "spdxVersion": "SPDX-2.2",
    "creationInfo": {
        "created": "2023-12-05 09:59:05",
        "creators": [
            "Organization: OpenHarmony"
        ]
    },
    "packages": [
        {
            "spdxId": "A",
            "name": "A",
            "downloadLocation": "https://gitee.com/openhamony/dcts/tree/master",
            "versionInfo": "3.1",
            "supplier": "Organization: OpenHarmony",
            "externalRefs": [
                {
                    "referenceCategory": "PACKAGE_MANAGER",
                    "referenceType": "purl",
                    "referenceLocator": "pkg:gitee/openharmony/xts_dcts@master?revision\u003d24a3c135de1830bde84a98c1990843ee3b32feaa"
                }
            ],
            "licenses": [
                {
                    "spdxId": "MIT"
                }
            ]
        },
        {
            "spdxId": "B",
            "name": "B",
            "downloadLocation": "https://gitee.com/openhamony/dcts/tree/master",
            "versionInfo": "3.1",
            "supplier": "Organization: OpenHarmony",
            "externalRefs": [
                {
                    "referenceCategory": "PACKAGE_MANAGER",
                    "referenceType": "purl",
                    "referenceLocator": "pkg:gitee/openharmony/xts_dcts@master?revision\u003d24a3c135de1830bde84a98c1990843ee3b32feaa"
                }
            ],
            "licenses": [
                {
                    "spdxId": "Apache-2.0"
                }
            ]
        }
    ],
    "relationships": [
        {
            "spdxElementId": "A",
            "relationshipType": "DEPENDS_ON",
            "relatedSpdxElement": "B"
        }
    ]
}

```

查看帮助 `lict sbom -h`

```shell
usage: lict sbom [-h]  [--sbom_file SBOM_FILE]

options:
  -h, --help            show this help message and exit
  --sbom_file SBOM_FILE  sbom_file_path
```

运行shell命令进行兼容性检查

```shell
lict sbom --sbom_file SBOMPATH
```

#### 参数列表

| 参数        | 类型 | 说明         | 是否必须 |
| ----------- | ---- | ------------ | -------- |
| --c         | str  | 配置文件路径 | 否       |
| sbom        | bool | 指明使用sbom | 是       |
| --sbom_file | str  | sbom文件路径 | 是       |


### 分析代码仓库的兼容性(请确保存在gn工具或者gn解析文件)
查看帮助 `lict cpp -h`
```shell
usage: lict cpp [-h] (--gn_tool GN_TOOL | --gn_file GN_FILE)
                (--scancode-file SCANCODE_FILE | --scancode-dir SCANCODE_DIR) [--rm-ref-lang] [--save-kg]
                [--ignore-unk] [--out-gml OUT_GML] [--echo] [--out-echo OUT_ECHO]

options:
  -h, --help            show this help message and exit
  --gn_tool GN_TOOL     the path of the gn tool in executable form
  --gn_file GN_FILE     the path of the gn deps graph output file
  --scancode-file SCANCODE_FILE
                        The path of the scancode output in json format file
  --scancode-dir SCANCODE_DIR
                        The path of the directory that contain json files
  --rm-ref-lang         Automatically remove scancode ref prefix and language suffix from spdx ids
  --save-kg             Save new knowledge graph after infer parse
  --ignore-unk          Ignore unknown licenses
  --out-gml OUT_GML     The output path of the graph
  --echo                Echo the final result of compatibility checking
  --out-echo OUT_ECHO   The output path of the echo result
```
运行shell命令进行兼容性检查，示例如下
```shell
lict cpp --gn_tool GN_TOOL --scancode-file SCANCODE_FILE --echo 
```

#### 参数列表

| 参数            | 类型 | 说明                                 | 是否必须 |
| --------------- | ---- | ------------------------------------ | -------- |
| cpp             | bool | 指明检测C/C++代码仓库                | 是       |
| --gn_tool       | str  | GN 工具的可执行文件路径              | 是       |
| --gn_file       | str  | GN 依赖图输出文件路径                | 是       |
| --scancode-file | str  | Scancode 输出的 JSON 格式文件路径    | 是       |
| --scancode-dir  | str  | 包含 JSON 文件的目录路径             | 是       |
| --rm-ref-lang   | bool | 自动移除 Scancode 引用前缀和语言后缀 | 否       |
| --save-kg       | bool | 在解析后保存新的知识图谱             | 否       |
| --ignore-unk    | bool | 忽略未知的许可证                     | 否       |
| --out-gml       | str  | 图谱的输出路径                       | 否       |
| --echo          | bool | 回显兼容性检查的最终结果             | 否       |
| --out-echo      | str  | 回显结果的输出路径                   | 否       |

gn依赖图格式如下
```json
{
  "build_settings": {
    "build_dir": "//out/hispark_taurus/ipcamera_hispark_taurus/",
    "default_toolchain": "//build/lite/toolchain:linux_x86_64_ohos_clang",
    "gen_input_files": [
      "//.gn",
      "//vendor/hisilicon/hispark_taurus/hdf_config/BUILD.gn",
      "//vendor/hisilicon/hispark_taurus/hdf_config/hdf_test/BUILD.gn"
    ],
    "root_path": "/home/dragon/oh"
  },
  "targets": {
    "//applications/sample/camera/cameraApp:cameraApp_hap": {
      "all_dependent_configs": [
        "//third_party/musl/scripts/build_lite:sysroot_flags"
      ],
      "deps": [
        "//applications/sample/camera/cameraApp:cameraApp",
        "//developtools/packing_tool:packing_tool",
        "//third_party/musl:sysroot_lite"
      ],
      "metadata": {
      },
      "outputs": [
        "//out/hispark_taurus/ipcamera_hispark_taurus/obj/applications/sample/camera/cameraApp/cameraApp_hap_build_log.txt"
      ],
      "public": "*",
      "script": "//build/lite/hap_pack.py",
      "testonly": false,
      "toolchain": "//build/lite/toolchain:linux_x86_64_ohos_clang",
      "type": "action",
      "visibility": [
        "*"
      ]
    },
    "//foundation/arkui/ace_engine_lite/frameworks/src/core/stylemgr/test/unittest:stylemgr_unittest": {
         "all_dependent_configs": [ "//third_party/musl/scripts/build_lite:sysroot_flags" ],
         "deps": [ "//foundation/arkui/ace_engine_lite/frameworks/src/core/stylemgr/test/unittest:js_frameworks_test_condition_arbitrator", "//foundation/arkui/ace_engine_lite/frameworks/src/core/stylemgr/test/unittest:js_frameworks_test_link_queue", "//foundation/arkui/ace_engine_lite/frameworks/src/core/stylemgr/test/unittest:js_frameworks_test_link_stack", "//foundation/arkui/ace_engine_lite/frameworks/src/core/stylemgr/test/unittest:js_frameworks_test_stylemgr", "//foundation/arkui/ace_engine_lite/frameworks/src/core/stylemgr/test/unittest:js_frameworks_test_stylemgr_media_query" ],
         "metadata": {

         },
         "public": "*",
         "testonly": false,
         "toolchain": "//build/lite/toolchain:linux_x86_64_ohos_clang",
         "type": "group",
         "visibility": [ "*" ]
      }
  }
}

```

## 已知问题

1. `poetry install | add` 无响应或者报错提示包括 `Failed to unlock the collection`.


```shell
export PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring
```

## 参与贡献

参见[设计文档](doc/设计文档.md#开发手册)

