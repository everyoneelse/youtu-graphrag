#!/usr/bin/env python3
"""
测试两步验证机制：semantic dedup + LLM validation

这个脚本演示如何使用LLM进行自我校验和修正聚类不一致。
"""

import json
from typing import List, Dict


def simulate_initial_clustering():
    """模拟LLM初始聚类结果（含不一致）"""
    return {
        "clusters": [
            {
                "members": [0, 1],
                "description": '"增加相位编码步数"与"增加相位编码方向的分辨率"指同一操作，完全一致。'
            },
            {
                "members": [2],
                "description": '"增加相位编码"表述过于简略，信息粒度不同，不宜合并。'
            },
            {
                "members": [3],
                "description": '"增加矩阵"泛指扩大整个成像矩阵，与组1并非同一实体。'
            },
            {
                "members": [4],  # ❌ 不一致：只有1个成员
                "description": '"增加相位编码方向的矩阵"即扩大相位编码步数，与组1完全一致，信息无差异，可合并。'  # ❌ 但说要合并！
            },
            {
                "members": [5],
                "description": '"增大采集矩阵"与组3同义，保持独立。'
            }
        ]
    }


def simulate_validation_response():
    """模拟LLM校验响应（检测并修正不一致）"""
    return {
        "has_inconsistencies": True,
        "inconsistencies": [
            {
                "cluster_ids": [4, 0],
                "issue_type": "singleton_should_merge",
                "description": "Cluster 4 has 1 member but description says it's identical to cluster 0 and should merge",
                "suggested_fix": "merge_cluster_4_into_0"
            }
        ],
        "corrected_clusters": [
            {
                "members": [0, 1, 4],  # ✅ 修正：将4合并进来
                "description": "增加相位编码步数/方向的分辨率/矩阵（合并后的组）"
            },
            {
                "members": [2],
                "description": '"增加相位编码"表述过于简略，保持独立。'
            },
            {
                "members": [3],
                "description": '"增加矩阵"泛指整体矩阵，保持独立。'
            },
            {
                "members": [5],
                "description": '"增大采集矩阵"与组3同义，保持独立。'
            }
        ]
    }


def demonstrate_two_step_validation():
    """演示两步验证流程"""
    print("=" * 80)
    print("两步验证机制演示")
    print("=" * 80)
    
    # 候选项
    candidates = [
        "[0] 增加相位编码步数 (chunk: 8OcOMgfc, type: 解决方案)",
        "[1] 增加相位编码方向的分辨率 (chunk: 8OcOMgfc, type: 解决方案)",
        "[2] 增加相位编码 (chunk: HQXnd2uF)",
        "[3] 增加矩阵 (chunk: lFV1MqAO, type: 解决方案)",
        "[4] 增加相位编码方向的矩阵 (chunk: TEjwxFfF)",
        "[5] 增大采集矩阵 (chunk: itN6pun7)"
    ]
    
    print("\n【原始候选项】")
    for c in candidates:
        print(f"  {c}")
    
    # Step 1: 初始聚类
    print("\n" + "=" * 80)
    print("STEP 1: 初始LLM聚类")
    print("=" * 80)
    
    initial_result = simulate_initial_clustering()
    
    print("\n初始聚类结果:")
    for idx, cluster in enumerate(initial_result["clusters"]):
        members = cluster["members"]
        desc = cluster["description"]
        print(f"\n  Cluster {idx}: members={members}")
        print(f"    描述: {desc[:80]}...")
        
        # 检测不一致
        if len(members) == 1 and any(keyword in desc for keyword in ["合并", "一致", "同义", "merge", "identical"]):
            print(f"    ⚠️  警告: 描述说要合并，但只有1个成员！")
    
    # Step 2: LLM自我校验
    print("\n" + "=" * 80)
    print("STEP 2: LLM自我校验与修正")
    print("=" * 80)
    
    validation_result = simulate_validation_response()
    
    print(f"\n检测到 {len(validation_result['inconsistencies'])} 处不一致:")
    for inc in validation_result['inconsistencies']:
        print(f"\n  ❌ 不一致:")
        print(f"     涉及cluster: {inc['cluster_ids']}")
        print(f"     类型: {inc['issue_type']}")
        print(f"     描述: {inc['description']}")
        print(f"     建议修复: {inc['suggested_fix']}")
    
    # 修正后的结果
    print("\n" + "=" * 80)
    print("修正后的聚类结果:")
    print("=" * 80)
    
    corrected = validation_result['corrected_clusters']
    for idx, cluster in enumerate(corrected):
        members = cluster["members"]
        desc = cluster["description"]
        print(f"\n  ✅ Cluster {idx}: members={members}")
        print(f"     描述: {desc}")
    
    # 对比
    print("\n" + "=" * 80)
    print("对比总结")
    print("=" * 80)
    
    initial_count = len(initial_result['clusters'])
    corrected_count = len(corrected)
    fixed_count = len(validation_result['inconsistencies'])
    
    print(f"\n  初始聚类: {initial_count} 个clusters")
    print(f"  修正后:   {corrected_count} 个clusters")
    print(f"  修复数量: {fixed_count} 处不一致")
    print(f"  变化:     {initial_count - corrected_count} 个clusters被合并")
    
    print("\n  具体变化:")
    print(f"    • Cluster 4 [成员4] 被合并到 Cluster 0 [成员0,1]")
    print(f"    • 新的 Cluster 0 现在包含成员 [0, 1, 4]")
    
    print("\n" + "=" * 80)
    print("✅ 两步验证成功修正了不一致！")
    print("=" * 80)


def test_validation_benefits():
    """测试两步验证的好处"""
    print("\n\n" + "=" * 80)
    print("两步验证的优势")
    print("=" * 80)
    
    benefits = [
        {
            "title": "1. 自动修正",
            "desc": "LLM可以自己发现并修正不一致，无需人工干预"
        },
        {
            "title": "2. 更高准确性",
            "desc": "两次LLM调用相互校验，减少单次调用的错误"
        },
        {
            "title": "3. 可追溯性",
            "desc": "记录所有修正操作，便于审计和分析"
        },
        {
            "title": "4. 灵活控制",
            "desc": "通过配置可以启用/禁用，适应不同场景"
        },
        {
            "title": "5. 成本优化",
            "desc": "只在需要时启用，embedding聚类可以跳过"
        }
    ]
    
    for benefit in benefits:
        print(f"\n{benefit['title']}")
        print(f"  → {benefit['desc']}")
    
    print("\n" + "=" * 80)


def test_configuration_examples():
    """展示配置示例"""
    print("\n\n" + "=" * 80)
    print("配置示例")
    print("=" * 80)
    
    print("\n【启用两步验证】")
    print("""
semantic_dedup:
  enabled: true
  clustering_method: llm
  enable_clustering_validation: true  # 启用二次校验
  
  clustering_llm:
    temperature: 0.3  # 较低的temperature提高一致性
""")
    
    print("\n【仅使用规则检测（不自动修正）】")
    print("""
semantic_dedup:
  enabled: true
  clustering_method: llm
  enable_clustering_validation: false  # 禁用LLM校验，只用规则检测
""")
    
    print("\n【Embedding聚类（无需LLM校验）】")
    print("""
semantic_dedup:
  enabled: true
  clustering_method: embedding  # embedding聚类通常不会有不一致
  enable_clustering_validation: false
""")


def test_workflow():
    """测试完整工作流"""
    print("\n\n" + "=" * 80)
    print("完整工作流")
    print("=" * 80)
    
    steps = [
        "1. 用户配置 enable_clustering_validation: true",
        "2. 系统进行初始LLM聚类",
        "3. 检测聚类结果中的潜在不一致",
        "4. 如果发现不一致 →",
        "   a. 调用LLM进行二次校验",
        "   b. LLM分析聚类结果",
        "   c. LLM提供修正建议",
        "   d. 系统应用修正",
        "5. 如果未发现不一致 → 使用原始结果",
        "6. 无论如何，都进行规则检测作为备份",
        "7. 记录所有操作到日志"
    ]
    
    print("\n工作流程:")
    for step in steps:
        if step.startswith("   "):
            print(f"    {step[3:]}")
        else:
            print(f"\n{step}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    print("两步验证机制 - 完整演示\n")
    
    # 运行演示
    demonstrate_two_step_validation()
    test_validation_benefits()
    test_configuration_examples()
    test_workflow()
    
    print("\n\n" + "=" * 80)
    print("总结")
    print("=" * 80)
    print("""
两步验证机制 = Semantic Dedup + LLM Self-Validation

优点:
✅ 自动发现并修正LLM聚类中的不一致
✅ 提高聚类准确性（两次LLM调用相互校验）
✅ 完整的审计日志
✅ 灵活的配置选项

使用方法:
1. 在配置中设置 enable_clustering_validation: true
2. 建议配合 clustering_method: llm 使用
3. 查看日志了解修正情况

文件:
• config/example_with_validation.yaml - 示例配置
• models/constructor/kt_gen.py - 核心实现
• 本测试脚本 - 演示效果

立即试用:
python main.py --config config/example_with_validation.yaml --dataset demo --mode all
""")
    
    print("\n" + "=" * 80)
