# compliance_license_compatibility


- [compliance\_license\_compatibility](#compliance_license_compatibility)
  - [介绍](#介绍)
  - [快速开始](#快速开始)
  - [安装教程](#安装教程)
  - [使用说明](#使用说明)
    - [分析代码仓库的兼容性(请确保存在gn工具或者gn解析文件)](#分析代码仓库的兼容性请确保存在gn工具或者gn解析文件)
      - [参数列表](#参数列表)
      - [gn依赖图格式](#gn依赖图格式)
  - [已知问题](#已知问题)
  - [审查结果](#审查结果)
  - [参与贡献](#参与贡献)



## 介绍

开源许可证兼容性分析工具，基于结构化的许可证信息和具体场景的依赖行为与构建设置，对目标中引入的开源许可证进行兼容性分析。

尽管我们会尽力确保该工具的准确性和可靠性，但**本项目的检查结果不构成任何法律建议**。使用者应自行审查和判断，以确定所采取的行动是否符合法律法规以及相关许可证的规定。

**注意：本项目当前仍处于早期版本，相关结果的准确性未进行验证，且迭代过程中各模块接口将会发生较大变化。**

## 快速开始

当前版本仅支持面向 OpenHarmony 的兼容性检测，欢迎使用面向 OpenHarmony 全量源码仓的一键检测脚本 [LictOneClick](https://gitee.com/zionmoe/lict-one-click)。

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

### 分析代码仓库的兼容性(请确保存在gn工具或者gn解析文件)

1. 获取 OpenHarmoy 源码
2. 安装 OpenHarmony 编译构建工具执行 
    `./build.sh --product-name {设备形态} --gn-flags="--ide=json" --gn-flags="--json-file-name=out.json"`
3. 确保在源码根目录下具有`OpenHarmony/out/{设备形态}/out.json` 存在
4. 使用 Scancode 扫描 OpenHarmony 许可证
5. 执行 lict 进行兼容性扫描
    ```shell
    lict cpp --gn_file OpenHarmony/out/{设备形态}/out.json --scancode-file path/to/scancode-res.json --output ./output
    ```
1. 查看 `output/results.json` 或则借助[审查工具](#审查结果)

其他参数可以，查看帮助 `lict cpp -h`，解释如下：
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

#### gn依赖图格式

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

## 审查结果

执行完成后审查冲突结果（请确保传入输出位置参数 `lict <command> ... --output path/to/output_dir`）

```shell
lict query /path/to/output_dir
```

![query演示](assets/example.gif)

## 参与贡献

参见[设计文档](doc/设计文档.md#开发手册)
