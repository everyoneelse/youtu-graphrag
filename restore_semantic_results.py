#!/usr/bin/env python3
"""
脚本：从triple_deduplicate_semantic保存的中间结果还原semantic_results

用法：
    python restore_semantic_results.py <intermediate_results_file.json>

输出：
    - 还原的semantic_results列表，保存为pickle文件
    - 可以直接用于替换_concurrent_llm_calls的输出
"""

import json
import pickle
import sys
import os
from typing import List, Dict, Any


def restore_semantic_results_from_intermediate(intermediate_file: str) -> List[Dict[str, Any]]:
    """
    从中间结果文件还原semantic_results
    
    Args:
        intermediate_file: 中间结果JSON文件路径
        
    Returns:
        semantic_results: 还原的semantic_results列表，格式与_concurrent_llm_calls返回值相同
    """
    print(f"Loading intermediate results from: {intermediate_file}")
    
    with open(intermediate_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    semantic_results = []
    
    # 检查文件类型
    if data.get('dedup_type') == 'edge_deduplication':
        print(f"Processing edge deduplication results...")
        print(f"Total triples: {len(data['triples'])}")
        
        # 遍历每个三元组
        for triple_idx, triple_data in enumerate(data['triples']):
            head_id = triple_data['head_id']
            head_name = triple_data['head_name']
            relation = triple_data['relation']
            
            print(f"\nProcessing triple {triple_idx + 1}/{len(data['triples'])}: "
                  f"{head_name} -{relation}-> ...")
            
            # 遍历该三元组的所有llm_groups
            for llm_result in triple_data.get('llm_groups', []):
                cluster_id = llm_result['cluster_id']
                batch_indices = llm_result['batch_indices']
                groups = llm_result['groups']
                
                # 重建LLM响应的JSON格式
                llm_response = {
                    "groups": []
                }
                
                for group in groups:
                    # 将local indices转换为1-based（LLM输出格式）
                    members_1based = [m + 1 for m in group['members']]
                    representative_1based = group['representative'] + 1 if group.get('representative') is not None else 1
                    
                    llm_response["groups"].append({
                        "members": members_1based,
                        "representative": representative_1based,
                        "rationale": group.get('rationale', '')
                    })
                
                # 构建semantic_result条目
                result = {
                    'type': 'semantic',
                    'metadata': {
                        'group_idx': triple_idx,  # 使用triple索引作为group_idx
                        'cluster_idx': cluster_id,
                        'batch_num': 0,  # 从llm_groups的顺序推断batch_num
                        'batch_indices': batch_indices,
                        'overflow_indices': []
                    },
                    'response': json.dumps(llm_response, ensure_ascii=False),
                    'error': None
                }
                
                semantic_results.append(result)
    
    elif data.get('dedup_type') == 'keyword_deduplication':
        print(f"Processing keyword deduplication results...")
        print(f"Total communities: {len(data['communities'])}")
        
        # 遍历每个community
        for comm_idx, comm_data in enumerate(data['communities']):
            comm_id = comm_data['community_id']
            
            print(f"\nProcessing community {comm_idx + 1}/{len(data['communities'])}: ID={comm_id}")
            
            # 遍历该community的所有llm_groups
            for llm_result in comm_data.get('llm_groups', []):
                cluster_id = llm_result['cluster_id']
                batch_indices = llm_result['batch_indices']
                groups = llm_result['groups']
                
                # 重建LLM响应的JSON格式
                llm_response = {
                    "groups": []
                }
                
                for group in groups:
                    members_1based = [m + 1 for m in group['members']]
                    representative_1based = group['representative'] + 1 if group.get('representative') is not None else 1
                    
                    llm_response["groups"].append({
                        "members": members_1based,
                        "representative": representative_1based,
                        "rationale": group.get('rationale', '')
                    })
                
                # 构建semantic_result条目
                result = {
                    'type': 'semantic',
                    'metadata': {
                        'comm_idx': comm_idx,  # keyword dedup使用comm_idx
                        'cluster_idx': cluster_id,
                        'batch_num': 0,
                        'batch_indices': batch_indices,
                        'overflow_indices': []
                    },
                    'response': json.dumps(llm_response, ensure_ascii=False),
                    'error': None
                }
                
                semantic_results.append(result)
    
    else:
        raise ValueError(f"Unknown dedup_type: {data.get('dedup_type')}")
    
    print(f"\n✅ Successfully restored {len(semantic_results)} semantic results")
    return semantic_results


def save_semantic_results(semantic_results: List[Dict[str, Any]], output_file: str):
    """保存semantic_results为pickle文件"""
    print(f"\nSaving semantic_results to: {output_file}")
    
    with open(output_file, 'wb') as f:
        pickle.dump(semantic_results, f)
    
    print(f"✅ Saved {len(semantic_results)} results")
    
    # 也保存为JSON格式方便查看
    json_output = output_file.replace('.pkl', '.json')
    with open(json_output, 'w', encoding='utf-8') as f:
        json.dump(semantic_results, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Also saved as JSON: {json_output}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python restore_semantic_results.py <intermediate_results_file.json>")
        print("\nExample:")
        print("  python restore_semantic_results.py output/dedup_intermediate/demo_edge_dedup_20241023_123456.json")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    if not os.path.exists(input_file):
        print(f"❌ Error: File not found: {input_file}")
        sys.exit(1)
    
    # 生成输出文件名
    base_name = os.path.basename(input_file)
    base_name = base_name.replace('_edge_dedup_', '_semantic_results_')
    base_name = base_name.replace('_keyword_dedup_', '_semantic_results_')
    base_name = base_name.replace('.json', '.pkl')
    
    output_dir = os.path.dirname(input_file)
    output_file = os.path.join(output_dir, base_name)
    
    try:
        # 还原semantic_results
        semantic_results = restore_semantic_results_from_intermediate(input_file)
        
        # 保存结果
        save_semantic_results(semantic_results, output_file)
        
        print(f"\n{'='*60}")
        print(f"✅ 完成！现在你可以使用还原的semantic_results：")
        print(f"{'='*60}")
        print(f"\n1. Pickle文件（用于Python加载）：")
        print(f"   {output_file}")
        print(f"\n2. JSON文件（用于查看）：")
        print(f"   {output_file.replace('.pkl', '.json')}")
        print(f"\n3. 如何使用：")
        print(f"   ```python")
        print(f"   import pickle")
        print(f"   with open('{output_file}', 'rb') as f:")
        print(f"       semantic_results = pickle.load(f)")
        print(f"   # 现在可以直接使用semantic_results，跳过_concurrent_llm_calls")
        print(f"   ```")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
