#!/usr/bin/env python3
"""
检查数据集配置工具
用于检查手动添加的graph文件配置是否正确
"""

import os
import json
import sys

def check_dataset_files(dataset_name):
    """检查数据集相关文件"""
    
    print(f"\n{'='*60}")
    print(f"检查数据集: {dataset_name}")
    print(f"{'='*60}\n")
    
    files_status = {
        'graph': None,
        'chunks': None,
        'corpus': None,
        'cache': None
    }
    
    # 检查 graph 文件
    graph_path = f"output/graphs/{dataset_name}_new.json"
    if os.path.exists(graph_path):
        size = os.path.getsize(graph_path)
        files_status['graph'] = {
            'path': graph_path,
            'size': size,
            'size_mb': f"{size / 1024 / 1024:.2f} MB"
        }
        try:
            with open(graph_path, 'r', encoding='utf-8') as f:
                graph_data = json.load(f)
                if isinstance(graph_data, list):
                    files_status['graph']['nodes'] = '未知（关系列表格式）'
                    files_status['graph']['edges'] = len(graph_data)
                elif isinstance(graph_data, dict):
                    files_status['graph']['nodes'] = len(graph_data.get('nodes', []))
                    files_status['graph']['edges'] = len(graph_data.get('edges', []))
        except Exception as e:
            files_status['graph']['error'] = str(e)
    
    # 检查 chunks 文件
    chunks_path = f"output/chunks/{dataset_name}.txt"
    if os.path.exists(chunks_path):
        size = os.path.getsize(chunks_path)
        files_status['chunks'] = {
            'path': chunks_path,
            'size': size,
            'size_mb': f"{size / 1024 / 1024:.2f} MB"
        }
        try:
            with open(chunks_path, 'r', encoding='utf-8') as f:
                chunk_count = sum(1 for line in f if line.strip() and line.startswith('id:'))
            files_status['chunks']['count'] = chunk_count
        except Exception as e:
            files_status['chunks']['error'] = str(e)
    
    # 检查 corpus 文件
    corpus_path = f"data/uploaded/{dataset_name}/corpus.json"
    if os.path.exists(corpus_path):
        size = os.path.getsize(corpus_path)
        files_status['corpus'] = {
            'path': corpus_path,
            'size': size,
            'size_mb': f"{size / 1024 / 1024:.2f} MB"
        }
        try:
            with open(corpus_path, 'r', encoding='utf-8') as f:
                corpus_data = json.load(f)
                if isinstance(corpus_data, list):
                    files_status['corpus']['count'] = len(corpus_data)
        except Exception as e:
            files_status['corpus']['error'] = str(e)
    
    # 检查 cache 目录
    cache_dir = f"retriever/faiss_cache_new/{dataset_name}"
    if os.path.exists(cache_dir):
        cache_files = os.listdir(cache_dir)
        files_status['cache'] = {
            'path': cache_dir,
            'files': len(cache_files),
            'file_list': cache_files
        }
    
    # 打印结果
    print("📊 文件检查结果:")
    print("-" * 60)
    
    # Graph 文件
    if files_status['graph']:
        print(f"✅ Graph 文件: {files_status['graph']['path']}")
        print(f"   大小: {files_status['graph']['size_mb']}")
        if 'nodes' in files_status['graph']:
            print(f"   节点数: {files_status['graph']['nodes']}")
            print(f"   边数: {files_status['graph']['edges']}")
        if 'error' in files_status['graph']:
            print(f"   ⚠️  解析错误: {files_status['graph']['error']}")
    else:
        print(f"❌ Graph 文件: 不存在")
        print(f"   预期路径: output/graphs/{dataset_name}_new.json")
    
    print()
    
    # Chunks 文件
    if files_status['chunks']:
        print(f"✅ Chunks 文件: {files_status['chunks']['path']}")
        print(f"   大小: {files_status['chunks']['size_mb']}")
        if 'count' in files_status['chunks']:
            print(f"   片段数: {files_status['chunks']['count']}")
        if 'error' in files_status['chunks']:
            print(f"   ⚠️  解析错误: {files_status['chunks']['error']}")
    else:
        print(f"⚠️  Chunks 文件: 不存在（可选）")
        print(f"   预期路径: output/chunks/{dataset_name}.txt")
        print(f"   影响: 无法检索原始文档片段")
    
    print()
    
    # Corpus 文件
    if files_status['corpus']:
        print(f"✅ Corpus 文件: {files_status['corpus']['path']}")
        print(f"   大小: {files_status['corpus']['size_mb']}")
        if 'count' in files_status['corpus']:
            print(f"   文档数: {files_status['corpus']['count']}")
        if 'error' in files_status['corpus']:
            print(f"   ⚠️  解析错误: {files_status['corpus']['error']}")
    else:
        print(f"ℹ️  Corpus 文件: 不存在（可选）")
        print(f"   预期路径: data/uploaded/{dataset_name}/corpus.json")
        print(f"   影响: 无法重新构建图谱")
    
    print()
    
    # Cache 目录
    if files_status['cache']:
        print(f"✅ Cache 目录: {files_status['cache']['path']}")
        print(f"   文件数: {files_status['cache']['files']}")
        print(f"   文件列表: {', '.join(files_status['cache']['file_list'][:5])}")
        if len(files_status['cache']['file_list']) > 5:
            print(f"             ...等{len(files_status['cache']['file_list']) - 5}个文件")
    else:
        print(f"ℹ️  Cache 目录: 不存在（首次查询时自动生成）")
        print(f"   预期路径: retriever/faiss_cache_new/{dataset_name}/")
    
    print()
    print("-" * 60)
    
    # 功能支持情况
    print("\n🔧 功能支持情况:")
    print("-" * 60)
    
    support_status = {
        '图谱可视化': files_status['graph'] is not None,
        '基础问答': files_status['graph'] is not None,
        '完整问答（含原文片段）': files_status['graph'] is not None and files_status['chunks'] is not None,
        '重新构建图谱': files_status['corpus'] is not None,
        '删除数据集': True  # 总是可以删除
    }
    
    for feature, supported in support_status.items():
        status = "✅ 支持" if supported else "❌ 不支持"
        print(f"{status} - {feature}")
    
    # 数据集类型判断
    print("\n📁 数据集类型:")
    print("-" * 60)
    
    if dataset_name == "demo":
        dataset_type = "demo（示例数据集）"
    elif files_status['corpus']:
        dataset_type = "uploaded（完整数据集）"
    else:
        dataset_type = "custom（自定义graph）"
    
    print(f"类型: {dataset_type}")
    
    # 建议
    print("\n💡 建议:")
    print("-" * 60)
    
    if not files_status['graph']:
        print("❌ 缺少graph文件，数据集无法使用！")
        print(f"   请将graph文件拷贝到: output/graphs/{dataset_name}_new.json")
    elif not files_status['chunks']:
        print("⚠️  建议添加chunks文件以获得更好的问答体验")
        print(f"   chunks文件路径: output/chunks/{dataset_name}.txt")
        print("   格式: id: chunk_id\\tChunk: chunk_text")
    elif not files_status['corpus']:
        print("ℹ️  如需支持重新构建功能，可添加corpus文件")
        print(f"   corpus文件路径: data/uploaded/{dataset_name}/corpus.json")
    else:
        print("✅ 数据集配置完整，所有功能均可使用！")
    
    if files_status['cache']:
        print("\nℹ️  检测到索引缓存，查询速度会很快")
    else:
        print("\nℹ️  首次查询时会自动构建索引（约需10-60秒）")
    
    print("\n" + "="*60 + "\n")
    
    return files_status

def list_all_datasets():
    """列出所有可用的数据集"""
    print("\n" + "="*60)
    print("扫描所有数据集")
    print("="*60 + "\n")
    
    datasets = set()
    
    # 扫描 graphs 目录
    graphs_dir = "output/graphs"
    if os.path.exists(graphs_dir):
        for filename in os.listdir(graphs_dir):
            if filename.endswith("_new.json"):
                dataset_name = filename[:-9]
                datasets.add(dataset_name)
    
    # 扫描 uploaded 目录
    uploaded_dir = "data/uploaded"
    if os.path.exists(uploaded_dir):
        for item in os.listdir(uploaded_dir):
            item_path = os.path.join(uploaded_dir, item)
            if os.path.isdir(item_path):
                corpus_path = os.path.join(item_path, "corpus.json")
                if os.path.exists(corpus_path):
                    datasets.add(item)
    
    if not datasets:
        print("❌ 未找到任何数据集")
        print("\n请参考文档添加数据集：")
        print("  - 将graph文件拷贝到: output/graphs/{数据集名称}_new.json")
        return
    
    print(f"找到 {len(datasets)} 个数据集:\n")
    
    for i, dataset in enumerate(sorted(datasets), 1):
        print(f"{i}. {dataset}")
    
    print("\n使用方法:")
    print(f"  python3 {sys.argv[0]} <数据集名称>")
    print(f"\n示例:")
    print(f"  python3 {sys.argv[0]} demo")
    print(f"  python3 {sys.argv[0]} my_custom_graph")
    
    print("\n" + "="*60 + "\n")

def main():
    if len(sys.argv) < 2:
        print("用法:")
        print(f"  python3 {sys.argv[0]} <数据集名称>     # 检查指定数据集")
        print(f"  python3 {sys.argv[0]} --list          # 列出所有数据集")
        print(f"\n示例:")
        print(f"  python3 {sys.argv[0]} demo")
        print(f"  python3 {sys.argv[0]} my_custom_graph")
        print(f"  python3 {sys.argv[0]} --list")
        sys.exit(1)
    
    if sys.argv[1] in ['--list', '-l', 'list']:
        list_all_datasets()
    else:
        dataset_name = sys.argv[1]
        check_dataset_files(dataset_name)

if __name__ == "__main__":
    main()
