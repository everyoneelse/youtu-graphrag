"""
创建通用的DSPy训练数据

这个脚本提供通用的训练数据格式，适配当前semantic dedup的实际流程。
不局限于特定领域或特定case。

训练数据格式对应：
  - 任何 head entity
  - 任何 relation type
  - 任何 domain

使用方法:
    # 从真实去重结果批量提取
    python scripts/create_universal_training_data.py \
        --from-dedup-results output/dedup_intermediate/*.json \
        --output data/universal_training.json \
        --sample-size 50

    # 创建多领域示例
    python scripts/create_universal_training_data.py \
        --create-diverse-examples \
        --output data/diverse_training.json
"""

import json
import argparse
from pathlib import Path
from typing import List, Dict, Any
import dspy
from collections import defaultdict


# ========== 通用训练数据格式 ==========

UNIVERSAL_TRAINING_FORMAT = {
    "description": """
    通用DSPy训练样本格式
    
    这个格式适用于任何semantic dedup场景：
    - 任何领域（医学、技术、商业等）
    - 任何关系类型（has_attribute, has_property, located_in等）
    - 任何实体类型（概念、人物、地点等）
    """,
    
    "required_fields": {
        "head_entity": "str - 头实体的描述/名称",
        "relation": "str - 关系类型",
        "tail_descriptions": "List[str] - 待去重的尾实体列表",
    },
    
    "optional_fields": {
        "contexts": "List[List[str]] - 每个tail的上下文信息",
        "metadata": "Dict - 额外的元信息（domain, complexity等）",
        "original_data": "Any - 保留原始数据供参考"
    },
    
    "annotation_fields": {
        "gold_clusters": "List[List[int]] - 聚类标注（1-based indices）",
        "gold_groups": "List[Dict] - 去重标注，每个dict包含members, representative, rationale"
    },
    
    "example": {
        "head_entity": "任意实体名称",
        "relation": "任意关系",
        "tail_descriptions": ["tail 1", "tail 2", "tail 3"],
        "contexts": [
            ["context for tail 1"],
            ["context for tail 2"],
            ["context for tail 3"]
        ],
        "gold_clusters": [[1, 2], [3]],
        "gold_groups": [
            {
                "members": [1, 2],
                "representative": 1,
                "rationale": "为什么合并"
            },
            {
                "members": [3],
                "representative": 3,
                "rationale": "为什么独立"
            }
        ]
    }
}


def extract_from_dedup_results(results_dir: str, sample_size: int = None) -> List[Dict]:
    """
    从真实的去重结果中提取训练样本
    
    这个函数读取 output/dedup_intermediate/*.json 中的去重结果，
    提取高质量的样本作为训练数据。
    
    Args:
        results_dir: 去重结果目录
        sample_size: 采样数量（None表示全部）
    
    Returns:
        提取的训练样本列表
    """
    results_files = list(Path(results_dir).glob("*.json"))
    
    if not results_files:
        print(f"⚠️  未找到去重结果文件: {results_dir}")
        return []
    
    print(f"找到 {len(results_files)} 个去重结果文件")
    
    extracted_samples = []
    
    for result_file in results_files:
        try:
            with open(result_file, 'r', encoding='utf-8') as f:
                result_data = json.load(f)
            
            # 根据实际的intermediate results格式提取
            if 'edges' in result_data:
                # Edge deduplication results
                for edge_result in result_data.get('edges', []):
                    sample = extract_from_edge_result(edge_result)
                    if sample:
                        extracted_samples.append(sample)
            
            elif 'communities' in result_data:
                # Community/keyword deduplication results
                for comm_result in result_data.get('communities', []):
                    sample = extract_from_community_result(comm_result)
                    if sample:
                        extracted_samples.append(sample)
        
        except Exception as e:
            print(f"⚠️  读取文件失败 {result_file}: {e}")
            continue
    
    print(f"提取了 {len(extracted_samples)} 个候选样本")
    
    # 过滤和采样
    filtered_samples = filter_quality_samples(extracted_samples)
    
    if sample_size and len(filtered_samples) > sample_size:
        import random
        filtered_samples = random.sample(filtered_samples, sample_size)
    
    print(f"最终选择 {len(filtered_samples)} 个训练样本")
    
    return filtered_samples


def extract_from_edge_result(edge_result: Dict) -> Dict:
    """从edge dedup结果中提取训练样本"""
    try:
        head_name = edge_result.get('head_name', 'Unknown')
        relation = edge_result.get('relation', 'unknown')
        
        # 提取candidates
        candidates = edge_result.get('candidates', [])
        if not candidates or len(candidates) < 2:
            return None
        
        tail_descriptions = [c.get('description', '') for c in candidates]
        
        # 提取contexts
        contexts = []
        for candidate in candidates:
            ctx = candidate.get('context_summaries', [])
            contexts.append(ctx if ctx else ['- (no context)'])
        
        # 提取clustering结果（如果有）
        clusters_data = edge_result.get('clustering', {}).get('clusters', [])
        gold_clusters = []
        for cluster in clusters_data:
            members = cluster.get('member_indices', [])
            if members:
                # 转换为1-based
                gold_clusters.append([m + 1 for m in members])
        
        # 提取final merges（如果有）
        final_merges = edge_result.get('final_merges', [])
        gold_groups = []
        for merge in final_merges:
            members = merge.get('members', [])
            if members:
                # 转换为1-based
                gold_groups.append({
                    "members": [m + 1 for m in members],
                    "representative": members[0] + 1,
                    "rationale": merge.get('rationale', 'Merged by system')
                })
        
        # 如果没有标注，标记为unlabeled
        if not gold_clusters and not gold_groups:
            return None  # 跳过未标注的
        
        return {
            "head_entity": head_name,
            "relation": relation,
            "tail_descriptions": tail_descriptions,
            "contexts": contexts,
            "gold_clusters": gold_clusters if gold_clusters else None,
            "gold_groups": gold_groups if gold_groups else None,
            "metadata": {
                "source": "edge_dedup",
                "total_candidates": len(candidates)
            }
        }
    
    except Exception as e:
        print(f"  提取edge result失败: {e}")
        return None


def extract_from_community_result(comm_result: Dict) -> Dict:
    """从community/keyword dedup结果中提取训练样本"""
    try:
        head_name = comm_result.get('head_name', 'Unknown')
        relation = 'keyword_of'  # Community结果通常是keyword关系
        
        candidates = comm_result.get('candidates', [])
        if not candidates or len(candidates) < 2:
            return None
        
        tail_descriptions = [c.get('description', '') for c in candidates]
        
        contexts = []
        for candidate in candidates:
            ctx = candidate.get('context_summaries', [])
            contexts.append(ctx if ctx else ['- (no context)'])
        
        # 提取结果...（类似edge）
        clusters_data = comm_result.get('clustering', {}).get('clusters', [])
        gold_clusters = []
        for cluster in clusters_data:
            members = cluster.get('member_indices', [])
            if members:
                gold_clusters.append([m + 1 for m in members])
        
        final_merges = comm_result.get('final_merges', [])
        gold_groups = []
        for merge in final_merges:
            members = merge.get('members', [])
            if members:
                gold_groups.append({
                    "members": [m + 1 for m in members],
                    "representative": members[0] + 1,
                    "rationale": merge.get('rationale', 'Merged by system')
                })
        
        if not gold_clusters and not gold_groups:
            return None
        
        return {
            "head_entity": head_name,
            "relation": relation,
            "tail_descriptions": tail_descriptions,
            "contexts": contexts,
            "gold_clusters": gold_clusters,
            "gold_groups": gold_groups,
            "metadata": {
                "source": "community_dedup",
                "total_candidates": len(candidates)
            }
        }
    
    except Exception as e:
        print(f"  提取community result失败: {e}")
        return None


def filter_quality_samples(samples: List[Dict]) -> List[Dict]:
    """
    过滤高质量的训练样本
    
    标准:
    - 有明确的标注（gold_clusters或gold_groups）
    - tail数量适中（2-20个）
    - 不是trivial case（全部合并或全部分开）
    """
    filtered = []
    
    for sample in samples:
        # 检查是否有标注
        if not sample.get('gold_clusters') and not sample.get('gold_groups'):
            continue
        
        # 检查tail数量
        num_tails = len(sample.get('tail_descriptions', []))
        if num_tails < 2 or num_tails > 20:
            continue
        
        # 检查是否trivial（所有在一组或每个都单独）
        gold_groups = sample.get('gold_groups', [])
        if gold_groups:
            if len(gold_groups) == 1 and len(gold_groups[0]['members']) == num_tails:
                # 所有合并到一组 - trivial
                continue
            if len(gold_groups) == num_tails:
                # 每个都单独 - trivial
                all_singleton = all(len(g['members']) == 1 for g in gold_groups)
                if all_singleton:
                    continue
        
        filtered.append(sample)
    
    return filtered


def create_diverse_examples() -> List[Dict]:
    """
    创建多样化的训练示例
    
    覆盖不同的：
    - 领域（医学、技术、地理、人物等）
    - 关系类型（属性、位置、作者等）
    - 复杂度（简单、中等、困难）
    """
    
    examples = []
    
    # ========== 示例1: 技术领域 - 编程语言版本 ==========
    examples.append({
        "head_entity": "Python",
        "relation": "has_version",
        "tail_descriptions": [
            "Python 3.9",
            "Python 3.9.0",
            "Python 3.10",
            "Python 3.x",
            "Python 3",
            "Python 2.7"
        ],
        "contexts": [
            ["- Python 3.9 released in October 2020"],
            ["- Python 3.9.0 is the initial release of Python 3.9"],
            ["- Python 3.10 released in October 2021"],
            ["- Python 3.x refers to Python 3 series"],
            ["- Python 3 is the current major version"],
            ["- Python 2.7 was the last version of Python 2"]
        ],
        "gold_clusters": [
            [1, 2],    # 3.9 和 3.9.0
            [3],       # 3.10
            [4, 5],    # 3.x 和 3
            [6]        # 2.7
        ],
        "gold_groups": [
            {"members": [1, 2], "representative": 1, "rationale": "3.9.0 is 3.9"},
            {"members": [3], "representative": 3, "rationale": "Different version"},
            {"members": [4, 5], "representative": 5, "rationale": "3.x is generic term for Python 3"},
            {"members": [6], "representative": 6, "rationale": "Different major version"}
        ],
        "metadata": {
            "domain": "技术",
            "complexity": "中等",
            "challenge": "版本号的粒度判断"
        }
    })
    
    # ========== 示例2: 地理领域 - 城市别名 ==========
    examples.append({
        "head_entity": "中国",
        "relation": "has_city",
        "tail_descriptions": [
            "北京",
            "北京市",
            "Beijing",
            "上海",
            "上海市",
            "Shanghai",
            "广州"
        ],
        "contexts": [
            ["- 北京是中国的首都"],
            ["- 北京市是直辖市"],
            ["- Beijing is the capital of China"],
            ["- 上海是中国最大的城市"],
            ["- 上海市是经济中心"],
            ["- Shanghai is a major financial hub"],
            ["- 广州是广东省省会"]
        ],
        "gold_clusters": [
            [1, 2, 3],    # 北京的各种表达
            [4, 5, 6],    # 上海的各种表达
            [7]           # 广州
        ],
        "gold_groups": [
            {"members": [1, 2, 3], "representative": 1, "rationale": "Same city - Beijing"},
            {"members": [4, 5, 6], "representative": 4, "rationale": "Same city - Shanghai"},
            {"members": [7], "representative": 7, "rationale": "Different city"}
        ],
        "metadata": {
            "domain": "地理",
            "complexity": "简单",
            "challenge": "中英文别名"
        }
    })
    
    # ========== 示例3: 人物领域 - 作者名称 ==========
    examples.append({
        "head_entity": "哈利波特系列",
        "relation": "author",
        "tail_descriptions": [
            "J.K. Rowling",
            "J.K.罗琳",
            "罗琳",
            "Joanne Rowling",
            "J. K. Rowling"
        ],
        "contexts": [
            ["- J.K. Rowling is the author of Harry Potter"],
            ["- J.K.罗琳是英国作家"],
            ["- 罗琳创作了哈利波特"],
            ["- Joanne Rowling is her full name"],
            ["- J. K. Rowling (with spaces) is another spelling"]
        ],
        "gold_clusters": [
            [1, 2, 3, 4, 5]    # 所有都是同一个人
        ],
        "gold_groups": [
            {
                "members": [1, 2, 3, 4, 5],
                "representative": 1,
                "rationale": "All refer to the same person - J.K. Rowling"
            }
        ],
        "metadata": {
            "domain": "人物",
            "complexity": "中等",
            "challenge": "中英文、缩写、全名的统一"
        }
    })
    
    # ========== 示例4: 商业领域 - 公司名称 ==========
    examples.append({
        "head_entity": "科技行业",
        "relation": "has_company",
        "tail_descriptions": [
            "Apple Inc.",
            "Apple",
            "苹果公司",
            "Apple Computer",
            "Microsoft Corporation",
            "Microsoft",
            "微软"
        ],
        "contexts": [
            ["- Apple Inc. is officially registered name"],
            ["- Apple is commonly used short form"],
            ["- 苹果公司是中文名称"],
            ["- Apple Computer was the old name before 2007"],
            ["- Microsoft Corporation is official name"],
            ["- Microsoft is common usage"],
            ["- 微软是中文名称"]
        ],
        "gold_clusters": [
            [1, 2, 3, 4],    # Apple相关
            [5, 6, 7]        # Microsoft相关
        ],
        "gold_groups": [
            {
                "members": [1, 2, 3, 4],
                "representative": 1,
                "rationale": "Same company - Apple (including old name)"
            },
            {
                "members": [5, 6, 7],
                "representative": 5,
                "rationale": "Same company - Microsoft"
            }
        ],
        "metadata": {
            "domain": "商业",
            "complexity": "中等",
            "challenge": "公司名称变更、中英文对应"
        }
    })
    
    # ========== 示例5: 属性领域 - 多个不同属性（医学示例）==========
    examples.append({
        "head_entity": "磁共振成像",
        "relation": "has_attribute",
        "tail_descriptions": [
            "无创性检查",
            "非侵入性检查",
            "软组织分辨率高",
            "对软组织有高对比度",
            "检查时间长",
            "扫描时间较长",
            "费用较高",
            "成本高"
        ],
        "contexts": [
            ["- MRI is a non-invasive procedure"],
            ["- MRI does not require surgical incision"],
            ["- MRI provides excellent soft tissue contrast"],
            ["- MRI has superior soft tissue resolution"],
            ["- MRI scans typically take 30-60 minutes"],
            ["- MRI examination duration is longer than CT"],
            ["- MRI costs are generally higher"],
            ["- MRI is more expensive than X-ray"]
        ],
        "gold_clusters": [
            [1, 2],    # 无创性
            [3, 4],    # 软组织分辨率
            [5, 6],    # 时间
            [7, 8]     # 费用
        ],
        "gold_groups": [
            {"members": [1, 2], "representative": 1, "rationale": "Same attribute - non-invasive"},
            {"members": [3, 4], "representative": 3, "rationale": "Same attribute - soft tissue resolution"},
            {"members": [5, 6], "representative": 5, "rationale": "Same attribute - long duration"},
            {"members": [7, 8], "representative": 7, "rationale": "Same attribute - high cost"}
        ],
        "metadata": {
            "domain": "医学",
            "complexity": "中等",
            "challenge": "多个独立属性，每个属性有不同表述"
        }
    })
    
    # ========== 示例6: 困难case - 相似但不同的概念 ==========
    examples.append({
        "head_entity": "机器学习",
        "relation": "sub_field",
        "tail_descriptions": [
            "监督学习",
            "有监督学习",
            "Supervised Learning",
            "无监督学习",
            "Unsupervised Learning",
            "半监督学习",
            "Semi-supervised Learning",
            "强化学习"
        ],
        "contexts": [
            ["- 监督学习使用标注数据"],
            ["- 有监督学习需要标签"],
            ["- Supervised Learning uses labeled data"],
            ["- 无监督学习不需要标签"],
            ["- Unsupervised Learning discovers patterns"],
            ["- 半监督学习结合两者"],
            ["- Semi-supervised Learning uses both labeled and unlabeled"],
            ["- 强化学习通过奖励学习"]
        ],
        "gold_clusters": [
            [1, 2, 3],    # 监督学习
            [4, 5],       # 无监督学习
            [6, 7],       # 半监督学习
            [8]           # 强化学习
        ],
        "gold_groups": [
            {"members": [1, 2, 3], "representative": 1, "rationale": "Same concept - Supervised Learning"},
            {"members": [4, 5], "representative": 4, "rationale": "Same concept - Unsupervised Learning"},
            {"members": [6, 7], "representative": 6, "rationale": "Same concept - Semi-supervised Learning"},
            {"members": [8], "representative": 8, "rationale": "Different concept - Reinforcement Learning"}
        ],
        "metadata": {
            "domain": "计算机科学",
            "complexity": "困难",
            "challenge": "相似但不同的概念，不应合并"
        }
    })
    
    return examples


def convert_to_dspy_examples(samples: List[Dict]) -> List[dspy.Example]:
    """将样本转换为DSPy Example格式"""
    dspy_examples = []
    
    for sample in samples:
        # 创建Example
        example_dict = {
            "head_entity": sample["head_entity"],
            "relation": sample["relation"],
            "tail_descriptions": sample["tail_descriptions"]
        }
        
        # 添加可选字段
        if "contexts" in sample:
            example_dict["contexts"] = sample["contexts"]
        
        if "gold_clusters" in sample:
            example_dict["gold_clusters"] = sample["gold_clusters"]
        
        if "gold_groups" in sample:
            example_dict["gold_groups"] = sample["gold_groups"]
        
        if "metadata" in sample:
            example_dict["metadata"] = sample["metadata"]
        
        # 创建DSPy Example
        example = dspy.Example(**example_dict)
        
        # 标记输入字段
        example = example.with_inputs("head_entity", "relation", "tail_descriptions")
        
        dspy_examples.append(example)
    
    return dspy_examples


def analyze_training_set(samples: List[Dict]):
    """分析训练集的分布"""
    print("\n" + "="*80)
    print("训练集分析")
    print("="*80)
    
    # 统计domain分布
    domains = defaultdict(int)
    relations = defaultdict(int)
    complexities = defaultdict(int)
    
    total_tails = 0
    total_groups = 0
    
    for sample in samples:
        metadata = sample.get('metadata', {})
        domain = metadata.get('domain', 'unknown')
        complexity = metadata.get('complexity', 'unknown')
        
        domains[domain] += 1
        relations[sample['relation']] += 1
        complexities[complexity] += 1
        
        total_tails += len(sample['tail_descriptions'])
        if 'gold_groups' in sample:
            total_groups += len(sample['gold_groups'])
    
    print(f"\n总样本数: {len(samples)}")
    print(f"总tail数: {total_tails}")
    print(f"平均每样本: {total_tails/len(samples):.1f} tails")
    print(f"总groups: {total_groups}")
    
    print(f"\n领域分布:")
    for domain, count in sorted(domains.items(), key=lambda x: -x[1]):
        print(f"  {domain}: {count}")
    
    print(f"\n关系类型分布:")
    for relation, count in sorted(relations.items(), key=lambda x: -x[1]):
        print(f"  {relation}: {count}")
    
    print(f"\n复杂度分布:")
    for complexity, count in sorted(complexities.items(), key=lambda x: -x[1]):
        print(f"  {complexity}: {count}")


def main():
    parser = argparse.ArgumentParser(description="创建通用DSPy训练数据")
    
    parser.add_argument(
        '--from-dedup-results',
        type=str,
        help='从去重结果目录提取（如 output/dedup_intermediate/*.json）'
    )
    parser.add_argument(
        '--create-diverse-examples',
        action='store_true',
        help='创建多样化的示例数据'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='data/universal_training.json',
        help='输出文件路径'
    )
    parser.add_argument(
        '--sample-size',
        type=int,
        help='采样数量'
    )
    parser.add_argument(
        '--show-format',
        action='store_true',
        help='显示训练数据格式说明'
    )
    
    args = parser.parse_args()
    
    if args.show_format:
        print(json.dumps(UNIVERSAL_TRAINING_FORMAT, indent=2, ensure_ascii=False))
        return
    
    samples = []
    
    # 从去重结果提取
    if args.from_dedup_results:
        print("从去重结果提取训练数据...")
        samples.extend(extract_from_dedup_results(
            args.from_dedup_results,
            args.sample_size
        ))
    
    # 创建多样化示例
    if args.create_diverse_examples:
        print("创建多样化示例...")
        samples.extend(create_diverse_examples())
    
    if not samples:
        print("❌ 没有生成任何训练数据")
        print("\n使用方法:")
        print("  --from-dedup-results output/dedup_intermediate")
        print("  --create-diverse-examples")
        return
    
    # 转换为DSPy格式
    dspy_examples = convert_to_dspy_examples(samples)
    
    # 分析
    analyze_training_set(samples)
    
    # 保存
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump([ex.toDict() for ex in dspy_examples], f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ 训练数据已保存到: {output_path}")
    print(f"\n下一步:")
    print(f"  python scripts/train_dspy_modules.py \\")
    print(f"    --train-data {output_path} \\")
    print(f"    --train-all")


if __name__ == "__main__":
    main()
