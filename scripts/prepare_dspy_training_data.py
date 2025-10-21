"""
准备DSPy训练数据

这个脚本创建训练样本用于优化semantic dedup的DSPy模块。

使用方法:
    python scripts/prepare_dspy_training_data.py --output data/dspy_training_examples.json
"""

import json
import dspy
from pathlib import Path
import argparse
from typing import List, Dict


def create_synthetic_training_examples() -> List[dspy.Example]:
    """
    创建合成训练样本
    
    这些样本覆盖了常见的去重场景:
    1. Person names with aliases
    2. City/location names
    3. Product names with versions
    4. Organization names
    5. Attributes and properties
    """
    
    examples = []
    
    # ========== Example 1: Movie Directors (Person Aliases) ==========
    examples.append(dspy.Example(
        head_entity="Star Wars film series",
        relation="director",
        tail_descriptions=[
            "George Lucas",
            "G. Lucas", 
            "George Walton Lucas Jr.",
            "J.J. Abrams",
            "Jeffrey Jacob Abrams",
            "Rian Johnson",
            "Irvin Kershner",
            "Richard Marquand"
        ],
        # Gold clustering: group potential aliases
        gold_clusters=[
            [1, 2, 3],     # George Lucas variants
            [4, 5],        # J.J. Abrams variants
            [6],           # Rian Johnson
            [7],           # Irvin Kershner
            [8]            # Richard Marquand
        ],
        # Gold groups: true coreferences only
        gold_groups=[
            {"members": [1, 2, 3], "representative": 1, "rationale": "Same person - George Lucas"},
            {"members": [4, 5], "representative": 4, "rationale": "Same person - J.J. Abrams"},
            {"members": [6], "representative": 6, "rationale": "Different director"},
            {"members": [7], "representative": 7, "rationale": "Different director"},
            {"members": [8], "representative": 8, "rationale": "Different director"}
        ]
    ).with_inputs("head_entity", "relation", "tail_descriptions"))
    
    # ========== Example 2: Cities (Location Aliases) ==========
    examples.append(dspy.Example(
        head_entity="United States",
        relation="has_city",
        tail_descriptions=[
            "New York City",
            "NYC",
            "New York",
            "The Big Apple",
            "Los Angeles",
            "LA",
            "City of Angels",
            "San Francisco",
            "SF",
            "Chicago"
        ],
        gold_clusters=[
            [1, 2, 3, 4],   # New York variants
            [5, 6, 7],      # Los Angeles variants
            [8, 9],         # San Francisco variants
            [10]            # Chicago
        ],
        gold_groups=[
            {"members": [1, 2, 3, 4], "representative": 1, "rationale": "Same city - New York"},
            {"members": [5, 6, 7], "representative": 5, "rationale": "Same city - Los Angeles"},
            {"members": [8, 9], "representative": 8, "rationale": "Same city - San Francisco"},
            {"members": [10], "representative": 10, "rationale": "Different city"}
        ]
    ).with_inputs("head_entity", "relation", "tail_descriptions"))
    
    # ========== Example 3: Products (Should NOT Merge Different Versions) ==========
    examples.append(dspy.Example(
        head_entity="Apple Inc.",
        relation="product",
        tail_descriptions=[
            "iPhone",
            "iPhone 13",
            "iPhone 14",
            "iPhone 15",
            "MacBook",
            "MacBook Pro",
            "MacBook Air",
            "iPad",
            "iPad Pro"
        ],
        gold_clusters=[
            [1, 2, 3, 4],    # iPhone series (cluster together for initial grouping)
            [5, 6, 7],       # MacBook series
            [8, 9]           # iPad series
        ],
        gold_groups=[
            # Keep specific models separate - they are different products
            {"members": [1], "representative": 1, "rationale": "Generic iPhone product line"},
            {"members": [2], "representative": 2, "rationale": "Specific model - iPhone 13"},
            {"members": [3], "representative": 3, "rationale": "Specific model - iPhone 14"},
            {"members": [4], "representative": 4, "rationale": "Specific model - iPhone 15"},
            {"members": [5], "representative": 5, "rationale": "Generic MacBook"},
            {"members": [6], "representative": 6, "rationale": "Specific model - MacBook Pro"},
            {"members": [7], "representative": 7, "rationale": "Specific model - MacBook Air"},
            {"members": [8], "representative": 8, "rationale": "Generic iPad"},
            {"members": [9], "representative": 9, "rationale": "Specific model - iPad Pro"}
        ]
    ).with_inputs("head_entity", "relation", "tail_descriptions"))
    
    # ========== Example 4: Countries (Aliases and Abbreviations) ==========
    examples.append(dspy.Example(
        head_entity="United Nations",
        relation="member_country",
        tail_descriptions=[
            "United States",
            "USA",
            "US",
            "America",
            "United States of America",
            "United Kingdom",
            "UK",
            "Britain",
            "Great Britain",
            "France",
            "French Republic"
        ],
        gold_clusters=[
            [1, 2, 3, 4, 5],    # United States variants
            [6, 7, 8, 9],       # United Kingdom variants
            [10, 11]            # France variants
        ],
        gold_groups=[
            {"members": [1, 2, 3, 4, 5], "representative": 1, "rationale": "Same country - United States"},
            {"members": [6, 7, 8, 9], "representative": 6, "rationale": "Same country - United Kingdom"},
            {"members": [10, 11], "representative": 10, "rationale": "Same country - France"}
        ]
    ).with_inputs("head_entity", "relation", "tail_descriptions"))
    
    # ========== Example 5: Organizations (Similar Names but Different Entities) ==========
    examples.append(dspy.Example(
        head_entity="Fortune 500",
        relation="company",
        tail_descriptions=[
            "Microsoft",
            "Microsoft Corporation",
            "Apple",
            "Apple Inc.",
            "Apple Computer",
            "Amazon",
            "Amazon.com",
            "Google",
            "Alphabet Inc."
        ],
        gold_clusters=[
            [1, 2],         # Microsoft
            [3, 4, 5],      # Apple variants
            [6, 7],         # Amazon
            [8, 9]          # Google/Alphabet (tricky case!)
        ],
        gold_groups=[
            {"members": [1, 2], "representative": 1, "rationale": "Same company - Microsoft"},
            {"members": [3, 4, 5], "representative": 3, "rationale": "Same company - Apple"},
            {"members": [6, 7], "representative": 6, "rationale": "Same company - Amazon"},
            # Google and Alphabet are technically different (Alphabet is parent), but commonly used interchangeably
            {"members": [8, 9], "representative": 9, "rationale": "Parent-subsidiary, often used interchangeably"}
        ]
    ).with_inputs("head_entity", "relation", "tail_descriptions"))
    
    # ========== Example 6: Attributes (Unit Conversions) ==========
    examples.append(dspy.Example(
        head_entity="Water",
        relation="has_attribute",
        tail_descriptions=[
            "boiling point 100°C",
            "boiling point 212°F",
            "boiling point 373K",
            "freezing point 0°C",
            "freezing point 32°F",
            "density 1 g/cm³",
            "density 1000 kg/m³",
            "molecular formula H2O"
        ],
        gold_clusters=[
            [1, 2, 3],      # Boiling point variants
            [4, 5],         # Freezing point variants
            [6, 7],         # Density variants
            [8]             # Molecular formula
        ],
        gold_groups=[
            {"members": [1, 2, 3], "representative": 1, "rationale": "Same property-value, different units"},
            {"members": [4, 5], "representative": 4, "rationale": "Same property-value, different units"},
            {"members": [6, 7], "representative": 6, "rationale": "Same property-value, different units"},
            {"members": [8], "representative": 8, "rationale": "Different property"}
        ]
    ).with_inputs("head_entity", "relation", "tail_descriptions"))
    
    # ========== Example 7: Books (Multiple Works by Same Author - Don't Merge!) ==========
    examples.append(dspy.Example(
        head_entity="J.K. Rowling",
        relation="author_of",
        tail_descriptions=[
            "Harry Potter and the Philosopher's Stone",
            "Harry Potter and the Sorcerer's Stone",
            "Harry Potter and the Chamber of Secrets",
            "Harry Potter and the Prisoner of Azkaban",
            "The Casual Vacancy",
            "The Cuckoo's Calling"
        ],
        gold_clusters=[
            [1, 2],         # Same book, different titles (UK vs US)
            [3],            # Different book
            [4],            # Different book
            [5],            # Different book
            [6]             # Different book
        ],
        gold_groups=[
            {"members": [1, 2], "representative": 1, "rationale": "Same book, regional title differences"},
            {"members": [3], "representative": 3, "rationale": "Different book in series"},
            {"members": [4], "representative": 4, "rationale": "Different book in series"},
            {"members": [5], "representative": 5, "rationale": "Different book (not HP series)"},
            {"members": [6], "representative": 6, "rationale": "Different book (pseudonym work)"}
        ]
    ).with_inputs("head_entity", "relation", "tail_descriptions"))
    
    # ========== Example 8: Scientific Concepts (Different Representations) ==========
    examples.append(dspy.Example(
        head_entity="Carbon",
        relation="allotrope",
        tail_descriptions=[
            "diamond",
            "graphite",
            "graphene",
            "carbon nanotube",
            "fullerene",
            "C60",
            "buckminsterfullerene",
            "buckyball"
        ],
        gold_clusters=[
            [1],            # Diamond
            [2],            # Graphite
            [3],            # Graphene
            [4],            # Carbon nanotube
            [5, 6, 7, 8]    # Fullerene variants
        ],
        gold_groups=[
            {"members": [1], "representative": 1, "rationale": "Distinct allotrope"},
            {"members": [2], "representative": 2, "rationale": "Distinct allotrope"},
            {"members": [3], "representative": 3, "rationale": "Distinct allotrope"},
            {"members": [4], "representative": 4, "rationale": "Distinct allotrope"},
            {"members": [5, 6, 7, 8], "representative": 5, "rationale": "Same molecule - C60 fullerene, multiple names"}
        ]
    ).with_inputs("head_entity", "relation", "tail_descriptions"))
    
    return examples


def save_training_examples(examples: List[dspy.Example], output_file: str):
    """保存训练样本到JSON文件"""
    data = []
    for ex in examples:
        ex_dict = ex.toDict()
        data.append(ex_dict)
    
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Saved {len(examples)} training examples to {output_file}")


def load_training_examples(input_file: str) -> List[dspy.Example]:
    """从JSON文件加载训练样本"""
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    examples = []
    for item in data:
        # Reconstruct dspy.Example
        example = dspy.Example(**item)
        
        # Set inputs (assuming standard fields)
        if "head_entity" in item and "relation" in item and "tail_descriptions" in item:
            example = example.with_inputs("head_entity", "relation", "tail_descriptions")
        
        examples.append(example)
    
    return examples


def print_example_stats(examples: List[dspy.Example]):
    """打印训练样本统计信息"""
    print("\n" + "="*80)
    print("Training Examples Statistics")
    print("="*80)
    
    total_tails = 0
    total_clusters = 0
    total_groups = 0
    
    for ex in examples:
        num_tails = len(ex.tail_descriptions)
        num_clusters = len(ex.gold_clusters) if hasattr(ex, 'gold_clusters') else 0
        num_groups = len(ex.gold_groups) if hasattr(ex, 'gold_groups') else 0
        
        total_tails += num_tails
        total_clusters += num_clusters
        total_groups += num_groups
        
        print(f"\nExample: {ex.head_entity} - {ex.relation}")
        print(f"  Tails: {num_tails}")
        print(f"  Gold Clusters: {num_clusters}")
        print(f"  Gold Groups: {num_groups}")
    
    print("\n" + "="*80)
    print(f"Total Examples: {len(examples)}")
    print(f"Total Tails: {total_tails}")
    print(f"Avg Tails per Example: {total_tails / len(examples):.1f}")
    print(f"Total Clusters: {total_clusters}")
    print(f"Total Groups: {total_groups}")
    print("="*80 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Prepare DSPy training data for semantic dedup")
    parser.add_argument(
        '--output',
        type=str,
        default='data/dspy_training_examples.json',
        help='Output JSON file path'
    )
    parser.add_argument(
        '--show-stats',
        action='store_true',
        help='Show statistics about the training examples'
    )
    
    args = parser.parse_args()
    
    print("Creating synthetic training examples...")
    examples = create_synthetic_training_examples()
    
    print(f"Created {len(examples)} training examples")
    
    if args.show_stats:
        print_example_stats(examples)
    
    # Save to file
    save_training_examples(examples, args.output)
    
    print("\nNext steps:")
    print("1. Review the training examples")
    print("2. Add more examples from real data if available")
    print("3. Run: python scripts/train_dspy_modules.py")


if __name__ == "__main__":
    main()
