"""
简化版链式等价解析 - 不考虑频率，只解决传递闭包问题

核心思想：并查集的 find + union 是必须的最小组合
"""

def resolve_chain_mapping_simple(merge_mapping: dict) -> dict:
    """
    最简化的链式解析方案
    
    Args:
        merge_mapping: {duplicate: canonical} 原始pair-wise映射
        
    Returns:
        resolved_mapping: {duplicate: final_canonical} 解析后的映射
    
    Example:
        输入: {'A': 'B', 'B': 'C', 'D': 'C'}
        输出: {'A': 'C', 'B': 'C', 'D': 'C'}
    """
    parent = {}
    
    def find(x):
        """
        查找x的最终root（代表元）
        带路径压缩优化
        """
        if x not in parent:
            parent[x] = x  # 初始化：自己是自己的parent
        if parent[x] != x:
            parent[x] = find(parent[x])  # 递归查找并压缩路径
        return parent[x]
    
    def union(x, y):
        """
        合并x和y所在的集合
        简化版：不考虑rank优化，直接让y成为x的parent
        """
        root_x = find(x)
        root_y = find(y)
        if root_x != root_y:
            parent[root_x] = root_y  # x的root指向y的root
    
    # 步骤1: 应用所有pair-wise关系，构建并查集
    for duplicate, canonical in merge_mapping.items():
        union(duplicate, canonical)
    
    # 步骤2: 为每个duplicate找到最终的canonical
    resolved_mapping = {}
    for duplicate in merge_mapping.keys():
        final_canonical = find(duplicate)
        if duplicate != final_canonical:
            resolved_mapping[duplicate] = final_canonical
    
    return resolved_mapping


# ============= 测试用例 =============

if __name__ == "__main__":
    print("=" * 60)
    print("测试1: 简单链式")
    print("=" * 60)
    
    mapping1 = {
        'entity_1': 'entity_2',
        'entity_2': 'entity_3',
    }
    
    print(f"输入: {mapping1}")
    result1 = resolve_chain_mapping_simple(mapping1)
    print(f"输出: {result1}")
    print(f"✓ entity_1 最终指向: {result1.get('entity_1')}")
    print()
    
    print("=" * 60)
    print("测试2: 多条链式 + 汇聚")
    print("=" * 60)
    
    mapping2 = {
        'entity_1': 'entity_2',
        'entity_2': 'entity_3',
        'entity_4': 'entity_3',
        'entity_5': 'entity_6',
        'entity_6': 'entity_3',
    }
    
    print(f"输入: {mapping2}")
    print("  entity_1 -> entity_2")
    print("  entity_2 -> entity_3")
    print("  entity_4 -> entity_3")
    print("  entity_5 -> entity_6")
    print("  entity_6 -> entity_3")
    
    result2 = resolve_chain_mapping_simple(mapping2)
    print(f"\n输出: {result2}")
    
    for dup, can in sorted(result2.items()):
        print(f"  {dup} -> {can}")
    
    print("\n✓ 所有节点都正确指向最终root: entity_3")
    print()
    
    print("=" * 60)
    print("测试3: 复杂链式")
    print("=" * 60)
    
    mapping3 = {
        'A': 'B',
        'B': 'C',
        'C': 'D',
        'D': 'E',
        'F': 'D',
    }
    
    print(f"输入: {mapping3}")
    print("  链式: A -> B -> C -> D -> E")
    print("  分支: F -> D -> E")
    
    result3 = resolve_chain_mapping_simple(mapping3)
    print(f"\n输出: {result3}")
    
    for dup, can in sorted(result3.items()):
        print(f"  {dup} -> {can}")
    
    print("\n✓ 所有节点都正确指向最终root: E")
    print()
    
    print("=" * 60)
    print("关键结论")
    print("=" * 60)
    print("1. find() 函数本身不够！")
    print("   - 必须先用 union() 构建parent关系")
    print("   - 然后用 find() 查找最终root")
    print()
    print("2. 最小组合：")
    print("   - find(): 查找root + 路径压缩")
    print("   - union(): 建立集合关系")
    print()
    print("3. 可选优化：")
    print("   - rank优化: 按树高度合并（避免树退化）")
    print("   - 频率优先: 高频entity作为root（语义更好）")
