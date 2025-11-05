#!/usr/bin/env python3
"""
便捷脚本：导出知识图谱到 Neo4j 格式
Convenience script: Export knowledge graph to Neo4j format

用法 | Usage:
    python3 export_to_neo4j.py [graph_json_path]
    
示例 | Example:
    python3 export_to_neo4j.py output/graphs/demo_new.json
    python3 export_to_neo4j.py  # 默认导出所有图 | Export all graphs by default
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.neo4j_exporter import export_graph_to_neo4j
from utils.logger import logger


def main():
    """Main function to export graphs"""
    
    if len(sys.argv) > 1:
        # 导出指定的图 | Export specified graph
        json_path = sys.argv[1]
        if not os.path.exists(json_path):
            logger.error(f"文件不存在 | File not found: {json_path}")
            sys.exit(1)
        
        logger.info(f"开始导出 | Starting export: {json_path}")
        export_graph_to_neo4j(json_path)
        
    else:
        # 导出所有图 | Export all graphs
        graphs_dir = Path("output/graphs")
        if not graphs_dir.exists():
            logger.error("未找到 output/graphs 目录 | Directory not found: output/graphs")
            sys.exit(1)
        
        json_files = list(graphs_dir.glob("*_new.json"))
        
        if not json_files:
            logger.warning("未找到任何图文件 | No graph files found")
            logger.info("请先构建知识图谱 | Please build knowledge graph first:")
            logger.info("  python3 main.py --construct --dataset demo")
            sys.exit(0)
        
        logger.info(f"找到 {len(json_files)} 个图文件 | Found {len(json_files)} graph files")
        
        for json_file in json_files:
            logger.info(f"\n{'='*60}")
            logger.info(f"正在导出 | Exporting: {json_file.name}")
            logger.info(f"{'='*60}")
            
            try:
                export_graph_to_neo4j(str(json_file))
            except Exception as e:
                logger.error(f"导出失败 | Export failed: {e}")
                continue
    
    logger.info("\n" + "="*60)
    logger.info("✅ 所有导出完成！| All exports completed!")
    logger.info("="*60)
    logger.info("\n📖 查看导入指南 | View import guide:")
    logger.info("   docs/NEO4J_IMPORT_GUIDE.md")
    logger.info("\n🚀 快速导入到 Neo4j | Quick import to Neo4j:")
    logger.info("   1. 启动 Neo4j | Start Neo4j: docker run -p 7474:7474 -p 7687:7687 neo4j")
    logger.info("   2. 打开浏览器 | Open browser: http://localhost:7474")
    logger.info("   3. 复制粘贴 .cypher 文件内容 | Copy-paste .cypher file content")
    logger.info("")


if __name__ == "__main__":
    main()
