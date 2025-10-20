"""
Test script for dual LLM configuration.

This script demonstrates how to use different LLMs for clustering and deduplication.
"""

import os
from models.constructor.kt_gen import KTBuilder
from config import get_config

def test_dual_llm_configuration():
    """Test dual LLM configuration."""
    
    print("=" * 80)
    print("Testing Dual LLM Configuration")
    print("=" * 80)
    
    # Load configuration
    config = get_config()
    
    print("\n" + "=" * 80)
    print("Checking LLM Configuration")
    print("=" * 80)
    
    # Check semantic dedup config
    semantic_config = config.construction.semantic_dedup
    
    print(f"\nSemantic Dedup Enabled: {semantic_config.enabled}")
    print(f"Clustering Method: {semantic_config.clustering_method}")
    
    # Check clustering LLM config
    clustering_llm = semantic_config.clustering_llm
    if clustering_llm and clustering_llm.model:
        print(f"\n✓ Custom Clustering LLM configured:")
        print(f"  - Model: {clustering_llm.model}")
        print(f"  - Base URL: {clustering_llm.base_url}")
        print(f"  - Temperature: {clustering_llm.temperature}")
    else:
        print(f"\n○ Using default LLM for clustering")
    
    # Check dedup LLM config
    dedup_llm = semantic_config.dedup_llm
    if dedup_llm and dedup_llm.model:
        print(f"\n✓ Custom Deduplication LLM configured:")
        print(f"  - Model: {dedup_llm.model}")
        print(f"  - Base URL: {dedup_llm.base_url}")
        print(f"  - Temperature: {dedup_llm.temperature}")
    else:
        print(f"\n○ Using default LLM for deduplication")
    
    # Create KTBuilder instance to test LLM client initialization
    print("\n" + "=" * 80)
    print("Initializing KTBuilder")
    print("=" * 80)
    
    try:
        builder = KTBuilder("demo", config=config)
        
        print(f"\n✓ KTBuilder initialized successfully")
        print(f"\n✓ Default LLM client: {builder.llm_client.llm_model}")
        print(f"✓ Clustering LLM client: {builder.clustering_llm_client.llm_model}")
        print(f"✓ Deduplication LLM client: {builder.dedup_llm_client.llm_model}")
        
        # Check if they are different instances
        if builder.clustering_llm_client != builder.dedup_llm_client:
            print(f"\n✓ Using separate LLM clients for clustering and deduplication")
        else:
            print(f"\n○ Using the same LLM client for both tasks")
        
    except Exception as e:
        print(f"\n❌ Failed to initialize KTBuilder: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test a simple clustering call (if LLM is configured)
    print("\n" + "=" * 80)
    print("Testing Clustering LLM Call")
    print("=" * 80)
    
    test_descriptions = [
        "New York City",
        "NYC",
        "New York",
        "Los Angeles",
        "LA"
    ]
    
    try:
        print(f"\nTest input: {len(test_descriptions)} tail descriptions")
        for i, desc in enumerate(test_descriptions, 1):
            print(f"  [{i}] {desc}")
        
        clusters = builder._cluster_candidate_tails_with_llm(
            head_text="United States",
            relation="has_city",
            descriptions=test_descriptions,
            max_batch_size=10
        )
        
        print(f"\n✓ Clustering successful: {len(clusters)} clusters formed")
        for i, cluster in enumerate(clusters, 1):
            print(f"\nCluster {i}:")
            for idx in cluster:
                if 0 <= idx < len(test_descriptions):
                    print(f"  - {test_descriptions[idx]}")
        
    except Exception as e:
        print(f"\n❌ Clustering call failed: {e}")
        print(f"This is expected if API keys are not configured")
    
    print("\n" + "=" * 80)
    print("Cost Estimation")
    print("=" * 80)
    
    # Estimate costs for different configurations
    num_tails = 1000
    clustering_calls = num_tails // 30
    dedup_calls = num_tails // 8
    
    print(f"\nAssuming {num_tails} tails to process:")
    print(f"  - Clustering calls: ~{clustering_calls}")
    print(f"  - Deduplication calls: ~{dedup_calls}")
    
    # Cost estimates (approximate, in USD)
    costs = {
        "gpt-4": 0.03,
        "gpt-3.5-turbo": 0.002,
        "deepseek-chat": 0.001
    }
    
    clustering_model = clustering_llm.model if clustering_llm and clustering_llm.model else "default"
    dedup_model = dedup_llm.model if dedup_llm and dedup_llm.model else "default"
    
    clustering_cost = clustering_calls * costs.get(clustering_model, 0.01)
    dedup_cost = dedup_calls * costs.get(dedup_model, 0.01)
    
    print(f"\nEstimated costs:")
    print(f"  - Clustering ({clustering_model}): ${clustering_cost:.2f}")
    print(f"  - Deduplication ({dedup_model}): ${dedup_cost:.2f}")
    print(f"  - Total: ${clustering_cost + dedup_cost:.2f}")
    
    # Compare with single LLM
    single_cost = (clustering_calls + dedup_calls) * costs.get("gpt-4", 0.03)
    print(f"\nCompare with single GPT-4:")
    print(f"  - Single LLM cost: ${single_cost:.2f}")
    if (clustering_cost + dedup_cost) < single_cost:
        savings = single_cost - (clustering_cost + dedup_cost)
        savings_pct = (savings / single_cost) * 100
        print(f"  - Savings: ${savings:.2f} ({savings_pct:.1f}%)")
    
    print("\n" + "=" * 80)
    print("Test completed!")
    print("=" * 80)
    
    print("\nNext steps:")
    print("1. Configure your LLM API keys in .env or config file")
    print("2. Run with: python main.py --config config/example_with_dual_llm.yaml --dataset demo")
    print("3. Analyze results with: python example_analyze_dedup_results.py output/dedup_intermediate/*")
    print("4. Adjust configurations based on your cost/quality requirements")

if __name__ == "__main__":
    test_dual_llm_configuration()
