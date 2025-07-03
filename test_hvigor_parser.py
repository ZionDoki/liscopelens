#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test script for Hvigor parser implementation.
"""

import argparse
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from liscopelens.parser.hvigor.project_parser import HvigorProjectParser
from liscopelens.utils.structure import Config
from liscopelens.utils.graph import GraphManager


def test_hvigor_parser():
    """Test the Hvigor parser with the ffmpeg_harmony_os project."""
    
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
    
    print(f"Testing Hvigor parser with project: {project_path}")
    print("=" * 60)
    
    try:
        # Parse the project
        context = parser.parse(project_path)
        
        print("\n" + "=" * 60)
        print("PARSING RESULTS:")
        print("=" * 60)
        
        # Display results
        nodes = list(context.nodes(data=True))
        edges = list(context.edges(data=True))
        
        print(f"Total nodes: {len(nodes)}")
        print(f"Total edges: {len(edges)}")
        
        print("\nNODES:")
        print("-" * 40)
        for node_id, node_data in nodes:
            node_type = node_data.get('type', 'unknown')
            name = node_data.get('name', node_id)
            is_native = node_data.get('is_native', False)
            native_indicator = " [NATIVE]" if is_native else ""
            print(f"  {node_type.upper()}: {name}{native_indicator}")
            print(f"    Label: {node_id}")
            if 'path' in node_data:
                print(f"    Path: {node_data['path']}")
            print()
        
        print("EDGES:")
        print("-" * 40)
        for edge in edges:
            source, target, edge_data = edge[0], edge[1], edge[2]
            edge_type = edge_data.get('type', 'unknown')
            relationship = edge_data.get('relationship', '')
            dependency_type = edge_data.get('dependency_type', '')
            linkage_type = edge_data.get('linkage_type', '')
            
            print(f"  {source} -> {target}")
            print(f"    Type: {edge_type}")
            if relationship:
                print(f"    Relationship: {relationship}")
            if dependency_type:
                print(f"    Dependency: {dependency_type}")
            if linkage_type:
                print(f"    Linkage: {linkage_type}")
            print()
        
        # Save the graph
        output_file = "hvigor_test_output.json"
        context.save(output_file)
        print(f"Graph saved to: {output_file}")
        
        print("\n" + "=" * 60)
        print("TEST COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_hvigor_parser()
    sys.exit(0 if success else 1)