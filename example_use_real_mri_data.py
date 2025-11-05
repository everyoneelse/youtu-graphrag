"""
使用真实MRI数据的DSPy训练示例

这个脚本演示如何使用您提供的魔角效应数据来训练DSPy模块。

运行方法:
    python example_use_real_mri_data.py
"""

import json
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))


def create_magic_angle_training_data():
    """
    创建魔角效应的训练数据
    
    基于您提供的真实数据，添加专家标注
    """
    
    # 您的原始数据
    original_data = {
        "head_node": {
            "label": "entity",
            "properties": {
                "name": "魔角效应",
                "chunk id": "Dwjxk2M8",
                "schema_type": "MRI伪影"
            }
        },
        "relation": "has_attribute",
        "tail_nodes_to_dedup": [
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
    }
    
    # 清理tail descriptions（去掉metadata）
    clean_tails = []
    for tail in original_data['tail_nodes_to_dedup']:
        # 移除 chunk id
        clean = tail.split(" (chunk id:")[0] if "(chunk id:" in tail else tail
        # 移除 [attribute] 标记
        clean = clean.split(" [attribute]")[0] if "[attribute]" in clean else clean
        clean_tails.append(clean)
    
    print("="*80)
    print("原始数据分析")
    print("="*80)
    print(f"\nHead: {original_data['head_node']['properties']['name']}")
    print(f"Schema Type: {original_data['head_node']['properties']['schema_type']}")
    print(f"Relation: {original_data['relation']}")
    print(f"\nTails ({len(clean_tails)}):")
    for i, tail in enumerate(clean_tails, 1):
        print(f"  [{i}] {tail}")
    
    # 专家标注的去重结果
    print("\n" + "="*80)
    print("专家标注的去重策略")
    print("="*80)
    
    print("\n📊 分析:")
    print("  - 4个\"定义\"描述魔角效应的不同方面")
    print("  - 定义2和定义3表达相同内容（3是2的简化版）✅ 应合并")
    print("  - 定义1强调临床表现（误诊）- 独特信息")
    print("  - 定义4强调组织特性 - 独特信息")
    print("  - 其他属性（角度、条件、效果等）都是独立信息")
    
    gold_groups = [
        {
            "members": [2, 3],
            "representative": 2,
            "rationale": "定义3是定义2的简化版本，都描述角度-信号增高的物理原理"
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
            "rationale": "强调纤维组织特性，不同于其他定义的侧重点"
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
    
    print("\n✅ 标注结果:")
    for i, group in enumerate(gold_groups, 1):
        members_text = [clean_tails[idx-1] for idx in group['members']]
        print(f"\n  Group {i}:")
        print(f"    Members ({len(group['members'])}):")
        for m in members_text:
            print(f"      - {m[:70]}...")
        print(f"    Representative: {clean_tails[group['representative']-1][:60]}...")
        print(f"    Rationale: {group['rationale']}")
    
    # 生成聚类结果（用于clustering训练）
    gold_clusters = [
        [2, 3],    # 两个相似的定义
        [1],       # 临床表现定义
        [4],       # 角度
        [5],       # 条件
        [6],       # 效果
        [7],       # 组织特性定义
        [8],       # 特点
        [9]        # T2时间
    ]
    
    # 创建训练样本
    training_sample = {
        "head_entity": "魔角效应",
        "relation": "has_attribute",
        "tail_descriptions": clean_tails,
        "original_tails": original_data['tail_nodes_to_dedup'],
        "gold_clusters": gold_clusters,
        "gold_groups": gold_groups,
        "metadata": {
            "domain": "医学影像 - MRI伪影",
            "schema_type": "MRI伪影",
            "complexity": "高 - 多个定义描述不同方面",
            "challenge": "需要医学专业知识判断哪些定义可以合并"
        }
    }
    
    return training_sample


def test_with_dspy(training_sample):
    """
    使用DSPy模块测试这个训练样本
    """
    try:
        import dspy
        from models.constructor.dspy_semantic_dedup import (
            SemanticClusteringModule,
            SemanticDedupModule,
            MultiStageDedupPipeline
        )
    except ImportError as e:
        print(f"\n⚠️  无法导入DSPy模块: {e}")
        print("请先安装: pip install dspy-ai")
        return
    
    import os
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("\n⚠️  未找到OPENAI_API_KEY，跳过DSPy测试")
        print("如需测试，请设置: export OPENAI_API_KEY=your_key")
        return
    
    print("\n" + "="*80)
    print("使用DSPy模块测试")
    print("="*80)
    
    # 配置DSPy
    lm = dspy.OpenAI(model="gpt-3.5-turbo", api_key=api_key, max_tokens=2500)
    dspy.settings.configure(lm=lm)
    
    # 测试clustering
    print("\n🔸 测试Clustering...")
    clustering_module = SemanticClusteringModule()
    
    try:
        clusters = clustering_module(
            head_entity=training_sample['head_entity'],
            relation=training_sample['relation'],
            tail_descriptions=training_sample['tail_descriptions']
        )
        
        print(f"✓ Clustering完成: {len(clusters)} clusters")
        for i, cluster in enumerate(clusters[:3], 1):  # 只显示前3个
            members = [training_sample['tail_descriptions'][m-1][:40] + "..." 
                      for m in cluster.get('members', [])]
            print(f"  Cluster {i}: {members}")
    except Exception as e:
        print(f"✗ Clustering失败: {e}")
    
    # 测试deduplication
    print("\n🔸 测试Deduplication...")
    dedup_module = SemanticDedupModule(prompt_type="attribute")
    
    batch_entries = [
        {
            "description": desc,
            "context_summaries": [f"- {desc}是魔角效应的一个属性"]
        }
        for desc in training_sample['tail_descriptions']
    ]
    
    try:
        groups, reasoning = dedup_module(
            head_entity=training_sample['head_entity'],
            relation=training_sample['relation'],
            head_contexts=["- 魔角效应是一种MRI伪影"],
            batch_entries=batch_entries
        )
        
        print(f"✓ Dedup完成: {len(groups)} groups")
        
        # 对比gold labels
        gold_group_count = len(training_sample['gold_groups'])
        print(f"\n  Gold标注: {gold_group_count} groups")
        print(f"  DSPy输出: {len(groups)} groups")
        
        if abs(len(groups) - gold_group_count) <= 2:
            print(f"  ✓ 分组数量接近!")
        else:
            print(f"  ⚠️  分组数量差异较大")
        
    except Exception as e:
        print(f"✗ Dedup失败: {e}")


def save_as_training_data(training_sample, output_path="data/mri_magic_angle_training.json"):
    """
    保存为DSPy训练数据格式
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 创建DSPy Example
    try:
        import dspy
        example = dspy.Example(
            head_entity=training_sample['head_entity'],
            relation=training_sample['relation'],
            tail_descriptions=training_sample['tail_descriptions'],
            gold_clusters=training_sample['gold_clusters'],
            gold_groups=training_sample['gold_groups']
        ).with_inputs("head_entity", "relation", "tail_descriptions")
        
        # 保存
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump([example.toDict()], f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ 训练数据已保存到: {output_path}")
        print(f"\n下一步:")
        print(f"  python scripts/train_dspy_modules.py \\")
        print(f"    --train-data {output_path} \\")
        print(f"    --train-all")
        
    except ImportError:
        # 如果没有dspy，直接保存dict
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump([training_sample], f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ 训练数据已保存到: {output_path}")


def main():
    """主函数"""
    print("\n" + "="*80)
    print("使用真实MRI数据训练DSPy - 魔角效应示例")
    print("="*80)
    print("\n这个示例展示如何将您的真实医学数据用于训练DSPy模块")
    
    # 创建训练数据
    training_sample = create_magic_angle_training_data()
    
    # 保存训练数据
    save_as_training_data(training_sample)
    
    # 测试DSPy（如果环境配置好）
    test_with_dspy(training_sample)
    
    print("\n" + "="*80)
    print("示例完成!")
    print("="*80)
    
    print("\n📚 更多信息:")
    print("  - 如何标注更多数据: USING_YOUR_DATA_FOR_DSPY.md")
    print("  - 数据转换脚本: scripts/convert_real_data_to_dspy.py")
    print("  - DSPy快速开始: DSPY_QUICKSTART.md")
    
    print("\n💡 建议:")
    print("  1. 准备10-20个类似的标注样本")
    print("  2. 使用 convert_real_data_to_dspy.py 批量转换")
    print("  3. 训练DSPy模块")
    print("  4. 在实际数据上评估效果")


if __name__ == "__main__":
    main()
