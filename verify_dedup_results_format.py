#!/usr/bin/env python3
"""
验证dedup_results格式是否符合要求

这个脚本检查你的去重结果是否可以直接用于apply_tail_dedup_results.py
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any


class DedupFormatValidator:
    """去重结果格式验证器"""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.info = []
    
    def validate_file(self, file_path: str) -> bool:
        """验证文件格式"""
        path = Path(file_path)
        
        # 检查文件存在
        if not path.exists():
            self.errors.append(f"文件不存在: {file_path}")
            return False
        
        # 加载JSON
        try:
            with path.open('r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            self.errors.append(f"JSON格式错误: {e}")
            return False
        except Exception as e:
            self.errors.append(f"加载文件失败: {e}")
            return False
        
        # 验证数据结构
        return self.validate_structure(data)
    
    def validate_structure(self, data: Any) -> bool:
        """验证数据结构"""
        # 必须是列表
        if not isinstance(data, list):
            self.errors.append("根元素必须是列表（数组）")
            return False
        
        if len(data) == 0:
            self.warnings.append("去重结果为空列表")
            return True
        
        self.info.append(f"发现 {len(data)} 个去重组")
        
        # 验证每个组
        all_valid = True
        for i, group in enumerate(data):
            if not self.validate_group(group, i):
                all_valid = False
        
        return all_valid
    
    def validate_group(self, group: Dict, index: int) -> bool:
        """验证单个去重组"""
        group_id = f"组{index+1}"
        valid = True
        
        # 检查必需字段
        required_fields = ['head_node', 'relation', 'dedup_results']
        for field in required_fields:
            if field not in group:
                self.errors.append(f"{group_id}: 缺少必需字段 '{field}'")
                valid = False
        
        if not valid:
            return False
        
        # 验证 head_node
        if not self.validate_node(group['head_node'], f"{group_id}.head_node"):
            valid = False
        
        # 验证 relation
        if not isinstance(group['relation'], str):
            self.errors.append(f"{group_id}: 'relation' 必须是字符串")
            valid = False
        
        # 验证 dedup_results
        if not isinstance(group['dedup_results'], dict):
            self.errors.append(f"{group_id}: 'dedup_results' 必须是字典")
            valid = False
        else:
            if len(group['dedup_results']) == 0:
                self.warnings.append(f"{group_id}: 'dedup_results' 为空")
            else:
                self.info.append(f"{group_id}: {len(group['dedup_results'])} 个cluster")
                
                # 验证每个cluster
                for cluster_name, cluster_data in group['dedup_results'].items():
                    if not self.validate_cluster(cluster_data, f"{group_id}.{cluster_name}"):
                        valid = False
        
        return valid
    
    def validate_node(self, node: Dict, path: str) -> bool:
        """验证节点结构"""
        if not isinstance(node, dict):
            self.errors.append(f"{path}: 必须是字典")
            return False
        
        # 检查必需字段
        if 'label' not in node:
            self.errors.append(f"{path}: 缺少 'label' 字段")
            return False
        
        if 'properties' not in node:
            self.errors.append(f"{path}: 缺少 'properties' 字段")
            return False
        
        if not isinstance(node['properties'], dict):
            self.errors.append(f"{path}.properties: 必须是字典")
            return False
        
        # 检查properties中的name
        if 'name' not in node['properties']:
            self.errors.append(f"{path}.properties: 缺少 'name' 字段")
            return False
        
        return True
    
    def validate_cluster(self, cluster: Dict, path: str) -> bool:
        """验证cluster结构"""
        if not isinstance(cluster, dict):
            self.errors.append(f"{path}: 必须是字典")
            return False
        
        # 检查member字段
        if 'member' not in cluster:
            self.errors.append(f"{path}: 缺少 'member' 字段")
            return False
        
        if not isinstance(cluster['member'], list):
            self.errors.append(f"{path}.member: 必须是列表")
            return False
        
        members = cluster['member']
        if len(members) == 0:
            self.warnings.append(f"{path}: 'member' 列表为空")
            return True
        
        if len(members) == 1:
            self.warnings.append(f"{path}: 只有1个成员，不需要去重")
        
        # 验证成员格式
        for i, member in enumerate(members):
            if not isinstance(member, str):
                self.errors.append(f"{path}.member[{i}]: 必须是字符串")
                return False
            
            # 检查格式: "name (chunk id: xxx) [label]"
            if not self.validate_member_format(member, f"{path}.member[{i}]"):
                return False
        
        # 检查代表节点（最后一个成员）
        representative = members[-1]
        self.info.append(f"{path}: 代表节点 = {representative}")
        
        return True
    
    def validate_member_format(self, member: str, path: str) -> bool:
        """验证成员标识符格式"""
        # 格式: "name (chunk id: xxx) [label]"
        
        # 检查是否包含必要部分
        if '(chunk id:' not in member:
            self.warnings.append(f"{path}: 缺少 'chunk id' 部分，可能导致匹配失败")
            return True  # 警告但不算错误
        
        if '[' not in member or ']' not in member:
            self.errors.append(f"{path}: 缺少 '[label]' 部分")
            return False
        
        # 提取各部分
        try:
            # 提取label
            label_start = member.rfind('[')
            label_end = member.rfind(']')
            if label_start == -1 or label_end == -1 or label_start >= label_end:
                self.errors.append(f"{path}: label格式错误")
                return False
            
            label = member[label_start+1:label_end].strip()
            if not label:
                self.errors.append(f"{path}: label为空")
                return False
            
            # 提取chunk id
            chunk_start = member.find('(chunk id:')
            chunk_end = member.find(')', chunk_start)
            if chunk_start == -1 or chunk_end == -1:
                self.warnings.append(f"{path}: chunk id格式异常")
                return True
            
            chunk_id = member[chunk_start+10:chunk_end].strip()
            if not chunk_id:
                self.warnings.append(f"{path}: chunk id为空")
            
            # 提取name
            name = member[:chunk_start].strip()
            if not name:
                self.errors.append(f"{path}: name为空")
                return False
            
        except Exception as e:
            self.errors.append(f"{path}: 解析失败 - {e}")
            return False
        
        return True
    
    def print_report(self):
        """打印验证报告"""
        print("\n" + "="*70)
        print("  去重结果格式验证报告")
        print("="*70)
        
        # 信息
        if self.info:
            print("\n📊 信息:")
            for msg in self.info:
                print(f"  ℹ️  {msg}")
        
        # 警告
        if self.warnings:
            print("\n⚠️  警告:")
            for msg in self.warnings:
                print(f"  ⚠️  {msg}")
        
        # 错误
        if self.errors:
            print("\n❌ 错误:")
            for msg in self.errors:
                print(f"  ❌ {msg}")
        
        # 总结
        print("\n" + "="*70)
        if self.errors:
            print("❌ 验证失败！请修复上述错误。")
            return False
        elif self.warnings:
            print("⚠️  验证通过，但有警告。建议检查后再使用。")
            return True
        else:
            print("✅ 验证通过！格式完全符合要求。")
            return True
        print("="*70 + "\n")


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python3 verify_dedup_results_format.py <dedup_results.json>")
        print("\n示例:")
        print("  python3 verify_dedup_results_format.py your_dedup_results.json")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    print(f"验证文件: {file_path}")
    
    validator = DedupFormatValidator()
    valid = validator.validate_file(file_path)
    validator.print_report()
    
    if valid:
        print("\n💡 下一步:")
        print("  运行以下命令应用去重结果:")
        print(f"\n  python3 apply_tail_dedup_results.py \\")
        print(f"      --graph output/graphs/original.json \\")
        print(f"      --dedup-results {file_path} \\")
        print(f"      --output output/graphs/deduped.json\n")
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
