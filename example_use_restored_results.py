#!/usr/bin/env python3
"""
示例：如何使用还原的semantic_results跳过LLM调用

这个脚本展示了如何修改triple_deduplicate_semantic以使用缓存的结果
"""

import pickle
import json
from typing import List, Dict, Any


class ExampleUsage:
    """展示如何使用还原的semantic_results"""
    
    def __init__(self, restored_results_file: str = None):
        """
        Args:
            restored_results_file: 还原的semantic_results pickle文件路径
        """
        self.restored_results_file = restored_results_file
        self.cached_semantic_results = None
        
        if restored_results_file:
            print(f"Loading cached semantic_results from: {restored_results_file}")
            with open(restored_results_file, 'rb') as f:
                self.cached_semantic_results = pickle.load(f)
            print(f"✅ Loaded {len(self.cached_semantic_results)} cached results")
    
    def triple_deduplicate_semantic_modified(self):
        """
        修改后的triple_deduplicate_semantic，支持使用缓存的semantic_results
        
        这是原始方法的简化版本，展示关键修改点
        """
        # ... 前面的代码（PHASE 1, PHASE 2）保持不变 ...
        
        # ================================================================
        # PHASE 3: Batch collect and process semantic dedup prompts
        # ================================================================
        print("Collecting all semantic dedup prompts...")
        semantic_prompts = []
        
        # 收集所有prompts（即使使用缓存也需要这一步来建立索引）
        for group_idx, group_data in enumerate(dedup_groups):
            prompts = self._collect_semantic_dedup_prompts(group_data)
            for prompt_data in prompts:
                prompt_data['metadata']['group_idx'] = group_idx
                semantic_prompts.append(prompt_data)
        
        print(f"Collected {len(semantic_prompts)} semantic dedup prompts")
        
        # ============================================================
        # 🔥 关键修改：使用缓存的semantic_results或调用LLM
        # ============================================================
        if self.cached_semantic_results is not None:
            print("🚀 Using cached semantic_results, skipping LLM calls!")
            print(f"💰 Saving tokens for {len(semantic_prompts)} prompts")
            semantic_results = self.cached_semantic_results
        else:
            print("Calling LLM for semantic deduplication...")
            semantic_results = self._concurrent_llm_calls(semantic_prompts)
        
        # Parse semantic dedup results and update group_data
        print("Parsing semantic dedup results...")
        self._parse_semantic_dedup_results(dedup_groups, semantic_results)
        
        # ================================================================
        # PHASE 4: Build final deduplicated edges
        # ================================================================
        # ... 后面的代码保持不变 ...


def demo_usage():
    """演示如何使用"""
    
    print("=" * 70)
    print("方案1：在代码中直接加载缓存的结果")
    print("=" * 70)
    print("""
# 在kt_gen.py的triple_deduplicate_semantic方法中：

def triple_deduplicate_semantic(self, use_cached_results: str = None):
    '''
    Args:
        use_cached_results: 缓存的semantic_results pickle文件路径
    '''
    config = self._get_semantic_dedup_config()
    save_intermediate = config and getattr(config, "save_intermediate_results", False)
    if save_intermediate:
        self._edge_dedup_results = []
    
    # ... PHASE 1 & 2 代码 ...
    
    # PHASE 3: 收集prompts
    semantic_prompts = []
    for group_idx, group_data in enumerate(dedup_groups):
        prompts = self._collect_semantic_dedup_prompts(group_data)
        for prompt_data in prompts:
            prompt_data['metadata']['group_idx'] = group_idx
            semantic_prompts.append(prompt_data)
    
    # 🔥 使用缓存或调用LLM
    if use_cached_results:
        logger.info(f"Using cached results from: {use_cached_results}")
        import pickle
        with open(use_cached_results, 'rb') as f:
            semantic_results = pickle.load(f)
        logger.info(f"Loaded {len(semantic_results)} cached results")
    else:
        logger.info(f"Collected {len(semantic_prompts)} semantic dedup prompts, processing concurrently...")
        semantic_results = self._concurrent_llm_calls(semantic_prompts)
    
    # Parse结果
    self._parse_semantic_dedup_results(dedup_groups, semantic_results)
    
    # ... PHASE 4 代码 ...
    """)
    
    print("\n" + "=" * 70)
    print("方案2：通过配置文件指定缓存")
    print("=" * 70)
    print("""
# 在config/semantic_dedup.yaml中添加：

semantic_dedup:
  # ... 其他配置 ...
  
  # 使用缓存的semantic_results（如果指定，将跳过LLM调用）
  cached_results_path: "output/dedup_intermediate/demo_semantic_results_20241023_123456.pkl"
    """)
    
    print("\n" + "=" * 70)
    print("方案3：命令行参数")
    print("=" * 70)
    print("""
# 修改main.py支持命令行参数：

parser.add_argument(
    '--use-cached-semantic-results',
    type=str,
    default=None,
    help='Path to cached semantic_results pickle file to skip LLM calls'
)

# 然后在构建KnowledgeGraph时传入：
kg = KnowledgeGraph(
    dataset_name=args.dataset,
    cached_semantic_results=args.use_cached_semantic_results
)
    """)
    
    print("\n" + "=" * 70)
    print("完整工作流程")
    print("=" * 70)
    print("""
步骤1：首次运行，保存中间结果
---------------------------------
# 设置配置文件中的 save_intermediate_results: true
python main.py --dataset demo --config config/semantic_dedup.yaml

# 输出：output/dedup_intermediate/demo_edge_dedup_20241023_123456.json


步骤2：从中间结果还原semantic_results
------------------------------------
python restore_semantic_results.py \\
    output/dedup_intermediate/demo_edge_dedup_20241023_123456.json

# 输出：
#   output/dedup_intermediate/demo_semantic_results_20241023_123456.pkl
#   output/dedup_intermediate/demo_semantic_results_20241023_123456.json


步骤3：使用缓存的结果重新运行（无需调用LLM）
------------------------------------------
python main.py --dataset demo \\
    --use-cached-semantic-results \\
    output/dedup_intermediate/demo_semantic_results_20241023_123456.pkl

# 🚀 这次运行会跳过所有semantic dedup的LLM调用！
# 💰 节省大量tokens成本！
    """)


def validate_restored_results(intermediate_file: str, restored_file: str):
    """验证还原的结果是否正确"""
    print("\n" + "=" * 70)
    print("验证还原的结果")
    print("=" * 70)
    
    # 加载中间结果
    with open(intermediate_file, 'r', encoding='utf-8') as f:
        intermediate = json.load(f)
    
    # 加载还原的结果
    with open(restored_file, 'rb') as f:
        restored = pickle.load(f)
    
    print(f"\n中间结果文件：{intermediate_file}")
    print(f"还原结果文件：{restored_file}")
    
    # 统计信息
    if intermediate.get('dedup_type') == 'edge_deduplication':
        total_llm_groups = sum(len(t.get('llm_groups', [])) for t in intermediate['triples'])
        print(f"\n中间结果中的LLM调用次数：{total_llm_groups}")
        print(f"还原的semantic_results条目数：{len(restored)}")
        
        if total_llm_groups == len(restored):
            print("✅ 数量匹配！")
        else:
            print("⚠️  数量不匹配，可能存在问题")
    
    # 检查第一个结果的格式
    if restored:
        print("\n第一个还原结果的格式：")
        first = restored[0]
        print(f"  - type: {first.get('type')}")
        print(f"  - metadata keys: {list(first.get('metadata', {}).keys())}")
        print(f"  - has response: {'response' in first}")
        print(f"  - has error: {'error' in first}")
        
        # 尝试解析response
        try:
            response_data = json.loads(first['response'])
            print(f"  - response is valid JSON: ✅")
            print(f"  - response has groups: {'groups' in response_data}")
            if 'groups' in response_data:
                print(f"  - number of groups: {len(response_data['groups'])}")
        except Exception as e:
            print(f"  - response parse error: {e}")


if __name__ == "__main__":
    demo_usage()
    
    print("\n" + "=" * 70)
    print("如需验证还原结果，请提供文件路径：")
    print("=" * 70)
    print("python example_use_restored_results.py \\")
    print("  --validate \\")
    print("  --intermediate output/dedup_intermediate/demo_edge_dedup_xxx.json \\")
    print("  --restored output/dedup_intermediate/demo_semantic_results_xxx.pkl")
