#!/usr/bin/env python3
"""
测试LLM聚类结果不一致性检测

这个脚本演示如何检测和报告LLM聚类结果中的不一致性问题。
"""

import re
from typing import List, Dict, Tuple


def validate_clustering_inconsistencies(clusters: list, cluster_details: list) -> list:
    """
    验证聚类结果中rationale与members的不一致。
    
    Returns:
        List of inconsistencies found
    """
    
    merge_keywords = [
        r'应该?合并', r'可合并', r'需要合并', r'建议合并',
        r'should.*merge', r'can.*merge', r'need.*merge',
        r'identical', r'equivalent', r'same', r'完全一致', r'信息.*一致',
        r'互换使用', r'interchangeable', r'同义', r'synonym'
    ]
    
    separate_keywords = [
        r'应该?分开', r'保持.*独立', r'单独.*组', r'不.*合并',
        r'should.*separate', r'keep.*separate', r'distinct', r'different',
        r'不同', r'有差异', r'不一致'
    ]
    
    inconsistencies_found = []
    
    for idx, detail in enumerate(cluster_details):
        rationale = detail.get('rationale', '') or detail.get('llm_rationale', '') or detail.get('description', '')
        members = detail.get('members', [])
        
        if not rationale or len(members) == 0:
            continue
        
        rationale_lower = rationale.lower()
        
        # Check for merge keywords
        has_merge_keyword = any(re.search(pattern, rationale_lower, re.IGNORECASE) 
                               for pattern in merge_keywords)
        
        # Check for separation keywords
        has_separate_keyword = any(re.search(pattern, rationale_lower, re.IGNORECASE)
                                  for pattern in separate_keywords)
        
        # Case 1: Rationale says "merge" but only 1 member
        if has_merge_keyword and len(members) == 1 and not has_separate_keyword:
            # Extract referenced groups
            referenced_groups = []
            group_matches = re.findall(r'组\s*(\d+)', rationale)
            referenced_groups.extend([int(g) - 1 for g in group_matches if g.isdigit()])
            
            cluster_matches = re.findall(r'cluster\s*(\d+)', rationale_lower)
            referenced_groups.extend([int(c) for c in cluster_matches if c.isdigit()])
            
            inconsistency = {
                'type': 'singleton_but_should_merge',
                'cluster_idx': idx,
                'members': members,
                'rationale': rationale,
                'referenced_groups': list(set(referenced_groups)),
                'severity': 'high'
            }
            inconsistencies_found.append(inconsistency)
    
    return inconsistencies_found


def test_case_1_user_reported():
    """测试用户报告的真实案例"""
    print("=" * 80)
    print("测试案例1: 用户报告的截断伪影解决方案去重问题")
    print("=" * 80)
    
    # 模拟LLM返回的聚类结果
    clusters = [
        [0, 1],  # 组1: 增加相位编码步数 + 增加相位编码方向的分辨率
        [2],     # 组2: 增加相位编码
        [3],     # 组3: 增加矩阵
        [4],     # 组4: 增加相位编码方向的矩阵 (问题在这里!)
        [5]      # 组5: 增大采集矩阵
    ]
    
    cluster_details = [
        {
            "members": [0, 1],
            "rationale": '"增加相位编码步数"与"增加相位编码方向的分辨率"指同一操作：在相位编码方向采集更多步级，从而提升该方向的空间分辨率。二者信息完全一致，可互换使用。'
        },
        {
            "members": [2],
            "rationale": '"增加相位编码"虽与组1方向相同，但表述过于简略，未明确是"步数"还是"矩阵"，信息粒度不同，不宜合并。'
        },
        {
            "members": [3],
            "rationale": '"增加矩阵"泛指扩大整个成像矩阵（可含频率与相位两方向），与仅针对相位编码方向的组1/组3并非同一实体，保留独立。'
        },
        {
            "members": [4],  # ❌ 问题：只有1个成员
            "rationale": '"增加相位编码方向的矩阵"即扩大相位编码步数，与组1/组2所指操作完全一致，信息无差异，可合并。'  # ❌ 但rationale说要合并!
        },
        {
            "members": [5],
            "rationale": '"增大采集矩阵"与组4同义，均指整体矩阵扩大，区别于仅针对相位方向的组1/组2/组5，保持独立。'
        }
    ]
    
    # 运行验证
    inconsistencies = validate_clustering_inconsistencies(clusters, cluster_details)
    
    # 输出结果
    print(f"\n发现 {len(inconsistencies)} 处不一致\n")
    
    for inc in inconsistencies:
        print(f"❌ 不一致 #{inc['cluster_idx']}:")
        print(f"   类型: {inc['type']}")
        print(f"   成员: {inc['members']}")
        print(f"   引用的组: {inc['referenced_groups']}")
        print(f"   理由: {inc['rationale'][:150]}...")
        print(f"   严重性: {inc['severity']}")
        print()
    
    # 建议修复
    if inconsistencies:
        print("💡 修复建议:")
        for inc in inconsistencies:
            if inc['type'] == 'singleton_but_should_merge':
                if inc['referenced_groups']:
                    target_groups = ', '.join([f"组{g+1}" for g in inc['referenced_groups']])
                    print(f"   - 将成员 {inc['members']} 合并到 {target_groups}")
                else:
                    print(f"   - 检查成员 {inc['members']} 的rationale，手动判断应合并到哪个组")
    
    print("\n" + "=" * 80)
    
    return len(inconsistencies) > 0


def test_case_2_correct_clustering():
    """测试正确的聚类结果（不应有警告）"""
    print("\n" + "=" * 80)
    print("测试案例2: 正确的聚类结果（无不一致）")
    print("=" * 80)
    
    clusters = [
        [0, 1, 2],  # 合并的组
        [3],        # 独立的组
    ]
    
    cluster_details = [
        {
            "members": [0, 1, 2],
            "rationale": "这三个实体表示相同的概念，信息完全一致，应该合并。"  # ✅ rationale说合并，members确实合并了
        },
        {
            "members": [3],
            "rationale": "这个实体与其他实体语义不同，保持独立。"  # ✅ rationale说独立，members确实是单独的
        }
    ]
    
    inconsistencies = validate_clustering_inconsistencies(clusters, cluster_details)
    
    print(f"\n发现 {len(inconsistencies)} 处不一致")
    
    if len(inconsistencies) == 0:
        print("✅ 测试通过！聚类结果一致性良好。")
    else:
        print("❌ 测试失败！不应该有不一致。")
    
    print("\n" + "=" * 80)
    
    return len(inconsistencies) == 0


def test_case_3_multiple_inconsistencies():
    """测试多个不一致的情况"""
    print("\n" + "=" * 80)
    print("测试案例3: 多个不一致情况")
    print("=" * 80)
    
    clusters = [
        [0, 1],
        [2],  # ❌ 应该合并但单独了
        [3],  # ❌ 应该合并但单独了
        [4]
    ]
    
    cluster_details = [
        {
            "members": [0, 1],
            "rationale": "These are identical entities that should be merged together."
        },
        {
            "members": [2],
            "rationale": "This is equivalent to cluster 1 and should be merged with it."
        },
        {
            "members": [3],
            "rationale": "Same concept as members 0 and 1, can be merged."
        },
        {
            "members": [4],
            "rationale": "This is distinct from others and should remain separate."
        }
    ]
    
    inconsistencies = validate_clustering_inconsistencies(clusters, cluster_details)
    
    print(f"\n发现 {len(inconsistencies)} 处不一致\n")
    
    for inc in inconsistencies:
        print(f"❌ 不一致 #{inc['cluster_idx']}: {inc['rationale'][:80]}...")
    
    expected_count = 2
    if len(inconsistencies) == expected_count:
        print(f"\n✅ 测试通过！正确检测到 {expected_count} 处不一致。")
    else:
        print(f"\n❌ 测试失败！预期 {expected_count} 处，实际 {len(inconsistencies)} 处。")
    
    print("\n" + "=" * 80)
    
    return len(inconsistencies) == expected_count


if __name__ == "__main__":
    print("LLM聚类不一致性检测测试\n")
    
    results = []
    
    # 运行测试
    results.append(("用户报告案例", test_case_1_user_reported()))
    results.append(("正确聚类案例", test_case_2_correct_clustering()))
    results.append(("多不一致案例", test_case_3_multiple_inconsistencies()))
    
    # 总结
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {name}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！不一致性检测功能正常工作。")
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败，需要检查。")
