"""
将真实的去重数据转换为DSPy训练格式

这个脚本将您的实际数据转换为DSPy可以使用的训练样本。

使用方法:
    python scripts/convert_real_data_to_dspy.py \
        --input data/real_dedup_data.json \
        --output data/dspy_training_from_real.json
"""

import json
import argparse
from pathlib import Path
from typing import List, Dict
import dspy


def analyze_dedup_case(head_name: str, relation: str, tails: List[str]) -> Dict:
    """
    分析一个去重case，提供人工标注的指导
    
    这个函数会打印出tail列表，帮助人工判断哪些应该合并。
    """
    print(f"\n{'='*80}")
    print(f"Head: {head_name}")
    print(f"Relation: {relation}")
    print(f"{'='*80}")
    print(f"\nTails to analyze ({len(tails)}):")
    for i, tail in enumerate(tails, 1):
        # 提取主要内容（去掉chunk id等metadata）
        main_content = tail.split(" (chunk id:")[0] if "(chunk id:" in tail else tail
        main_content = main_content.split(" [attribute]")[0] if "[attribute]" in main_content else main_content
        print(f"  [{i}] {main_content}")
    
    print(f"\n分析建议:")
    
    # 检测是否有多个"定义"
    definitions = [i for i, t in enumerate(tails, 1) if t.startswith("定义:")]
    if len(definitions) > 1:
        print(f"  ⚠️  发现 {len(definitions)} 个定义 (indices: {definitions})")
        print(f"      建议: 判断这些定义是否表达相同的概念")
        print(f"           - 如果是相同概念的不同表述 → 合并")
        print(f"           - 如果强调不同方面 → 保持分开")
    
    # 检测属性类型
    has_angle = any("角度" in t for t in tails)
    has_condition = any("条件" in t for t in tails)
    has_effect = any("效果" in t for t in tails)
    has_property = any("特点" in t or "性质" in t for t in tails)
    
    if has_angle:
        print(f"  ℹ️  包含角度信息")
    if has_condition:
        print(f"  ℹ️  包含条件信息")
    if has_effect:
        print(f"  ℹ️  包含效果描述")
    if has_property:
        print(f"  ℹ️  包含特性描述")
    
    return {
        "has_definitions": len(definitions),
        "definition_indices": definitions,
        "attribute_types": {
            "angle": has_angle,
            "condition": has_condition,
            "effect": has_effect,
            "property": has_property
        }
    }


def create_gold_labels_for_magic_angle_example() -> Dict:
    """
    为魔角效应示例创建标准答案
    
    这是基于医学知识的专家标注：
    - 3个定义描述的是同一个现象，但侧重点不同
    - 其他属性（角度、条件、效果等）是独立的信息
    """
    # 实际的tail列表
    tails = [
        "定义:魔角效应伪影，在短TE序列上较为显著，常被误诊为损伤 (chunk id: Dwjxk2M8) [attribute]",
        "定义:在关节磁共振扫描过程中，当关节软骨的轴线与主磁场轴形成约55度角时，成像结果表现出更高的信号的现象 (chunk id: LxRPnW2L) [attribute]",
        "定义:在特定角度下MRI信号异常增高的现象 (chunk id: PHuCr1nf) [attribute]",
        "关键角度: 55° (chunk id: PHuCr1nf) [attribute]",
        "条件: 短TE序列 (chunk id: PHuCr1nf) [attribute]",
        "效果: 局部异常增高的高信号 (chunk id: PHuCr1nf) [attribute]",
        "定义:特殊走向的纤维组织出现虚假的相对高信号 (chunk id: IwfMagF6) [attribute]",
        "特点:角度依赖性、组织依赖性、TE依赖性 (chunk id: IwfMagF6) [attribute]",
        "T2弛豫时间延长:最多可延长两倍以上 (chunk id: IwfMagF6) [attribute]"
    ]
    
    # 专家标注的聚类结果
    # 策略1: 保守去重 - 只合并明显重复的
    conservative_clusters = [
        [1, 2, 3],  # 三个定义可以聚在一起考虑
        [4],        # 角度信息
        [5],        # 条件
        [6],        # 效果
        [7],        # 另一个定义（强调纤维组织）
        [8],        # 特点
        [9]         # T2时间
    ]
    
    # 策略2: 积极去重 - 合并相关定义
    aggressive_clusters = [
        [1, 2, 3, 7],  # 所有定义合并（都在描述魔角效应的本质）
        [4],           # 角度
        [5],           # 条件
        [6],           # 效果
        [8],           # 特点
        [9]            # T2时间
    ]
    
    # 最终去重组（基于医学专业知识）
    # 判断依据:
    # - 定义1: 强调临床表现（伪影、误诊）
    # - 定义2: 强调物理原理（55度角、信号增高）
    # - 定义3: 简化描述（特定角度、信号增高）
    # - 定义4: 强调组织特性（纤维组织、虚假信号）
    # 
    # 定义2和3可以合并（都强调角度-信号关系，3是2的简化）
    # 定义1和4应该保留（强调不同方面）
    gold_groups = [
        {
            "members": [2, 3],
            "representative": 2,
            "rationale": "都描述角度导致信号增高的物理现象，定义3是定义2的简化版本"
        },
        {
            "members": [1],
            "representative": 1,
            "rationale": "强调临床表现和误诊风险，是独特的信息"
        },
        {
            "members": [4],
            "representative": 4,
            "rationale": "关键角度参数，独立信息"
        },
        {
            "members": [5],
            "representative": 5,
            "rationale": "条件信息，独立"
        },
        {
            "members": [6],
            "representative": 6,
            "rationale": "效果描述，独立"
        },
        {
            "members": [7],
            "representative": 7,
            "rationale": "强调纤维组织特性，不同于其他定义"
        },
        {
            "members": [8],
            "representative": 8,
            "rationale": "依赖性特点，独立信息"
        },
        {
            "members": [9],
            "representative": 9,
            "rationale": "T2时间参数，独立信息"
        }
    ]
    
    return {
        "head_entity": "魔角效应",
        "relation": "has_attribute",
        "tail_descriptions": tails,
        "gold_clusters": conservative_clusters,  # 用于clustering训练
        "gold_groups": gold_groups,  # 用于dedup训练
        "notes": {
            "domain": "医学影像 - MRI伪影",
            "challenge": "专业术语，多个定义描述同一现象的不同方面",
            "strategy": "保留不同侧重的定义，合并重复描述"
        }
    }


def convert_real_data_to_dspy_format(data_list: List[Dict], include_unlabeled: bool = False) -> List[dspy.Example]:
    """
    将真实数据转换为DSPy训练格式
    
    Args:
        data_list: 原始数据列表，每个元素包含:
            - head_node: {label, properties}
            - relation: str
            - tail_nodes_to_dedup: List[str]
            - dedup_results: Dict (可能为空)
            - deduped_tails: List[str]
        include_unlabeled: 是否包含未标注的数据（用于后续人工标注）
    
    Returns:
        DSPy Example列表
    """
    examples = []
    
    for item in data_list:
        head_name = item['head_node']['properties'].get('name', 'Unknown')
        relation = item['relation']
        tails = item['tail_nodes_to_dedup']
        
        # 提取干净的tail descriptions（去掉metadata）
        clean_tails = []
        for tail in tails:
            # 移除 chunk id
            clean_tail = tail.split(" (chunk id:")[0] if "(chunk id:" in tail else tail
            # 移除 [attribute] 标记
            clean_tail = clean_tail.split(" [attribute]")[0] if "[attribute]" in clean_tail else clean_tail
            clean_tails.append(clean_tail)
        
        # 检查是否已经有标注结果
        has_labels = False
        gold_clusters = None
        gold_groups = None
        
        if 'gold_clusters' in item:
            has_labels = True
            gold_clusters = item['gold_clusters']
            gold_groups = item.get('gold_groups', None)
        elif 'dedup_results' in item and item['dedup_results']:
            # 尝试从dedup_results中提取
            # 这需要根据您的实际数据格式调整
            has_labels = True
            # TODO: 解析dedup_results
        
        # 如果有标注或者允许包含未标注数据
        if has_labels or include_unlabeled:
            example_dict = {
                "head_entity": head_name,
                "relation": relation,
                "tail_descriptions": clean_tails,
                "original_tails": tails,  # 保留原始数据供参考
            }
            
            if gold_clusters:
                example_dict["gold_clusters"] = gold_clusters
            if gold_groups:
                example_dict["gold_groups"] = gold_groups
            
            # 创建DSPy Example
            example = dspy.Example(**example_dict)
            
            # 设置输入字段
            if has_labels:
                example = example.with_inputs("head_entity", "relation", "tail_descriptions")
            
            examples.append(example)
    
    return examples


def interactive_labeling(data_item: Dict) -> Dict:
    """
    交互式标注一个数据样本
    
    引导用户完成人工标注
    """
    head_name = data_item['head_node']['properties'].get('name', 'Unknown')
    relation = data_item['relation']
    tails = data_item['tail_nodes_to_dedup']
    
    # 清理tails
    clean_tails = []
    for tail in tails:
        clean_tail = tail.split(" (chunk id:")[0] if "(chunk id:" in tail else tail
        clean_tail = clean_tail.split(" [attribute]")[0] if "[attribute]" in clean_tail else clean_tail
        clean_tails.append(clean_tail)
    
    print(f"\n{'='*80}")
    print(f"标注样本")
    print(f"{'='*80}")
    print(f"Head: {head_name}")
    print(f"Relation: {relation}")
    print(f"\nTails ({len(clean_tails)}):")
    for i, tail in enumerate(clean_tails, 1):
        print(f"  [{i}] {tail}")
    
    # 分析建议
    analysis = analyze_dedup_case(head_name, relation, clean_tails)
    
    print(f"\n请标注去重结果:")
    print(f"格式: 输入应该合并的tail的索引，用逗号分隔。每行一个组。")
    print(f"示例:")
    print(f"  1,2,3  (表示tail 1、2、3应该合并)")
    print(f"  4      (表示tail 4单独一组)")
    print(f"  5,6    (表示tail 5、6合并)")
    print(f"输入 'done' 完成标注\n")
    
    groups = []
    while True:
        line = input("输入一组 (或 'done'): ").strip()
        if line.lower() == 'done':
            break
        
        try:
            members = [int(x.strip()) for x in line.split(',')]
            # 验证索引
            if all(1 <= m <= len(clean_tails) for m in members):
                groups.append({
                    "members": members,
                    "representative": members[0],
                    "rationale": input(f"  为什么合并 {members}? ").strip()
                })
            else:
                print(f"  ❌ 错误: 索引必须在 1-{len(clean_tails)} 之间")
        except:
            print(f"  ❌ 格式错误，请重试")
    
    # 检查是否所有tail都被分配
    assigned = set()
    for group in groups:
        assigned.update(group['members'])
    
    unassigned = set(range(1, len(clean_tails) + 1)) - assigned
    if unassigned:
        print(f"\n⚠️  未分配的tail: {sorted(unassigned)}")
        for idx in sorted(unassigned):
            groups.append({
                "members": [idx],
                "representative": idx,
                "rationale": "Unassigned (kept separate)"
            })
    
    return {
        "head_entity": head_name,
        "relation": relation,
        "tail_descriptions": clean_tails,
        "original_tails": tails,
        "gold_groups": groups,
        "gold_clusters": [[g['members'] for g in groups]],  # 简化的聚类
    }


def main():
    parser = argparse.ArgumentParser(description="转换真实数据为DSPy训练格式")
    
    parser.add_argument(
        '--input',
        type=str,
        help='输入JSON文件路径（您的原始数据）'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='data/dspy_training_from_real.json',
        help='输出JSON文件路径'
    )
    parser.add_argument(
        '--interactive',
        action='store_true',
        help='交互式标注模式'
    )
    parser.add_argument(
        '--include-unlabeled',
        action='store_true',
        help='包含未标注的数据'
    )
    parser.add_argument(
        '--create-example',
        action='store_true',
        help='创建魔角效应示例'
    )
    
    args = parser.parse_args()
    
    if args.create_example:
        # 创建魔角效应示例
        print("创建魔角效应示例...")
        example_data = create_gold_labels_for_magic_angle_example()
        
        # 保存为训练数据格式
        examples = [dspy.Example(**example_data).with_inputs(
            "head_entity", "relation", "tail_descriptions"
        )]
        
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump([ex.toDict() for ex in examples], f, indent=2, ensure_ascii=False)
        
        print(f"✓ 示例已保存到 {output_path}")
        
        # 显示分析
        tails = example_data['tail_descriptions']
        analyze_dedup_case(example_data['head_entity'], example_data['relation'], tails)
        
        print(f"\n✓ 标注结果:")
        for i, group in enumerate(example_data['gold_groups'], 1):
            members_desc = [tails[idx-1][:50] + "..." for idx in group['members']]
            print(f"\n  Group {i}:")
            print(f"    Members: {members_desc}")
            print(f"    Rationale: {group['rationale']}")
        
        return
    
    if not args.input:
        print("❌ 错误: 需要指定 --input 文件路径")
        print("\n或者使用 --create-example 创建示例")
        return
    
    # 读取输入数据
    with open(args.input, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if not isinstance(data, list):
        data = [data]
    
    print(f"读取了 {len(data)} 个样本")
    
    if args.interactive:
        # 交互式标注
        labeled_examples = []
        for i, item in enumerate(data, 1):
            print(f"\n样本 {i}/{len(data)}")
            labeled = interactive_labeling(item)
            labeled_examples.append(labeled)
            
            if i < len(data):
                cont = input("\n继续下一个? (y/n): ").strip().lower()
                if cont != 'y':
                    break
        
        # 转换为DSPy格式
        examples = convert_real_data_to_dspy_format(labeled_examples)
    else:
        # 自动转换（需要数据已有标注）
        examples = convert_real_data_to_dspy_format(data, args.include_unlabeled)
    
    # 保存
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump([ex.toDict() for ex in examples], f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ 转换完成!")
    print(f"  输入样本: {len(data)}")
    print(f"  输出样本: {len(examples)}")
    print(f"  保存到: {output_path}")
    
    print(f"\n下一步:")
    print(f"  python scripts/train_dspy_modules.py \\")
    print(f"    --train-data {output_path} \\")
    print(f"    --train-all")


if __name__ == "__main__":
    main()
