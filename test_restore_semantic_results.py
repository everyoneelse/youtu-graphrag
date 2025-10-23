#!/usr/bin/env python3
"""
测试脚本：验证semantic_results还原功能

这个脚本会：
1. 创建一个模拟的中间结果文件
2. 调用restore_semantic_results.py还原
3. 验证还原结果的格式和数据
"""

import json
import pickle
import os
import subprocess
import sys
from pathlib import Path


def create_mock_intermediate_results():
    """创建一个模拟的中间结果文件用于测试"""
    
    mock_data = {
        "dataset": "test_dataset",
        "dedup_type": "edge_deduplication",
        "config": {
            "threshold": 0.85,
            "max_batch_size": 8,
            "max_candidates": 0
        },
        "triples": [
            {
                "head_id": "node_1",
                "head_name": "测试实体1",
                "relation": "has_attribute",
                "total_edges": 5,
                "candidates": [
                    {"index": 0, "node_id": "attr_1", "description": "属性1"},
                    {"index": 1, "node_id": "attr_2", "description": "属性2"},
                    {"index": 2, "node_id": "attr_3", "description": "属性3"},
                ],
                "clustering": {
                    "method": "embedding",
                    "threshold": 0.85,
                    "clusters": [
                        {
                            "cluster_id": 0,
                            "size": 3,
                            "member_indices": [0, 1, 2],
                            "members": [
                                {"index": 0, "node_id": "attr_1", "description": "属性1"},
                                {"index": 1, "node_id": "attr_2", "description": "属性2"},
                                {"index": 2, "node_id": "attr_3", "description": "属性3"},
                            ]
                        }
                    ]
                },
                "llm_groups": [
                    {
                        "cluster_id": 0,
                        "batch_indices": [0, 1, 2],
                        "batch_size": 3,
                        "groups": [
                            {
                                "members": [0, 1],
                                "representative": 0,
                                "rationale": "属性1和属性2语义相似，可以合并",
                                "member_details": [
                                    {"local_idx": 0, "global_idx": 0, "description": "属性1"},
                                    {"local_idx": 1, "global_idx": 1, "description": "属性2"}
                                ]
                            },
                            {
                                "members": [2],
                                "representative": 2,
                                "rationale": "属性3独立，不合并",
                                "member_details": [
                                    {"local_idx": 2, "global_idx": 2, "description": "属性3"}
                                ]
                            }
                        ]
                    }
                ],
                "final_merges": [
                    {
                        "representative": {
                            "index": 0,
                            "node_id": "attr_1",
                            "description": "属性1"
                        },
                        "duplicates": [
                            {
                                "index": 1,
                                "node_id": "attr_2",
                                "description": "属性2"
                            }
                        ]
                    }
                ],
                "summary": {
                    "total_edges": 5,
                    "total_clusters": 1,
                    "total_llm_calls": 1,
                    "total_merges": 1,
                    "edges_merged": 1,
                    "final_edges": 2
                }
            },
            {
                "head_id": "node_2",
                "head_name": "测试实体2",
                "relation": "related_to",
                "total_edges": 4,
                "candidates": [
                    {"index": 0, "node_id": "rel_1", "description": "关系1"},
                    {"index": 1, "node_id": "rel_2", "description": "关系2"},
                ],
                "clustering": {
                    "method": "embedding",
                    "threshold": 0.85,
                    "clusters": [
                        {
                            "cluster_id": 0,
                            "size": 2,
                            "member_indices": [0, 1],
                            "members": [
                                {"index": 0, "node_id": "rel_1", "description": "关系1"},
                                {"index": 1, "node_id": "rel_2", "description": "关系2"},
                            ]
                        }
                    ]
                },
                "llm_groups": [
                    {
                        "cluster_id": 0,
                        "batch_indices": [0, 1],
                        "batch_size": 2,
                        "groups": [
                            {
                                "members": [0],
                                "representative": 0,
                                "rationale": "关系1独立",
                                "member_details": [
                                    {"local_idx": 0, "global_idx": 0, "description": "关系1"}
                                ]
                            },
                            {
                                "members": [1],
                                "representative": 1,
                                "rationale": "关系2独立",
                                "member_details": [
                                    {"local_idx": 1, "global_idx": 1, "description": "关系2"}
                                ]
                            }
                        ]
                    }
                ],
                "final_merges": [],
                "summary": {
                    "total_edges": 4,
                    "total_clusters": 1,
                    "total_llm_calls": 1,
                    "total_merges": 0,
                    "edges_merged": 0,
                    "final_edges": 2
                }
            }
        ],
        "summary": {
            "total_triples": 2,
            "total_edges": 9,
            "total_clusters": 2,
            "total_llm_calls": 2,
            "total_merges": 1,
            "total_edges_merged": 1,
            "final_total_edges": 4
        }
    }
    
    # 保存模拟数据
    output_dir = "output/dedup_intermediate"
    os.makedirs(output_dir, exist_ok=True)
    
    test_file = f"{output_dir}/test_edge_dedup_mock.json"
    with open(test_file, 'w', encoding='utf-8') as f:
        json.dump(mock_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Created mock intermediate results: {test_file}")
    return test_file


def test_restore_script(intermediate_file: str):
    """测试restore_semantic_results.py脚本"""
    
    print(f"\n{'='*70}")
    print("测试 restore_semantic_results.py 脚本")
    print(f"{'='*70}\n")
    
    # 运行还原脚本
    cmd = [sys.executable, "restore_semantic_results.py", intermediate_file]
    print(f"Running: {' '.join(cmd)}\n")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    print("STDOUT:")
    print(result.stdout)
    
    if result.stderr:
        print("\nSTDERR:")
        print(result.stderr)
    
    if result.returncode != 0:
        print(f"\n❌ Script failed with return code {result.returncode}")
        return None
    
    # 找到输出文件
    output_file = intermediate_file.replace("_edge_dedup_", "_semantic_results_").replace(".json", ".pkl")
    
    if not os.path.exists(output_file):
        print(f"\n❌ Output file not found: {output_file}")
        return None
    
    print(f"\n✅ Script completed successfully")
    return output_file


def validate_restored_results(pkl_file: str):
    """验证还原的结果"""
    
    print(f"\n{'='*70}")
    print("验证还原的结果")
    print(f"{'='*70}\n")
    
    # 加载pickle文件
    print(f"Loading: {pkl_file}")
    with open(pkl_file, 'rb') as f:
        results = pickle.load(f)
    
    print(f"✅ Loaded {len(results)} results\n")
    
    # 验证结果结构
    errors = []
    
    for i, result in enumerate(results):
        # 检查必需字段
        required_fields = ['type', 'metadata', 'response', 'error']
        for field in required_fields:
            if field not in result:
                errors.append(f"Result {i}: Missing field '{field}'")
        
        # 检查type
        if result.get('type') != 'semantic':
            errors.append(f"Result {i}: Invalid type '{result.get('type')}', expected 'semantic'")
        
        # 检查metadata
        metadata = result.get('metadata', {})
        required_metadata = ['group_idx', 'cluster_idx', 'batch_num', 'batch_indices']
        for field in required_metadata:
            if field not in metadata:
                errors.append(f"Result {i}: Missing metadata field '{field}'")
        
        # 检查response是否是valid JSON
        try:
            response_data = json.loads(result.get('response', ''))
            if 'groups' not in response_data:
                errors.append(f"Result {i}: Response missing 'groups' field")
            else:
                # 检查groups格式
                groups = response_data['groups']
                if not isinstance(groups, list):
                    errors.append(f"Result {i}: 'groups' should be a list")
                else:
                    for j, group in enumerate(groups):
                        if 'members' not in group:
                            errors.append(f"Result {i}, Group {j}: Missing 'members'")
                        if 'representative' not in group:
                            errors.append(f"Result {i}, Group {j}: Missing 'representative'")
                        if 'rationale' not in group:
                            errors.append(f"Result {i}, Group {j}: Missing 'rationale'")
                        
                        # 验证members是1-based
                        members = group.get('members', [])
                        if members and min(members) < 1:
                            errors.append(f"Result {i}, Group {j}: Members should be 1-based (found {members})")
        
        except json.JSONDecodeError as e:
            errors.append(f"Result {i}: Invalid JSON response: {e}")
    
    # 输出验证结果
    if errors:
        print(f"❌ Found {len(errors)} errors:\n")
        for error in errors[:10]:  # 只显示前10个错误
            print(f"  - {error}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more errors")
        return False
    else:
        print("✅ All validation checks passed!")
        
        # 显示示例结果
        print(f"\n{'='*70}")
        print("示例结果：")
        print(f"{'='*70}\n")
        
        if results:
            example = results[0]
            print(f"Type: {example['type']}")
            print(f"Metadata: {json.dumps(example['metadata'], indent=2)}")
            print(f"Response: {example['response'][:200]}...")
            print(f"Error: {example['error']}")
        
        return True


def main():
    """主测试流程"""
    
    print("=" * 70)
    print("测试 Semantic Results 还原功能")
    print("=" * 70)
    
    # Step 1: 创建模拟数据
    print("\nStep 1: 创建模拟中间结果")
    print("-" * 70)
    intermediate_file = create_mock_intermediate_results()
    
    # Step 2: 运行还原脚本
    print("\nStep 2: 运行还原脚本")
    print("-" * 70)
    pkl_file = test_restore_script(intermediate_file)
    
    if not pkl_file:
        print("\n❌ 测试失败：还原脚本未成功运行")
        sys.exit(1)
    
    # Step 3: 验证还原结果
    print("\nStep 3: 验证还原结果")
    print("-" * 70)
    success = validate_restored_results(pkl_file)
    
    # Step 4: 显示总结
    print(f"\n{'='*70}")
    print("测试总结")
    print(f"{'='*70}\n")
    
    if success:
        print("✅ 所有测试通过！")
        print(f"\n生成的文件：")
        print(f"  - 中间结果：{intermediate_file}")
        print(f"  - 还原结果：{pkl_file}")
        print(f"  - JSON格式：{pkl_file.replace('.pkl', '.json')}")
        
        print(f"\n现在你可以：")
        print(f"  1. 查看还原的结果：")
        print(f"     python -c \"import pickle; print(pickle.load(open('{pkl_file}', 'rb')))\"")
        print(f"  2. 在代码中使用缓存的结果")
        print(f"  3. 参考 patch_kt_gen_for_cached_results.md 修改代码")
        
        sys.exit(0)
    else:
        print("❌ 测试失败：验证未通过")
        sys.exit(1)


if __name__ == "__main__":
    main()
