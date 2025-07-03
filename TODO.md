# Hvigor 项目依赖构件图解析指导文档

## 项目背景

我正在实现一个许可证兼容性分析项目，需要解析基于 hvigor 构建的项目，为了准确的识别许可证，我首先需要解析待检测的目标仓库 A，获得 A 的依赖构件图。

依赖构建图是一个有向图，图中的节点表示一个逻辑上的"构件"，而边则表示构件之间的打包/链接/调用等依赖关系。

对于 Hvigor 项目来说，其开发语言是类似 typescript 的 ArkTS，由于 Typescript 的特殊性，我们可以将整个项目看作几个大的模块，每个模块可以看作一个构件。

**[CRITICAL]** 比较重要的是有些模块是 Native 模块，但由于 ArkTS 类似于 JNI 和 NAPI 所以链接关系应该都属于动态链接。在构建图上要识别 Native 构建并标记为动态链接。

## 基础背景知识

### 1. 工程结构定义

hvigor将工程解析为一个树形结构，项目为树的根节点，项目中的每个模块为树的叶子节点，树最多为两层，模块中不能包含其他模块。一般如下，其中 entry 为入口，这意味着依赖构件图的深度应该不超过 3 层：project(entry) -> module -> files.

```
ProjectA
├── Module1
│   ├── file1.ts
│   └── file2.ts
├── Module2
│   ├── cpp
│   │   ├── file1.cpp
│   │   └── file2.cpp
└── entry
```

### 2. 依赖构件图的主要依据

oh-package.json5 文件（每个模块以及 Project 根目录均有，类似于 package.json 存在 dependencies 以及 devDependencies 字段）。

**[CRITICAL]** 从 hvigor 的哲学上看，模块内部没有复杂的依赖关系，所有的依赖关系都应该在模块与模块之间明确列出。**这是感知依赖构件图的关键。**

### 3. Native 感知

如何识别一个模块涉及了 Native 依赖，主要需要通过项目文件有没有包含 C/C++ 以及 build-profile.json5，结合 oh-package.json5 中的 dependencies 或者 devDependencies 字段来判断。此时，依赖的产物 .so 可以看作是一种文件。

```json
{
  "buildOptionSet": [
    {
      "name": "release",
      "arkOptions": {
        "obfuscation": {
          "ruleOptions": {
            "enable": true,
            "files": ["./obfuscation-rules.txt"]
          }
        }
      },
      "externalNativeOptions": {
        "path": "./src/main/cpp/CMakeLists.txt",
        "arguments": ["-DCMAKE_BUILD_TYPE=Debug"],
        "cppFlags": "-g",
        "abiFilters": ["arm64-v8a"]
      },
      "nativeLib": {
        "debugSymbol": {
          "strip": true,
          "exclude": []
        },
        "filter": {
          "excludes": ["**/3.so", "**/x86_64/*.so"],
          "pickFirsts": [],
          "pickLasts": [],
          "enableOverride": true,
          "select": [
            {
              "package": "@ohos/curl",
              "version": "1.3.5",
              "include": ["libcurl.so"],
              "exclude": ["libc++_shared.so"]
            }
          ]
        },
        "headerPath": "./src/main/cpp/include",
        "librariesInfo": [
          {
            "name": "libentry.so",
            "linkLibraries": ["curl::curl"]
          }
        ]
      }
    }
  ]
}
```

你可以注意到，`build-profile.json5` 中的 select 和 filter 字段可以帮助我们识别 Native 模块。

## 完整的配置文件解析策略

### 1. oh-package.json5 (依赖声明文件)
**位置**: 项目根目录和各模块目录

**作用**: 声明模块的依赖关系，是构建依赖图的核心数据源

**关键字段**:
- `dependencies`: 运行时依赖
- `devDependencies`: 开发时依赖
- `name`: 模块名称
- `version`: 模块版本
- `license`: 许可证信息

**解析策略**: 
- `file:` 协议表示本地模块依赖，需要建立模块间的直接依赖关系
- `@ohos/` 前缀表示官方组件依赖
- `.so` 文件依赖表示 Native 库依赖，需要标记为动态链接
- 其他包名表示第三方依赖

### 2. build-profile.json5 (构建配置文件)
**位置**: 项目根目录和各模块目录

**作用**: 定义构建选项和 Native 模块配置

**关键字段**:
- `modules`: 项目模块列表（仅根目录）
- `buildOption.externalNativeOptions`: Native 构建配置
- `buildOptionSet[].nativeLib`: Native 库配置
- `apiType`: 模块 API 类型

**解析策略**: 
- 根目录的 modules 字段确定项目结构
- externalNativeOptions 的存在表明这是一个 Native 模块
- nativeLib 配置提供 Native 依赖的详细信息

### 3. module.json5 (模块配置文件)
**位置**: `{模块目录}/src/main/module.json5`

**作用**: 定义模块的基本信息、能力声明和权限需求

**关键字段**:
- `module.name`: 模块名称，用于构件图中的节点标识
- `module.type`: 模块类型（entry/library），影响依赖关系的方向性
- `requestPermissions`: 权限依赖，可能影响运行时依赖关系
- `abilities`: 能力声明，用于识别模块间的服务调用关系

**解析策略**: 通过 module.json5 可以确定模块在整个应用中的角色，entry 类型的模块通常是依赖图的起始节点。

### 4. app.json5 (应用配置文件)
**位置**: `AppScope/app.json5`

**作用**: 定义应用级别的全局配置

**关键字段**:
- `app.bundleName`: 应用包名，作为依赖图根节点的标识
- `app.versionCode/versionName`: 版本信息，用于依赖版本管理

**解析策略**: 作为依赖构件图的根节点信息来源，确定整个项目的顶层标识。

### 5. hvigorfile.ts (构建脚本配置)
**位置**: 项目根目录和各模块目录

**作用**: 定义构建时的插件依赖和自定义任务

**关键字段**:
- `system`: 内置构建插件（appTasks/hapTasks）
- `plugins`: 自定义插件列表，可能引入额外的构建时依赖

**解析策略**: 识别构建时依赖，这些依赖虽然不直接影响运行时，但对于完整的依赖分析很重要。

### 6. CMakeLists.txt (Native 构建配置)
**位置**: `{Native模块目录}/src/main/cpp/CMakeLists.txt`

**作用**: 定义 Native 模块的编译和链接配置

**关键字段**:
- `target_link_libraries`: 链接库声明
- `add_library`: 库目标定义
- `target_include_directories`: 头文件路径

**解析策略**: 解析 target_link_libraries 指令，提取 Native 依赖关系，区分静态库（.a）和动态库（.so）。

## Native 模块识别的完整策略

### 识别条件（多重验证）

1. **build-profile.json5 检查**:
   - 存在 `buildOption.externalNativeOptions` 字段
   - 存在 `buildOptionSet[].nativeLib` 配置

2. **目录结构检查**:
   - 存在 `src/main/cpp/` 目录
   - 存在 CMakeLists.txt 文件

3. **依赖声明检查**:
   - oh-package.json5 中声明了 `.so` 文件依赖
   - 如示例中的 `"libffmpeg.so": "file:./src/main/cpp/types/libffmpeg"`

### Native 依赖的层次结构

基于示例项目分析，Native 模块的依赖具有以下层次：

**第一层**: 模块自身产出的动态库
- 如 ffmpeg 模块产出 libffmpeg.so
- 如 filemgr 模块产出 libfilemgr.so

**第二层**: 第三方静态库依赖
- FFmpeg 核心库（libavcodec.a, libavformat.a 等）
- 编解码库（libx264.a, libx265.a 等）
- 工具库（libpng.a, libxml2.a 等）

**第三层**: 系统动态库依赖
- HarmonyOS 系统库（libace_napi.z.so, libohaudio.so 等）
- 标准 C/C++ 库

### Native 依赖的动态链接标记

**关键原则**: 所有 Native 模块与 ArkTS 模块的交互都通过动态链接实现

**标记规则**:
1. ArkTS 模块 → Native 模块: 标记为动态链接
2. Native 模块内部的 .a 文件: 静态链接（构建时合并）
3. Native 模块对系统 .so 文件: 动态链接
4. Native 模块产出的 .so 文件: 作为动态链接的目标

## 依赖关系的精确识别

### ArkTS 模块间依赖

**识别方法**: 解析 oh-package.json5 中的 dependencies 字段

**示例分析**: entry 模块依赖
```
"@sj/ffmpeg": "file:../ffmpeg"     → 本地 ffmpeg 模块
"@sj/mediacache": "^1.0.2"        → 外部依赖包
"@sj/filemgr": "file:../filemgr"  → 本地 filemgr 模块
```

**解析规则**:
- `file:` 协议: 建立模块间的直接依赖边
- 版本号依赖: 建立对外部包的依赖边
- 相对路径: 确定依赖模块的实际位置

### Native 依赖识别

**CMakeLists.txt 解析**:
- 解析 `target_link_libraries` 指令
- 识别静态库文件路径（.a 文件）
- 识别动态库依赖（.so 文件）
- 提取系统库依赖

**第三方库目录分析**:
- 扫描 `thirdparty/` 目录结构
- 按架构分类（arm64-v8a, x86_64）
- 提取库文件和头文件信息

## 构件图数据结构设计

### 节点类型定义

- **Project**: 项目根节点（基于 app.json5）
  - 属性: bundleName, version, 根路径
  
- **Module**: 模块节点（基于 module.json5）
  - 属性: name, type (entry/library), 模块路径, isNative
  
- **Library**: 外部库节点（基于 oh-package.json5 依赖）
  - 属性: name, version, source (external/local)
  
- **NativeLib**: Native 库节点（.so/.a 文件）
  - 属性: name, type (static/dynamic), architecture, 文件路径

### 边类型定义

- **ModuleDependency**: 模块间依赖（compile 时）
  - 属性: dependencyType (runtime/dev), version
  
- **NativeLinkage**: Native 链接关系
  - 属性: linkageType (static/dynamic), architecture
  
- **SystemDependency**: 系统库依赖
  - 属性: systemType (harmonyos/standard), linkageType

### 许可证信息提取策略

1. **模块级许可证**: 从各模块的 oh-package.json5 中的 license 字段提取
2. **第三方库许可证**: 需要额外的许可证数据库或扫描第三方库目录中的 LICENSE 文件
3. **系统库许可证**: 基于 HarmonyOS 官方文档或预定义的许可证映射表
4. [CRITICAL] **文件级许可证**：scancode 扫描（后期需要替换）

## 解析算法的执行顺序

### 阶段一: 项目发现

1. **根目录扫描**
   - 读取根目录 build-profile.json5，获取模块列表
   - 读取 AppScope/app.json5，确定项目基本信息
   - 读取根目录 oh-package.json5，获取项目级依赖

2. **模块验证**
   - 扫描各模块目录，验证模块存在性
   - 检查必要的配置文件是否存在

### 阶段二: 模块分析

1. **基础信息提取**
   - 遍历每个模块目录
   - 读取模块的 oh-package.json5，提取依赖声明
   - 读取模块的 module.json5，确定模块类型和能力

2. **构建配置分析**
   - 读取模块的 build-profile.json5，判断是否为 Native 模块
   - 读取模块的 hvigorfile.ts，提取构建时依赖

### 阶段三: Native 深度分析

1. **Native 模块识别**
   - 对识别出的 Native 模块，验证 C/C++ 源码目录
   - 检查 CMakeLists.txt 文件存在性

2. **Native 依赖解析**
   - 解析 CMakeLists.txt，提取 target_link_libraries 中的库依赖
   - 分析第三方库目录结构，识别静态库文件
   - 提取系统库依赖声明

3. **链接关系标记**
   - 标记所有 ArkTS 到 Native 的关系为动态链接
   - 区分 Native 内部的静态链接和动态链接

### 阶段四: 依赖图构建

1. **节点创建**
   - 创建项目根节点
   - 创建模块节点，建立项目到模块的包含关系
   - 创建库节点（外部依赖和 Native 库）

2. **边关系建立**
   - 根据 oh-package.json5 建立模块间依赖边
   - 根据 Native 分析结果建立 Native 依赖边
   - 标记所有边的链接类型（静态/动态）

3. **依赖传递分析**
   - 分析传递依赖关系
   - 处理版本冲突和依赖覆盖

### 阶段五: 验证和优化

1. **完整性检查**
   - 检查依赖图的完整性（无悬空节点）
   - 验证依赖关系的合理性（无循环依赖）
   - 确认所有声明的依赖都能找到对应的目标

2. **图结构优化**
   - 合并重复的库节点
   - 简化冗余的依赖路径
   - 标准化节点和边的属性

3. **许可证信息补充**
   - 为每个节点补充许可证信息
   - 标记许可证缺失的节点
   - 生成许可证兼容性分析的输入数据

## 特殊情况处理

### 错误处理策略

1. **配置文件缺失**: 提供默认值或跳过该模块，记录警告
2. **依赖声明不一致**: 以 oh-package.json5 为准，记录冲突
3. **Native 构建失败**: 标记为 Native 模块但跳过详细分析
4. **循环依赖**: 记录错误并提供依赖路径信息

### 边界情况

1. **空项目**: 只有根节点，无模块依赖
2. **纯 Native 项目**: 所有模块都是 Native 模块
3. **复杂第三方依赖**: 包含多层嵌套的外部依赖
4. **版本冲突**: 同一库的不同版本被不同模块依赖

## 实现建议

### Python 技术栈选择

1. **JSON5 解析**: 使用 `pyjson5` 库处理 .json5 文件
2. **文件系统操作**: 使用 `pathlib` 进行路径操作
3. **图数据结构**: 使用 `igraph` 构建和分析依赖图
4. **CMake 解析**: 使用正则表达式或简单的文本解析
5. **并发处理**: 使用 `concurrent.futures` 并行处理多个模块

### 性能优化

1. **缓存机制**: 缓存已解析的配置文件内容
2. **增量分析**: 支持增量更新依赖图
3. **并行处理**: 并行分析独立的模块
4. **内存优化**: 使用生成器处理大型项目

这个指导文档提供了完整的 hvigor 项目依赖构件图解析策略，涵盖了所有关键配置文件的解析方法、Native 模块的识别策略、以及完整的实现算法。基于这个文档，可以实现一个准确、完整的依赖构件图解析工具，为后续的许可证兼容性分析提供可靠的数据基础。