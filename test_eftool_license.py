#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试 eftool/LICENSE 文件的许可证处理
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from liscopelens.utils.structure import DualLicense, DualUnit, SPDXParser
from liscopelens.parser.scancode import ScancodeParser

def test_eftool_license_detection():
    """测试 eftool/LICENSE 文件检测"""
    print("=== 测试 eftool/LICENSE 文件检测 ===")
    
    # 模拟一个 ScancodeParser 实例
    import argparse
    from liscopelens.utils.structure import Config
    
    args = argparse.Namespace()
    config = Config()
    
    try:
        parser = ScancodeParser(args, config)
        
        # 测试 eftool/LICENSE 文件路径
        file_path = "eftool/LICENSE"
        project_root = Path(".")
        result = parser._detect_license_files(file_path, project_root)
        
        if result == "eftool":
            print(f"✓ eftool/LICENSE 检测正确，前缀: {result}")
        else:
            print(f"✗ eftool/LICENSE 检测错误，期望前缀 'eftool'，实际: {result}")
            
    except Exception as e:
        print(f"✗ 检测失败: {e}")

def test_apache_llvm_exception_parsing():
    """测试 Apache-2.0 AND LLVM-exception 解析"""
    print("\n=== 测试 Apache-2.0 AND LLVM-exception 解析 ===")
    
    spdx_parser = SPDXParser()
    
    # 测试不同的 SPDX 表达式
    test_expressions = [
        "Apache-2.0 AND LLVM-exception",
        "Apache-2.0 WITH LLVM-exception",
        "Apache-2.0 OR (Apache-2.0 WITH LLVM-exception)"
    ]
    
    for expr in test_expressions:
        try:
            result = spdx_parser(expr)
            print(f"表达式: {expr}")
            print(f"解析结果:")
            for group in result:
                for unit in group:
                    exceptions_str = f" WITH {', '.join(unit['exceptions'])}" if unit.get('exceptions') else ""
                    print(f"  - {unit['spdx_id']}{exceptions_str}")
            print()
        except Exception as e:
            print(f"✗ 解析失败 '{expr}': {e}")

def test_exception_application():
    """测试例外条款应用到 Apache-2.0"""
    print("=== 测试例外条款应用到 Apache-2.0 ===")
    
    # 创建包含 Apache-2.0 的 DualLicense
    dual_license = DualLicense([
        frozenset([
            DualUnit("Apache-2.0")
        ])
    ])
    
    print(f"原始许可证: {[unit['spdx_id'] for group in dual_license for unit in group]}")
    
    # 手动应用 LLVM-exception 到 Apache-2.0（虽然通常不这样做）
    try:
        # 注意：LLVM-exception 通常不适用于 Apache-2.0，但这里测试功能
        modified_license = dual_license.apply_exception_to_targets(
            "LLVM-exception", 
            ["Apache-2.0"]
        )
        
        print("修改后的许可证:")
        for group in modified_license:
            for unit in group:
                exceptions_str = f" WITH {', '.join(unit['exceptions'])}" if unit.get('exceptions') else ""
                print(f"  - {unit['spdx_id']}{exceptions_str}")
        
        # 验证结果
        apache_units = [unit for group in modified_license for unit in group if unit['spdx_id'] == 'Apache-2.0']
        if apache_units and 'LLVM-exception' in apache_units[0].get('exceptions', []):
            print("✓ LLVM-exception 成功应用到 Apache-2.0")
        else:
            print("✗ LLVM-exception 应用失败")
            
    except Exception as e:
        print(f"✗ 应用例外条款时出错: {e}")

if __name__ == "__main__":
    test_eftool_license_detection()
    test_apache_llvm_exception_parsing()
    test_exception_application()
    
    print("\n=== eftool/LICENSE 测试完成 ===")