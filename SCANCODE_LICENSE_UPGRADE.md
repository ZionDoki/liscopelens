# SCANCODE LICENSE 节点策略升级说明

## 升级概述

本次升级实现了对 SCANCODE LICENSE 节点的感知和处理，主要包括两个核心功能：

1. **LICENSE 文件感知与前缀规则**：自动检测 LICENSE 文件并以 AND 方式应用到相应路径下的节点
2. **例外条款智能处理**：自动将例外条款应用到其默认作用的标准许可证

## 核心修改内容

### 1. 例外条款定义增强

在 `liscopelens/resources/exceptions/` 目录下的例外条款定义文件中新增了 `default_target` 属性：

```toml
# LLVM-exception.toml
human_review = true
default_target = ["GPL-2.0-only", "GPL-2.0-or-later", "GPL-3.0-only", "GPL-3.0-or-later"]

[special.relicense]
protect_scope = ["DYNAMIC_LINKING", "STATIC_LINKING"]
escape_scope = []
target = ["public-domain"]
```

**说明**：`default_target` 定义了该例外条款默认作用的标准许可证 SPDX ID 列表。

### 2. 数据结构扩展

#### LicenseFeat 类增强
在 `liscopelens/utils/structure.py` 中的 `LicenseFeat` 类新增了 `default_target` 属性：

```python
@dataclass
class LicenseFeat:
    spdx_id: str
    # ... 其他属性
    default_target: list[str] = field(default_factory=list)  # 新增
```

#### DualLicense 类新增方法
在 `DualLicense` 类中新增了 `apply_exception_to_targets` 方法：

```python
def apply_exception_to_targets(self, exception_spdx_id: str, target_spdx_ids: list[str]) -> "DualLicense":
    """
    Apply exception license to specific target licenses within this DualLicense.
    
    Args:
        exception_spdx_id: SPDX ID of the exception license
        target_spdx_ids: List of target license SPDX IDs that this exception should apply to
        
    Returns:
        DualLicense: New DualLicense instance with exceptions applied
    """
```

### 3. ScancodeParser 升级

#### 新增属性
```python
def __init__(self, args: argparse.Namespace, config: Config):
    # ... 原有初始化
    self.license_paths = {}  # 存储 LICENSE 文件路径和其许可证
    self.detected_exceptions = {}  # 存储检测到的例外条款
```

#### 新增方法

1. **LICENSE 文件检测**
```python
def _detect_license_files(self, file_path: str, project_root: Path) -> Optional[str]:
    """检测文件是否为 LICENSE 文件并返回目录前缀"""
```

2. **例外条款目标加载**
```python
def _load_exceptions_with_targets(self) -> dict[str, list[str]]:
    """加载例外条款及其默认作用目标"""
```

3. **LICENSE 前缀规则应用**
```python
def _apply_license_prefix_rules(self, context: GraphManager, project_root: Path):
    """按前缀规则应用 LICENSE 文件许可证"""
```

4. **例外条款规则应用**
```python
def _apply_exception_rules(self, context: GraphManager):
    """应用例外条款到匹配的目标许可证"""
```

#### 修改的方法

1. **add_license 方法增强**
   - 检测 LICENSE 文件并记录路径
   - 记录检测到的例外条款
   - 避免 LICENSE 文件本身的重复处理

2. **parse 方法增强**
   - 在处理完所有文件后应用 LICENSE 前缀规则
   - 应用例外条款规则

## 工作流程

### 第一阶段：文件扫描与检测
1. 扫描所有文件，检测 LICENSE 文件（如 LICENSE、COPYING 等）
2. 记录 LICENSE 文件的路径前缀和对应的许可证信息
3. 记录所有检测到的例外条款

### 第二阶段：LICENSE 前缀规则应用
1. 遍历所有代码节点
2. 检查节点路径是否匹配 LICENSE 文件的前缀
3. 使用 AND 操作将 LICENSE 许可证与现有许可证合并

### 第三阶段：例外条款智能应用
1. 加载所有例外条款的默认作用目标
2. 遍历所有节点，检查是否包含目标许可证
3. 自动将例外条款应用到相应的目标许可证

## 使用示例

### 例外条款自动处理
```python
# 假设检测到以下许可证组合：
# - Apache-2.0 WITH LLVM-exception
# - GPL-2.0-only
# - MIT

# 系统会自动将 LLVM-exception 应用到所有 GPL-2.0 许可证：
# 结果：
# - Apache-2.0 WITH LLVM-exception  
# - GPL-2.0-only WITH LLVM-exception  # 自动应用
# - MIT
```

### LICENSE 文件前缀规则
```
项目结构：
project_root/
├── LICENSE (Apache-2.0)
├── src/
│   ├── main.c
│   └── utils.c
└── modules/
    ├── LICENSE (MIT)
    └── module.c

处理结果：
- src/main.c: 原有许可证 AND Apache-2.0
- src/utils.c: 原有许可证 AND Apache-2.0  
- modules/module.c: 原有许可证 AND MIT
```

## 配置说明

### 支持的 LICENSE 文件模式
- LICENSE
- LICENCE  
- COPYING
- COPYRIGHT
- LICENSE.*（如 LICENSE.txt）
- LICENSE-*（如 LICENSE-APACHE）

### 例外条款配置
在例外条款的 `.toml` 文件中添加 `default_target` 配置：

```toml
# 示例：为自定义例外条款配置默认目标
default_target = ["GPL-3.0-only", "LGPL-2.1-only"]
```

## 测试验证

运行 `test_license_upgrade.py` 可以验证升级功能：

```bash
python test_license_upgrade.py
```

预期输出：
```
=== 测试例外条款加载 ===
✓ LLVM-exception default_target 配置正确

=== 测试 DualLicense 例外条款应用 ===
✓ LLVM-exception 成功应用到 GPL-2.0-only

=== 测试 LICENSE 文件检测 ===
✓ 所有 LICENSE 文件检测正常
```

## 向后兼容性

本次升级完全保持向后兼容：
- 现有的 scancode 解析功能保持不变
- 新功能为增强性功能，不影响现有工作流
- 所有现有的配置和用法继续有效

## 注意事项

1. **例外条款验证**：系统会验证例外条款和目标许可证的有效性
2. **路径匹配**：LICENSE 前缀规则使用精确的路径前缀匹配
3. **AND 操作**：LICENSE 许可证使用 AND 方式与现有许可证合并
4. **处理顺序**：先应用 LICENSE 前缀规则，再应用例外条款规则