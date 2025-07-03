#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Complete test script for Hvigor parser implementation (Stage 1 + Stage 2).
"""

import argparse
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from liscopelens.parser.hvigor.project_parser import HvigorProjectParser
from liscopelens.parser.hvigor.arkts_mapping import HvigorArkTSMappingParser
from liscopelens.utils.structure import Config
from liscopelens.utils.graph import GraphManager


def test_stage_one():
    """Test Stage 1: Project Discovery."""
    print("=" * 60)
    print("STAGE 1: PROJECT DISCOVERY")
    print("=" * 60)
    
    # Create mock arguments
    args = argparse.Namespace()
    args.hvigor_path = "../ffmpeg_harmony_os"
    args.output = "test_output"
    
    # Create mock config
    config = Config()
    
    # Initialize parser
    parser = HvigorProjectParser(args, config)
    
    # Test project path
    project_path = "../ffmpeg_harmony_os"
    
    try:
        # Parse the project
        context = parser.parse(project_path)
        
        # Display results
        nodes = list(context.nodes(data=True))
        edges = list(context.edges(data=True))
        
        print(f"✓ Stage 1 completed. Total nodes: {len(nodes)}, Total edges: {len(edges)}")
        
        # Save stage 1 results
        output_file = "hvigor_stage1_output.json"
        context.save(output_file)
        print(f"✓ Stage 1 graph saved to: {output_file}")
        
        return context, True
        
    except Exception as e:
        print(f"✗ Stage 1 failed: {e}")
        import traceback
        traceback.print_exc()
        return None, False


def test_stage_two(stage1_context):
    """Test Stage 2: ArkTS File Mapping."""
    print("\n" + "=" * 60)
    print("STAGE 2: ARKTS FILE MAPPING")
    print("=" * 60)
    
    # Create mock arguments
    args = argparse.Namespace()
    args.hvigor_path = "../ffmpeg_harmony_os"
    args.output = "test_output"
    
    # Create mock config
    config = Config()
    
    # Initialize ArkTS mapping parser
    parser = HvigorArkTSMappingParser(args, config)
    
    # Test project path
    project_path = "../ffmpeg_harmony_os"
    
    try:
        # Parse with existing context from stage 1
        context = parser.parse(project_path, stage1_context)
        
        # Display results
        nodes = list(context.nodes(data=True))
        edges = list(context.edges(data=True))
        
        print(f"✓ Stage 2 completed. Total nodes: {len(nodes)}, Total edges: {len(edges)}")
        
        # Count file nodes added in stage 2
        file_nodes = [n for n in nodes if n[1].get('type') == 'file']
        print(f"✓ Added {len(file_nodes)} file nodes")
        
        # Save stage 2 results
        output_file = "hvigor_stage2_output.json"
        context.save(output_file)
        print(f"✓ Stage 2 graph saved to: {output_file}")
        
        return context, True
        
    except Exception as e:
        print(f"✗ Stage 2 failed: {e}")
        import traceback
        traceback.print_exc()
        return None, False


def display_complete_results(context):
    """Display complete parsing results."""
    print("\n" + "=" * 60)
    print("COMPLETE PARSING RESULTS:")
    print("=" * 60)
    
    # Display results
    nodes = list(context.nodes(data=True))
    edges = list(context.edges(data=True))
    
    print(f"Total nodes: {len(nodes)}")
    print(f"Total edges: {len(edges)}")
    
    # Group nodes by type
    node_types = {}
    for node_id, node_data in nodes:
        node_type = node_data.get('type', 'unknown')
        if node_type not in node_types:
            node_types[node_type] = []
        node_types[node_type].append((node_id, node_data))
    
    print("\nNODES BY TYPE:")
    print("-" * 40)
    for node_type, type_nodes in node_types.items():
        print(f"\n{node_type.upper()} ({len(type_nodes)} nodes):")
        for node_id, node_data in type_nodes[:5]:  # Show first 5 of each type
            name = node_data.get('name', node_id)
            is_native = node_data.get('is_native', False)
            native_indicator = " [NATIVE]" if is_native else ""
            print(f"  • {name}{native_indicator}")
            print(f"    ID: {node_id}")
            if 'path' in node_data:
                print(f"    Path: {node_data['path']}")
        if len(type_nodes) > 5:
            print(f"  ... and {len(type_nodes) - 5} more")
    
    print(f"\nEDGES:")
    print("-" * 40)
    edge_types = {}
    for edge in edges:
        source, target, edge_data = edge[0], edge[1], edge[2]
        edge_type = edge_data.get('type', 'unknown')
        if edge_type not in edge_types:
            edge_types[edge_type] = 0
        edge_types[edge_type] += 1
    
    for edge_type, count in edge_types.items():
        print(f"  {edge_type}: {count} edges")


def test_hvigor_complete():
    """Test the complete Hvigor parser (Stage 1 + Stage 2)."""
    
    project_path = "../ffmpeg_harmony_os"
    print(f"Testing complete Hvigor parser with project: {project_path}")
    
    # Stage 1: Project Discovery
    stage1_context, stage1_success = test_stage_one()
    if not stage1_success:
        return False
    
    # Stage 2: ArkTS File Mapping
    stage2_context, stage2_success = test_stage_two(stage1_context)
    if not stage2_success:
        return False
    
    # Display complete results
    display_complete_results(stage2_context)
    
    # Save final results
    final_output = "hvigor_complete_output.json"
    stage2_context.save(final_output)
    print(f"\n✓ Final complete graph saved to: {final_output}")
    
    print("\n" + "=" * 60)
    print("COMPLETE TEST FINISHED SUCCESSFULLY!")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    success = test_hvigor_complete()
    sys.exit(0 if success else 1)