#!/usr/bin/env python3
"""
测试 NV-Embed-v2 与 sentence-transformers 的兼容性
"""

import os
import sys

def test_sentence_transformers_loading():
    """测试通过 sentence-transformers 直接加载"""
    print("=" * 60)
    print("测试 1: 通过 sentence-transformers 直接加载 NV-Embed-v2")
    print("=" * 60)
    
    try:
        from sentence_transformers import SentenceTransformer
        print("✓ sentence-transformers 已安装")
        
        # 尝试加载 NV-Embed-v2
        print("\n尝试加载 nvidia/NV-Embed-v2...")
        model = SentenceTransformer('nvidia/NV-Embed-v2')
        
        # 测试编码
        test_text = "This is a test sentence."
        embedding = model.encode(test_text)
        
        print(f"✓ 成功加载并编码!")
        print(f"  Embedding 维度: {len(embedding)}")
        print(f"  Embedding 前5个值: {embedding[:5]}")
        return True, "sentence-transformers"
        
    except Exception as e:
        print(f"✗ 失败: {type(e).__name__}: {e}")
        return False, str(e)


def test_transformers_loading():
    """测试通过 transformers 加载（NV-Embed-v2 推荐方式）"""
    print("\n" + "=" * 60)
    print("测试 2: 通过 transformers 加载 NV-Embed-v2（推荐方式）")
    print("=" * 60)
    
    try:
        import torch
        from transformers import AutoTokenizer, AutoModel
        print("✓ transformers 已安装")
        
        print("\n尝试加载 nvidia/NV-Embed-v2...")
        tokenizer = AutoTokenizer.from_pretrained('nvidia/NV-Embed-v2')
        model = AutoModel.from_pretrained('nvidia/NV-Embed-v2', trust_remote_code=True)
        
        print("✓ 模型加载成功")
        
        # 测试编码
        test_text = "This is a test sentence."
        print(f"\n测试文本: '{test_text}'")
        
        # NV-Embed-v2 需要特殊的前缀处理
        inputs = tokenizer(test_text, return_tensors='pt', padding=True, truncation=True)
        
        with torch.no_grad():
            outputs = model(**inputs)
            # 通常使用 last_hidden_state 的 mean pooling
            embeddings = outputs.last_hidden_state.mean(dim=1)
        
        print(f"✓ 成功编码!")
        print(f"  Embedding 维度: {embeddings.shape}")
        print(f"  Embedding 前5个值: {embeddings[0][:5]}")
        
        return True, "transformers"
        
    except Exception as e:
        print(f"✗ 失败: {type(e).__name__}: {e}")
        return False, str(e)


def check_model_info():
    """获取模型信息"""
    print("\n" + "=" * 60)
    print("NV-Embed-v2 模型信息")
    print("=" * 60)
    
    print("""
模型名称: nvidia/NV-Embed-v2
开发者: NVIDIA
HuggingFace: https://huggingface.co/nvidia/NV-Embed-v2

特点:
- 高性能 embedding 模型
- 支持长文本（最长 32,768 tokens）
- 在多个基准测试中表现优异
- 模型大小: ~7B 参数

重要提示:
1. NV-Embed-v2 使用了自定义的模型架构
2. 需要 trust_remote_code=True 参数
3. 可能需要较大的 GPU 内存（推荐 16GB+）
4. 推荐使用 transformers 库而非 sentence-transformers
    """)


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("NV-Embed-v2 兼容性测试")
    print("=" * 60)
    
    # 设置镜像（如果需要）
    if 'HF_ENDPOINT' not in os.environ:
        print("\n提示: 如果下载慢，可以设置 HF_ENDPOINT=https://hf-mirror.com")
    
    # 测试 1: sentence-transformers
    success1, result1 = test_sentence_transformers_loading()
    
    # 测试 2: transformers
    success2, result2 = test_transformers_loading()
    
    # 显示模型信息
    check_model_info()
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    if success1:
        print("✓ sentence-transformers: 兼容")
    else:
        print(f"✗ sentence-transformers: 不兼容")
        print(f"  原因: {result1}")
    
    if success2:
        print("✓ transformers: 兼容（推荐）")
    else:
        print(f"✗ transformers: 不兼容")
        print(f"  原因: {result2}")
    
    print("\n建议:")
    if success1:
        print("- 可以直接使用 SentenceTransformer('nvidia/NV-Embed-v2')")
        print("- 修改配置文件即可")
    elif success2:
        print("- 需要自定义 embedding 加载器")
        print("- 使用 transformers.AutoModel + 自定义编码逻辑")
        print("- 无法直接通过配置文件切换")
    else:
        print("- 可能需要安装额外依赖")
        print("- 检查网络连接和 HuggingFace 访问")


if __name__ == "__main__":
    main()
