#!/usr/bin/env python3
"""
测试 Neo4j 导出功能
Test Neo4j Export Functionality

验证导出的 Cypher 脚本和 CSV 文件是否正确
Verify that exported Cypher scripts and CSV files are correct
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from utils.logger import logger


def test_json_structure(json_path: str):
    """测试 JSON 文件结构 | Test JSON file structure"""
    logger.info(f"📋 测试 JSON 文件: {json_path}")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 验证关系数量 | Verify relationship count
    assert len(data) > 0, "JSON 文件为空"
    logger.info(f"✅ 关系数量: {len(data)}")
    
    # 统计唯一节点 | Count unique nodes
    unique_nodes = set()
    node_types = {}
    
    for rel in data:
        assert 'start_node' in rel, "缺少 start_node"
        assert 'end_node' in rel, "缺少 end_node"
        assert 'relation' in rel, "缺少 relation"
        
        for node_key in ['start_node', 'end_node']:
            node = rel[node_key]
            assert 'label' in node, f"{node_key} 缺少 label"
            assert 'properties' in node, f"{node_key} 缺少 properties"
            assert 'name' in node['properties'], f"{node_key} 缺少 name 属性"
            
            label = node['label']
            name = node['properties']['name']
            unique_nodes.add((label, name))
            node_types[label] = node_types.get(label, 0) + 1
    
    logger.info(f"✅ 唯一节点数: {len(unique_nodes)}")
    
    # 验证四层结构 | Verify four-level structure
    expected_labels = {'attribute', 'entity', 'keyword', 'community'}
    actual_labels = set(node_types.keys())
    
    logger.info(f"📊 节点类型分布:")
    for label in expected_labels:
        count = len([n for l, n in unique_nodes if l == label])
        logger.info(f"   Level {_get_level(label)} - {label}: {count}")
    
    # 验证包含所有四层 | Verify all four levels exist
    if not expected_labels.issubset(actual_labels):
        logger.warning(f"⚠️  缺少某些层级: {expected_labels - actual_labels}")
    else:
        logger.info(f"✅ 四层结构完整 (attribute, entity, keyword, community)")
    
    return len(unique_nodes), len(data)


def test_cypher_export(cypher_path: str):
    """测试 Cypher 脚本 | Test Cypher script"""
    logger.info(f"\n📋 测试 Cypher 脚本: {cypher_path}")
    
    with open(cypher_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 验证关键语句 | Verify key statements
    assert 'CREATE CONSTRAINT' in content, "缺少约束创建语句"
    assert 'MERGE (:Attribute' in content, "缺少 Attribute 节点"
    assert 'MERGE (:Entity' in content, "缺少 Entity 节点"
    assert 'MERGE (:Keyword' in content, "缺少 Keyword 节点"
    assert 'MERGE (:Community' in content, "缺少 Community 节点"
    assert 'MATCH' in content and 'MERGE' in content, "缺少关系创建语句"
    
    # 统计语句数量 | Count statements
    merge_count = content.count('MERGE (:')
    match_count = content.count('MATCH (')
    
    logger.info(f"✅ MERGE 节点语句: {merge_count}")
    logger.info(f"✅ MATCH 关系语句: {match_count}")
    
    # 验证文件大小 | Verify file size
    file_size = Path(cypher_path).stat().st_size
    logger.info(f"✅ 文件大小: {file_size / 1024:.1f} KB")
    
    # 验证四层注释 | Verify four-level comments
    content_lower = content.lower()
    assert 'level 1' in content_lower and 'attribute' in content_lower, "缺少 Level 1 注释"
    assert 'level 2' in content_lower and 'entity' in content_lower, "缺少 Level 2 注释"
    assert 'level 3' in content_lower and 'keyword' in content_lower, "缺少 Level 3 注释"
    assert 'level 4' in content_lower and 'community' in content_lower, "缺少 Level 4 注释"
    logger.info(f"✅ 四层结构注释完整")
    
    return merge_count, match_count


def test_csv_export(csv_dir: str):
    """测试 CSV 导出 | Test CSV export"""
    logger.info(f"\n📋 测试 CSV 文件: {csv_dir}")
    
    csv_path = Path(csv_dir)
    assert csv_path.exists(), f"CSV 目录不存在: {csv_dir}"
    
    # 验证必需文件 | Verify required files
    required_files = [
        'entity_nodes.csv',
        'attribute_nodes.csv', 
        'keyword_nodes.csv',
        'community_nodes.csv',
        'relationships.csv',
        'neo4j_import.sh'
    ]
    
    for filename in required_files:
        file_path = csv_path / filename
        assert file_path.exists(), f"缺少文件: {filename}"
        logger.info(f"✅ {filename} 存在")
    
    # 验证导入脚本可执行 | Verify import script is executable
    import_script = csv_path / 'neo4j_import.sh'
    import stat
    is_executable = bool(import_script.stat().st_mode & stat.S_IXUSR)
    assert is_executable, "导入脚本不可执行"
    logger.info(f"✅ neo4j_import.sh 可执行")
    
    # 统计 CSV 行数 | Count CSV rows
    total_nodes = 0
    for node_file in ['entity_nodes.csv', 'attribute_nodes.csv', 'keyword_nodes.csv', 'community_nodes.csv']:
        with open(csv_path / node_file, 'r') as f:
            lines = len(f.readlines()) - 1  # 减去表头
            total_nodes += lines
            logger.info(f"   {node_file}: {lines} 行")
    
    with open(csv_path / 'relationships.csv', 'r') as f:
        rel_lines = len(f.readlines()) - 1
        logger.info(f"   relationships.csv: {rel_lines} 行")
    
    logger.info(f"✅ 总节点数: {total_nodes}")
    
    return total_nodes, rel_lines


def _get_level(label: str) -> int:
    """获取层级编号 | Get level number"""
    level_map = {
        'attribute': 1,
        'entity': 2,
        'keyword': 3,
        'community': 4
    }
    return level_map.get(label.lower(), 0)


def main():
    """主测试函数 | Main test function"""
    logger.info("="*60)
    logger.info("🧪 开始测试 Neo4j 导出功能")
    logger.info("   Testing Neo4j Export Functionality")
    logger.info("="*60)
    
    # 测试路径 | Test paths
    json_path = "output/graphs/demo_new.json"
    cypher_path = "output/graphs/demo_new_neo4j.cypher"
    csv_dir = "output/graphs/demo_new_neo4j_csv"
    
    try:
        # 测试 1: JSON 结构 | Test 1: JSON structure
        node_count, rel_count = test_json_structure(json_path)
        
        # 测试 2: Cypher 导出 | Test 2: Cypher export
        merge_count, match_count = test_cypher_export(cypher_path)
        
        # 测试 3: CSV 导出 | Test 3: CSV export
        csv_nodes, csv_rels = test_csv_export(csv_dir)
        
        # 验证数据一致性 | Verify data consistency
        logger.info("\n" + "="*60)
        logger.info("📊 数据一致性验证 | Data Consistency Verification")
        logger.info("="*60)
        
        logger.info(f"JSON 节点数: {node_count}")
        logger.info(f"CSV 节点数: {csv_nodes}")
        logger.info(f"Cypher MERGE 数: {merge_count}")
        
        logger.info(f"\nJSON 关系数: {rel_count}")
        logger.info(f"CSV 关系数: {csv_rels}")
        
        # 允许一些差异（去重等）| Allow some differences (deduplication, etc.)
        assert abs(node_count - csv_nodes) <= 5, "节点数差异过大"
        assert abs(rel_count - csv_rels) <= 5, "关系数差异过大"
        
        logger.info("\n" + "="*60)
        logger.info("✅ 所有测试通过！| All tests passed!")
        logger.info("="*60)
        logger.info("\n📖 下一步:")
        logger.info("   1. 查看导入指南: docs/NEO4J_IMPORT_GUIDE.md")
        logger.info("   2. 快速开始: docs/NEO4J_QUICKSTART.md")
        logger.info("   3. 导入到 Neo4j:")
        logger.info("      docker run -d -p 7474:7474 -p 7687:7687 neo4j")
        logger.info("      cat output/graphs/demo_new_neo4j.cypher | \\")
        logger.info("        docker exec -i neo4j cypher-shell -u neo4j -p password")
        logger.info("")
        
        return 0
        
    except AssertionError as e:
        logger.error(f"\n❌ 测试失败: {e}")
        return 1
    except Exception as e:
        logger.error(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
