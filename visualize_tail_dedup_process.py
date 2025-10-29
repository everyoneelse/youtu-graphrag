#!/usr/bin/env python3
"""
可视化tail去重处理过程

这个脚本用于演示和可视化tail去重的每个步骤，
帮助理解四个核心功能的工作原理。
"""

from typing import Dict, List, Set
from collections import defaultdict


class DedupVisualizer:
    """去重过程可视化工具"""
    
    def __init__(self):
        self.step_counter = 0
    
    def print_header(self, title: str):
        """打印标题"""
        print("\n" + "=" * 70)
        print(f"  {title}")
        print("=" * 70)
    
    def print_step(self, description: str):
        """打印步骤"""
        self.step_counter += 1
        print(f"\n【步骤 {self.step_counter}】{description}")
        print("-" * 70)
    
    def print_graph_structure(self, title: str, edges: List[tuple], communities: Dict = None):
        """打印图结构"""
        print(f"\n{title}:")
        print("  [三元组]")
        for u, relation, v in edges:
            print(f"    {u} --{relation}--> {v}")
        
        if communities:
            print("\n  [社区]")
            for comm_name, members in communities.items():
                print(f"    {comm_name}:")
                for member in members:
                    print(f"      ← {member}")
    
    def print_mapping(self, mapping: Dict[str, str]):
        """打印映射关系"""
        print("\n  映射关系:")
        for source, target in mapping.items():
            if source == target:
                print(f"    {source} → {target} (代表节点)")
            else:
                print(f"    {source} → {target}")
    
    def demonstrate_edge_dedup(self):
        """演示三元组去重"""
        self.print_header("功能1：三元组（Edges）去重演示")
        
        # 原始数据
        original_edges = [
            ("魔角效应", "解决方案为", "增加TE值 (chunk: A)"),
            ("魔角效应", "解决方案为", "延长TE (chunk: B)"),
            ("魔角效应", "解决方案为", "延长TE值 (chunk: C)"),
            ("魔角效应", "解决方案为", "改变体位 (chunk: B)"),
            ("魔角效应", "解决方案为", "改变扫描体位 (chunk: C)"),
        ]
        
        # 映射关系
        mapping = {
            "增加TE值 (chunk: A)": "延长TE值 (chunk: C)",
            "延长TE (chunk: B)": "延长TE值 (chunk: C)",
            "延长TE值 (chunk: C)": "延长TE值 (chunk: C)",
            "改变体位 (chunk: B)": "改变扫描体位 (chunk: C)",
            "改变扫描体位 (chunk: C)": "改变扫描体位 (chunk: C)",
        }
        
        self.print_graph_structure("原始图", original_edges)
        self.print_mapping(mapping)
        
        # 模拟处理过程
        new_edges = []
        edges_to_remove = []
        existing_edges = set()  # 记录已存在的边
        
        self.print_step("开始处理每条边")
        
        for i, (u, relation, v) in enumerate(original_edges, 1):
            print(f"\n  [{i}] 处理: {u} --{relation}--> {v}")
            
            # 查找代表
            v_rep = mapping.get(v, v)
            print(f"      代表节点: {v_rep}")
            
            if v_rep != v:
                # 检查是否已存在
                edge_sig = (u, relation, v_rep)
                if edge_sig in existing_edges:
                    print(f"      ❌ 边 {u} --{relation}--> {v_rep} 已存在")
                    print(f"      ➜ 删除旧边，不添加新边")
                else:
                    print(f"      ✅ 边 {u} --{relation}--> {v_rep} 不存在")
                    print(f"      ➜ 删除旧边，添加新边")
                    new_edges.append((u, relation, v_rep))
                    existing_edges.add(edge_sig)
                
                edges_to_remove.append((u, relation, v))
            else:
                print(f"      ⭕ 代表是自己，保持不变")
                existing_edges.add((u, relation, v))
        
        # 构建最终图
        final_edges = [e for e in original_edges if e not in edges_to_remove] + new_edges
        
        self.print_step("处理结果")
        print(f"\n  删除的边: {len(edges_to_remove)} 条")
        for u, r, v in edges_to_remove:
            print(f"    ❌ {u} --{r}--> {v}")
        
        print(f"\n  添加的边: {len(new_edges)} 条")
        for u, r, v in new_edges:
            print(f"    ✅ {u} --{r}--> {v}")
        
        self.print_graph_structure("\n最终图", final_edges)
        
        print(f"\n  📊 统计:")
        print(f"    原始边数: {len(original_edges)}")
        print(f"    最终边数: {len(final_edges)}")
        print(f"    减少: {len(original_edges) - len(final_edges)} 条 ({(len(original_edges) - len(final_edges)) / len(original_edges) * 100:.1f}%)")
    
    def demonstrate_community_dedup(self):
        """演示社区去重"""
        self.print_header("功能2：社区（Communities）去重演示")
        
        # 原始社区
        original_community = {
            "TE调整方法社区": [
                "增加TE值 (chunk: A)",
                "延长TE (chunk: B)",
                "延长TE值 (chunk: C)"
            ]
        }
        
        # 映射关系
        mapping = {
            "增加TE值 (chunk: A)": "延长TE值 (chunk: C)",
            "延长TE (chunk: B)": "延长TE值 (chunk: C)",
            "延长TE值 (chunk: C)": "延长TE值 (chunk: C)",
        }
        
        print("\n原始社区结构:")
        for comm_name, members in original_community.items():
            print(f"  {comm_name}:")
            for member in members:
                print(f"    ← {member}")
        
        self.print_mapping(mapping)
        
        self.print_step("处理社区成员")
        
        # 模拟处理
        representatives_in_community = set()
        members_to_remove = []
        members_to_add = []
        
        for member in original_community["TE调整方法社区"]:
            print(f"\n  处理成员: {member}")
            rep = mapping.get(member, member)
            print(f"    代表节点: {rep}")
            
            if rep != member:
                if rep in representatives_in_community:
                    print(f"    ❌ 代表 {rep} 已在社区中")
                    print(f"    ➜ 删除此成员，不添加")
                else:
                    # 检查原始成员中是否已有代表
                    if rep in original_community["TE调整方法社区"]:
                        print(f"    ⚠️  代表 {rep} 原本就在社区中")
                        print(f"    ➜ 删除此成员，不添加（避免重复）")
                        representatives_in_community.add(rep)
                    else:
                        print(f"    ✅ 代表 {rep} 不在社区中")
                        print(f"    ➜ 删除此成员，添加代表")
                        members_to_add.append(rep)
                        representatives_in_community.add(rep)
                
                members_to_remove.append(member)
            else:
                print(f"    ⭕ 代表是自己，保持不变")
                representatives_in_community.add(member)
        
        self.print_step("处理结果")
        
        print(f"\n  删除的成员: {len(members_to_remove)} 个")
        for member in members_to_remove:
            print(f"    ❌ {member}")
        
        print(f"\n  添加的成员: {len(members_to_add)} 个")
        for member in members_to_add:
            print(f"    ✅ {member}")
        
        # 构建最终社区
        final_members = [m for m in original_community["TE调整方法社区"] 
                        if m not in members_to_remove] + members_to_add
        
        print(f"\n最终社区结构:")
        print(f"  TE调整方法社区:")
        for member in final_members:
            print(f"    ← {member}")
        
        print(f"\n  📊 统计:")
        print(f"    原始成员数: {len(original_community['TE调整方法社区'])}")
        print(f"    最终成员数: {len(final_members)}")
        print(f"    去重: {len(original_community['TE调整方法社区']) - len(final_members)} 个")
    
    def demonstrate_edge_existence_check(self):
        """演示边存在性检查（避免重复）"""
        self.print_header("功能4：自动去重 - 避免创建重复边")
        
        self.print_step("场景1：同一cluster的多个成员")
        
        print("\n  假设有以下边要处理:")
        edges = [
            ("魔角效应", "解决方案为", "增加TE值"),
            ("魔角效应", "解决方案为", "延长TE"),
            ("魔角效应", "解决方案为", "延长TE值"),
        ]
        for i, (u, r, v) in enumerate(edges, 1):
            print(f"    [{i}] {u} --{r}--> {v}")
        
        print("\n  所有三个节点都映射到: 延长TE值")
        
        print("\n  处理过程:")
        existing_edges = set()
        operations = []
        
        for i, (u, r, v) in enumerate(edges, 1):
            print(f"\n  [{i}] 处理: {u} --{r}--> {v}")
            target = "延长TE值"
            print(f"      目标: {u} --{r}--> {target}")
            
            edge_sig = (u, r, target)
            if edge_sig in existing_edges:
                print(f"      ❌ 检查结果: 已存在")
                print(f"      ➜ 操作: 只删除，不添加")
                operations.append(f"删除 {u}→{v}")
            else:
                if v == target:
                    print(f"      ⭕ 代表是自己")
                    print(f"      ➜ 操作: 保持不变")
                    operations.append(f"保留 {u}→{v}")
                else:
                    print(f"      ✅ 检查结果: 不存在")
                    print(f"      ➜ 操作: 删除旧边，添加新边")
                    operations.append(f"删除 {u}→{v}, 添加 {u}→{target}")
                existing_edges.add(edge_sig)
        
        print(f"\n  最终结果: 只有1条边 (魔角效应 --解决方案为--> 延长TE值)")
        
        self.print_step("场景2：MultiDiGraph多重边")
        
        print("\n  假设有以下边:")
        multi_edges = [
            ("肺炎", "症状包括", "发热"),
            ("肺炎", "症状包括", "发烧"),  # 映射到发热
            ("肺炎", "并发症为", "发热"),
        ]
        for i, (u, r, v) in enumerate(multi_edges, 1):
            print(f"    [{i}] {u} --{r}--> {v}")
        
        print("\n  映射: 发烧 → 发热")
        
        print("\n  关键点: 必须按 (u, relation, v) 三元组检查重复")
        print("          而不是只按 (u, v) 检查！")
        
        print("\n  处理过程:")
        existing_multi = {}  # relation -> set of (u, v)
        
        for i, (u, r, v) in enumerate(multi_edges, 1):
            print(f"\n  [{i}] 处理: {u} --{r}--> {v}")
            target = "发热" if v == "发烧" else v
            
            if r not in existing_multi:
                existing_multi[r] = set()
            
            edge_sig = (u, target)
            if edge_sig in existing_multi[r]:
                print(f"      ❌ 边 ({u}, {r}, {target}) 已存在")
                print(f"      ➜ 不添加")
            else:
                print(f"      ✅ 边 ({u}, {r}, {target}) 不存在")
                if v == target:
                    print(f"      ➜ 保留原边")
                else:
                    print(f"      ➜ 替换为新边")
                existing_multi[r].add(edge_sig)
        
        print(f"\n  最终结果: 2条边")
        print(f"    肺炎 --症状包括--> 发热")
        print(f"    肺炎 --并发症为--> 发热")
        print(f"\n  ⚠️ 注意: 虽然都是 肺炎→发热，但relation不同，所以都保留！")
    
    def demonstrate_keyword_filter_by(self):
        """演示keyword_filter_by处理"""
        self.print_header("功能3：keyword_filter_by 特殊关系处理")
        
        print("\n  keyword_filter_by 的作用:")
        print("    用于关键词过滤和消歧")
        print("    格式: 关键词节点 --keyword_filter_by--> 实体节点")
        
        self.print_step("示例场景")
        
        # 原始边
        keyword_edges = [
            ('Keyword:"TE"', "keyword_filter_by", "增加TE值 (chunk: A)"),
            ('Keyword:"TE"', "keyword_filter_by", "延长TE (chunk: B)"),
            ('Keyword:"TE"', "keyword_filter_by", "延长TE值 (chunk: C)"),
        ]
        
        mapping = {
            "增加TE值 (chunk: A)": "延长TE值 (chunk: C)",
            "延长TE (chunk: B)": "延长TE值 (chunk: C)",
            "延长TE值 (chunk: C)": "延长TE值 (chunk: C)",
        }
        
        print("\n  原始keyword_filter_by关系:")
        for u, r, v in keyword_edges:
            print(f"    {u} --{r}--> {v}")
        
        self.print_mapping(mapping)
        
        self.print_step("处理过程")
        
        existing = set()
        result_edges = []
        
        for i, (u, r, v) in enumerate(keyword_edges, 1):
            print(f"\n  [{i}] 处理: {u} --> {v}")
            target = mapping.get(v, v)
            print(f"      代表: {target}")
            
            if (u, target) in existing:
                print(f"      ❌ 关系已存在")
                print(f"      ➜ 删除，不添加")
            else:
                if v == target:
                    print(f"      ⭕ 代表是自己")
                    print(f"      ➜ 保留")
                else:
                    print(f"      ✅ 关系不存在")
                    print(f"      ➜ 替换")
                result_edges.append((u, r, target))
                existing.add((u, target))
        
        print("\n  最终keyword_filter_by关系:")
        for u, r, v in result_edges:
            print(f"    {u} --{r}--> {v}")
        
        print(f"\n  📊 统计:")
        print(f"    原始关系数: {len(keyword_edges)}")
        print(f"    最终关系数: {len(result_edges)}")
        print(f"    keyword_filter_relations_updated: {len(keyword_edges) - len(result_edges)}")
        
        self.print_step("为什么单独处理？")
        
        print("\n  1. 语义重要性:")
        print("     keyword_filter_by 用于关键词消歧和精确检索")
        print("     错误处理会影响检索准确性")
        
        print("\n  2. 统计追踪:")
        print("     单独统计便于评估去重对关键词系统的影响")
        
        print("\n  3. 可扩展性:")
        print("     未来可能需要特殊处理逻辑")
        print("     例如: 关键词权重调整、频率更新等")


def main():
    """主函数"""
    visualizer = DedupVisualizer()
    
    print("\n" + "🎯" * 35)
    print("    Tail去重应用 - 详细处理过程可视化")
    print("🎯" * 35)
    
    print("\n本脚本将演示四个核心功能的处理过程:")
    print("  1. 三元组（Edges）去重")
    print("  2. 社区（Communities）成员去重")
    print("  3. keyword_filter_by 特殊关系处理")
    print("  4. 自动去重 - 避免创建重复边")
    
    # 演示各个功能
    visualizer.demonstrate_edge_dedup()
    visualizer.demonstrate_community_dedup()
    visualizer.demonstrate_keyword_filter_by()
    visualizer.demonstrate_edge_existence_check()
    
    # 总结
    print("\n" + "=" * 70)
    print("  💡 核心要点总结")
    print("=" * 70)
    
    print("\n1. 代表节点选择:")
    print("   - 使用cluster的最后一个成员作为代表")
    print("   - 所有成员都映射到这个代表")
    
    print("\n2. 边去重检查:")
    print("   - 必须按 (head, relation, tail) 三元组检查")
    print("   - MultiDiGraph允许多重边（不同relation）")
    
    print("\n3. 社区去重:")
    print("   - 多个成员可能映射到同一个代表")
    print("   - 需要检查代表是否已在社区中")
    
    print("\n4. 批量处理原则:")
    print("   - 先收集所有变更")
    print("   - 再批量应用（先删后加）")
    print("   - 避免遍历时修改图结构")
    
    print("\n5. 安全性:")
    print("   - 代表节点不存在时保持原节点")
    print("   - 输出警告但不中断处理")
    print("   - 记录详细日志便于调试")
    
    print("\n" + "=" * 70)
    print("  ✅ 演示完成！")
    print("=" * 70)
    print("\n查看 TAIL_DEDUP_DETAILED_EXPLANATION.md 了解更多技术细节\n")


if __name__ == "__main__":
    main()
