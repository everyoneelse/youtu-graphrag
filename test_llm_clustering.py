"""
Test script for LLM-based clustering functionality.

This script demonstrates how to use LLM clustering for tail deduplication.
"""

import json
from models.constructor.kt_gen import KTBuilder
from config import get_config

def test_llm_clustering():
    """Test LLM clustering with a simple example."""
    
    print("=" * 80)
    print("Testing LLM-based Clustering for Tail Deduplication")
    print("=" * 80)
    
    # Load configuration
    config = get_config()
    
    # Create KTBuilder instance
    builder = KTBuilder("demo", config=config)
    
    # Test case 1: Directors of Star Wars
    print("\n" + "=" * 80)
    print("Test Case 1: Movie Directors")
    print("=" * 80)
    
    head_text = "Star Wars (film series)"
    relation = "director"
    
    # Simulated tail descriptions
    tail_descriptions = [
        "George Lucas",
        "G. Lucas",
        "George Walton Lucas Jr.",
        "J.J. Abrams",
        "Jeffrey Jacob Abrams",
        "Rian Johnson",
        "Irvin Kershner",
        "Richard Marquand"
    ]
    
    print(f"\nHead: {head_text}")
    print(f"Relation: {relation}")
    print(f"\nTail candidates ({len(tail_descriptions)}):")
    for i, desc in enumerate(tail_descriptions, 1):
        print(f"  [{i}] {desc}")
    
    # Test LLM clustering
    print("\n" + "-" * 80)
    print("Testing LLM Clustering...")
    print("-" * 80)
    
    try:
        clusters = builder._cluster_candidate_tails_with_llm(
            head_text, 
            relation, 
            tail_descriptions,
            max_batch_size=10
        )
        
        print(f"\nLLM Clustering Results: {len(clusters)} clusters")
        for i, cluster in enumerate(clusters, 1):
            print(f"\nCluster {i} ({len(cluster)} members):")
            for idx in cluster:
                if 0 <= idx < len(tail_descriptions):
                    print(f"  [{idx+1}] {tail_descriptions[idx]}")
        
    except Exception as e:
        print(f"\n❌ LLM Clustering failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test embedding clustering for comparison
    print("\n" + "-" * 80)
    print("Testing Embedding Clustering (for comparison)...")
    print("-" * 80)
    
    try:
        clusters_emb = builder._cluster_candidate_tails(
            tail_descriptions,
            threshold=0.85
        )
        
        print(f"\nEmbedding Clustering Results: {len(clusters_emb)} clusters")
        for i, cluster in enumerate(clusters_emb, 1):
            print(f"\nCluster {i} ({len(cluster)} members):")
            for idx in cluster:
                if 0 <= idx < len(tail_descriptions):
                    print(f"  [{idx+1}] {tail_descriptions[idx]}")
        
    except Exception as e:
        print(f"\n❌ Embedding Clustering failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test case 2: City names
    print("\n\n" + "=" * 80)
    print("Test Case 2: City Names")
    print("=" * 80)
    
    head_text = "United States"
    relation = "has_city"
    
    city_descriptions = [
        "New York",
        "NYC",
        "New York City",
        "Los Angeles",
        "LA",
        "City of Angels",
        "Chicago",
        "San Francisco",
        "SF",
        "Bay Area city"
    ]
    
    print(f"\nHead: {head_text}")
    print(f"Relation: {relation}")
    print(f"\nTail candidates ({len(city_descriptions)}):")
    for i, desc in enumerate(city_descriptions, 1):
        print(f"  [{i}] {desc}")
    
    print("\n" + "-" * 80)
    print("Testing LLM Clustering...")
    print("-" * 80)
    
    try:
        clusters = builder._cluster_candidate_tails_with_llm(
            head_text,
            relation,
            city_descriptions,
            max_batch_size=10
        )
        
        print(f"\nLLM Clustering Results: {len(clusters)} clusters")
        for i, cluster in enumerate(clusters, 1):
            print(f"\nCluster {i} ({len(cluster)} members):")
            for idx in cluster:
                if 0 <= idx < len(city_descriptions):
                    print(f"  [{idx+1}] {city_descriptions[idx]}")
        
    except Exception as e:
        print(f"\n❌ LLM Clustering failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("Test completed!")
    print("=" * 80)

if __name__ == "__main__":
    test_llm_clustering()
