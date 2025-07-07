#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试新的 LICENSE 节点策略升级功能
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from liscopelens.utils.structure import DualLicense, DualUnit, load_exceptions
from liscopelens.parser.scancode import ScancodeParser

def test_exception_loading():
    """测试例外条款加载"""
    print("=== 测试例外条款加载 ===")
    
    exceptions = load_exceptions()
    
    # 验证 LLVM-exception 的 default_target 属性
    if "LLVM-exception" in exceptions:
        llvm_exception = exceptions["LLVM-exception"]
        print(f"LLVM-exception default_target: {llvm_exception.default_target}")
        
        expected_targets = ["GPL-2.0-only", "GPL-2.0-or-later", "GPL-3.0-only", "GPL-3.0-or-later"]
        if llvm_exception.default_target == expected_targets:
            print("✓ LLVM-exception default_target 配置正确")
        else:
            print("✗ LLVM-exception default_target 配置错误")
    else:
        print("✗ 未找到 LLVM-exception")

def test_dual_license_exception_application():
    """测试 DualLicense 例外条款应用"""
    print("\n=== 测试 DualLicense 例外条款应用 ===")
    
    # 创建包含 GPL-2.0 和 MIT 的 DualLicense
    dual_license = DualLicense([
        frozenset([
            DualUnit("GPL-2.0-only"),
            DualUnit("MIT")
        ])
    ])
    
    print(f"原始许可证: {[unit['spdx_id'] for group in dual_license for unit in group]}")
    
    # 应用 LLVM-exception 到 GPL-2.0
    try:
        modified_license = dual_license.apply_exception_to_targets(
            "LLVM-exception", 
            ["GPL-2.0-only"]
        )
        
        print("修改后的许可证:")
        for group in modified_license:
            for unit in group:
                exceptions_str = f" WITH {', '.join(unit['exceptions'])}" if unit.get('exceptions') else ""
                print(f"  - {unit['spdx_id']}{exceptions_str}")
        
        # 验证结果
        gpl_units = [unit for group in modified_license for unit in group if unit['spdx_id'] == 'GPL-2.0-only']
        if gpl_units and 'LLVM-exception' in gpl_units[0].get('exceptions', []):
            print("✓ LLVM-exception 成功应用到 GPL-2.0-only")
        else:
            print("✗ LLVM-exception 应用失败")
            
    except Exception as e:
        print(f"✗ 应用例外条款时出错: {e}")

def test_license_file_detection():
    """测试 LICENSE 文件检测"""
    print("\n=== 测试 LICENSE 文件检测 ===")
    
    # 模拟一个 ScancodeParser 实例
    import argparse
    from liscopelens.utils.structure import Config
    
    args = argparse.Namespace()
    config = Config()
    
    try:
        parser = ScancodeParser(args, config)
        
        # 测试不同的 LICENSE 文件路径
        test_cases = [
            ("LICENSE", "root level LICENSE file"),
            ("module/LICENSE", "module level LICENSE file"),
            ("src/main/LICENSE.txt", "LICENSE with extension"),
            ("docs/COPYING", "COPYING file"),
            ("regular_file.py", "regular Python file")
        ]
        
        for file_path, description in test_cases:
            project_root = Path(".")
            result = parser._detect_license_files(file_path, project_root)
            if result:
                print(f"✓ {description}: 检测到 LICENSE 文件，前缀: {result}")
            else:
                print(f"- {description}: 非 LICENSE 文件")
                
    except Exception as e:
        print(f"✗ LICENSE 文件检测测试失败: {e}")

if __name__ == "__main__":
    test_exception_loading()
    test_dual_license_exception_application()
    test_license_file_detection()
    
    print("\n=== 升级功能测试完成 ===")