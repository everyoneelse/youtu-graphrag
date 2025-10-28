#!/usr/bin/env python3
"""
检查 NV-Embed-v2 的模型配置信息（不下载完整模型）
"""

import os
import sys
import json

def check_model_config():
    """检查模型配置"""
    print("=" * 70)
    print("检查 NV-Embed-v2 模型配置")
    print("=" * 70)
    
    try:
        from huggingface_hub import hf_hub_download, model_info
        
        # 设置镜像（如果配置了）
        if 'HF_ENDPOINT' in os.environ:
            print(f"使用 HF 镜像: {os.environ['HF_ENDPOINT']}")
        
        print("\n正在获取模型信息...")
        
        # 获取模型信息
        info = model_info("nvidia/NV-Embed-v2")
        
        print(f"\n模型 ID: {info.id}")
        print(f"模型作者: {info.author}")
        print(f"下载次数: {info.downloads:,}")
        print(f"点赞数: {info.likes:,}")
        
        if hasattr(info, 'pipeline_tag'):
            print(f"Pipeline Tag: {info.pipeline_tag}")
        
        if hasattr(info, 'tags'):
            print(f"\n模型标签:")
            for tag in info.tags[:10]:
                print(f"  - {tag}")
        
        # 尝试获取 config.json
        print("\n正在下载 config.json...")
        config_path = hf_hub_download(
            repo_id="nvidia/NV-Embed-v2",
            filename="config.json",
            cache_dir=".cache"
        )
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        print("\n模型配置:")
        print(f"  架构: {config.get('architectures', 'Unknown')}")
        print(f"  模型类型: {config.get('model_type', 'Unknown')}")
        print(f"  隐藏层大小: {config.get('hidden_size', 'Unknown')}")
        print(f"  层数: {config.get('num_hidden_layers', 'Unknown')}")
        print(f"  注意力头数: {config.get('num_attention_heads', 'Unknown')}")
        print(f"  最大位置编码: {config.get('max_position_embeddings', 'Unknown')}")
        
        # 检查是否需要 trust_remote_code
        auto_map = config.get('auto_map', {})
        if auto_map:
            print(f"\n⚠️  需要 trust_remote_code=True")
            print(f"  自定义类: {list(auto_map.keys())}")
        
        # 检查 sentence-transformers 兼容性
        print("\n" + "=" * 70)
        print("sentence-transformers 兼容性分析")
        print("=" * 70)
        
        # 尝试下载 sentence-transformers 相关文件
        try:
            # sentence-transformers 模型通常包含这些文件
            st_config_path = hf_hub_download(
                repo_id="nvidia/NV-Embed-v2",
                filename="sentence_bert_config.json",
                cache_dir=".cache"
            )
            print("✓ 找到 sentence_bert_config.json")
            
            with open(st_config_path, 'r') as f:
                st_config = json.load(f)
            print(f"  最大序列长度: {st_config.get('max_seq_length', 'Unknown')}")
            
            has_st_support = True
            
        except Exception as e:
            print(f"✗ 未找到 sentence_bert_config.json")
            print(f"  这表明模型可能不直接支持 sentence-transformers")
            has_st_support = False
        
        # 总结
        print("\n" + "=" * 70)
        print("结论")
        print("=" * 70)
        
        if has_st_support:
            print("✓ NV-Embed-v2 支持 sentence-transformers")
            print("  可以直接使用: SentenceTransformer('nvidia/NV-Embed-v2')")
            print("\n修改配置文件:")
            print("  embedding_model: nvidia/NV-Embed-v2")
        else:
            print("✗ NV-Embed-v2 不直接支持 sentence-transformers")
            print("  需要使用 transformers.AutoModel 手动加载")
            print("\n解决方案:")
            print("  1. 修改代码以支持自定义 embedding 加载器")
            print("  2. 或者包装 NV-Embed-v2 为 sentence-transformers 兼容格式")
            print("  3. 或者使用其他兼容的模型")
        
        # 推荐的替代模型
        print("\n" + "=" * 70)
        print("如果不兼容，推荐的替代高性能模型:")
        print("=" * 70)
        print("  1. BAAI/bge-large-en-v1.5 (1024维)")
        print("  2. BAAI/bge-base-en-v1.5 (768维)")
        print("  3. intfloat/e5-large-v2 (1024维)")
        print("  4. sentence-transformers/all-mpnet-base-v2 (768维)")
        print("\n这些模型都原生支持 sentence-transformers")
        
        return True
        
    except Exception as e:
        print(f"\n✗ 错误: {type(e).__name__}: {e}")
        print("\n可能的原因:")
        print("  1. 网络连接问题")
        print("  2. 需要设置 HF_ENDPOINT 镜像")
        print("  3. huggingface_hub 未安装")
        
        return False


def check_sentence_transformers():
    """检查 sentence-transformers 版本"""
    print("\n" + "=" * 70)
    print("检查当前环境")
    print("=" * 70)
    
    try:
        import sentence_transformers
        print(f"✓ sentence-transformers 版本: {sentence_transformers.__version__}")
        
        import transformers
        print(f"✓ transformers 版本: {transformers.__version__}")
        
        import torch
        print(f"✓ torch 版本: {torch.__version__}")
        print(f"  CUDA 可用: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"  GPU 数量: {torch.cuda.device_count()}")
            print(f"  GPU 名称: {torch.cuda.get_device_name(0)}")
        
    except ImportError as e:
        print(f"✗ 缺少依赖: {e}")


def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("NV-Embed-v2 兼容性检查工具")
    print("=" * 70)
    
    # 检查环境
    check_sentence_transformers()
    
    # 检查模型配置
    success = check_model_config()
    
    print("\n" + "=" * 70)
    print("检查完成")
    print("=" * 70)
    
    if not success:
        print("\n提示: 如果在中国大陆，请设置环境变量:")
        print("  export HF_ENDPOINT=https://hf-mirror.com")


if __name__ == "__main__":
    main()
