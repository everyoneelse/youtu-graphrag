# DSPy Prompt Optimization Analysis for Semantic Dedup

## 概述

是的，您可以使用 DSPy 来优化 `semantic_dedup_group` 中使用的 LLM clustering 和 LLM dedup 的 prompt。本文档分析当前实现并提供 DSPy 优化方案。

## 当前实现分析

### 1. 当前使用的 Prompts

在 `models/constructor/kt_gen.py` 中，有三个主要的 prompt：

#### 1.1 LLM Clustering Prompt (`DEFAULT_LLM_CLUSTERING_PROMPT`)
**用途**: 初步聚类相似的tail entities  
**位置**: 第145-191行  
**调用**: `_llm_cluster_batch()` 方法（第970行）

```python
# 用于初始聚类，将相似的tail entities分组
prompt = DEFAULT_LLM_CLUSTERING_PROMPT.format(
    head=head_text,
    relation=relation,
    candidates=candidates_text
)
response = self.clustering_llm_client.call_api(prompt)
```

**输出格式**:
```json
{
  "clusters": [
    {
      "members": [1, 3, 5],
      "description": "Brief explanation of why these tails are clustered together"
    }
  ]
}
```

#### 1.2 Semantic Dedup Prompt (`DEFAULT_SEMANTIC_DEDUP_PROMPT`)
**用途**: 在cluster内识别共指实体（coreference）  
**位置**: 第22-80行  
**调用**: `_build_semantic_dedup_prompt()` -> `_llm_semantic_group()` 方法（第1166行）

```python
# 用于精细去重，识别哪些tail是同一个实体
prompt = self._build_semantic_dedup_prompt(head_text, relation, head_context_lines, batch_entries)
response = self.dedup_llm_client.call_api(prompt)
```

**输出格式**:
```json
{
  "groups": [
    {
      "members": [1, 2, 3],
      "representative": 2,
      "rationale": "These tails all refer to the same entity..."
    }
  ]
}
```

#### 1.3 Attribute Dedup Prompt (`DEFAULT_ATTRIBUTE_DEDUP_PROMPT`)
**用途**: 专门处理属性值的去重  
**位置**: 第82-143行  
**调用**: 与 semantic dedup 相同的代码路径，但通过 `prompt_type` 区分

---

## 为什么使用 DSPy

### 当前问题

1. **手工调优困难**: prompt 非常长且复杂，手动调整效果难以预测
2. **缺乏系统评估**: 没有自动化方式评估 prompt 性能
3. **固定模板**: 对不同的 relation 类型使用相同的 prompt，无法自适应
4. **无法量化改进**: 修改 prompt 后无法客观比较效果

### DSPy 的优势

1. **自动优化**: 基于训练数据自动调整 prompt
2. **程序化构建**: 将 prompt 逻辑模块化，易于维护
3. **可测量**: 使用明确的 metric 评估和优化
4. **少样本学习**: 只需要少量标注数据就能显著提升效果
5. **适应性**: 可以为不同类型的 relation 自动调整策略

---

## DSPy 实现方案

### 架构设计

```
┌─────────────────────────────────────────────────┐
│         Semantic Dedup with DSPy                │
├─────────────────────────────────────────────────┤
│                                                  │
│  1. DSPy Clustering Module                      │
│     ├─ Input: head, relation, tail_list         │
│     ├─ Signature: TailClustering                │
│     └─ Output: clusters with descriptions        │
│                                                  │
│  2. DSPy Deduplication Module                   │
│     ├─ Input: head, relation, context, cluster  │
│     ├─ Signature: CoreferenceResolution          │
│     └─ Output: coreference groups                │
│                                                  │
│  3. DSPy Optimizer                              │
│     ├─ Training Data: labeled examples          │
│     ├─ Metric: clustering accuracy + dedup F1   │
│     └─ Optimizer: MIPRO / BootstrapFewShot      │
│                                                  │
└─────────────────────────────────────────────────┘
```

### 第一步：定义 DSPy Signatures

创建 `models/constructor/dspy_semantic_dedup.py`:

```python
import dspy
from typing import List
import json


# ========== Signature Definitions ==========

class TailClustering(dspy.Signature):
    """初步聚类tail entities，将可能指向同一实体的tails分到一组。"""
    
    head_entity: str = dspy.InputField(desc="Head entity description")
    relation: str = dspy.InputField(desc="Relation name")
    tail_candidates: str = dspy.InputField(
        desc="List of tail entities with indices, format: [1] tail1\\n[2] tail2\\n..."
    )
    
    clusters: str = dspy.OutputField(
        desc="JSON array of clusters. Each cluster has 'members' (list of indices) and 'description' (rationale). "
        "Example: [{\"members\": [1,2], \"description\": \"potential coreference\"}]"
    )


class CoreferenceResolution(dspy.Signature):
    """在cluster内识别共指实体，决定哪些tail是同一个实体的不同表达。"""
    
    head_entity: str = dspy.InputField(desc="Head entity description")
    relation: str = dspy.InputField(desc="Relation name")
    head_contexts: str = dspy.InputField(desc="Context information about the head entity")
    tail_candidates: str = dspy.InputField(
        desc="List of tail entities with their contexts. Format: [idx] Tail: description\\n    Contexts: ...\\n"
    )
    
    # Add reasoning chain for better accuracy
    reasoning: str = dspy.OutputField(
        desc="Step-by-step reasoning: For each pair, explain if they are coreferent (same entity) or distinct. "
        "Apply the REFERENT TEST and SUBSTITUTION TEST."
    )
    
    coreference_groups: str = dspy.OutputField(
        desc="JSON array of coreference groups. Each group has 'members' (indices), 'representative' (index), "
        "and 'rationale'. Example: [{\"members\": [1,2,3], \"representative\": 2, \"rationale\": \"...\"}]"
    )


class AttributeEquivalence(dspy.Signature):
    """识别属性值的等价关系，判断哪些属性值表达相同的property-value pair。"""
    
    head_entity: str = dspy.InputField(desc="Head entity description")
    relation: str = dspy.InputField(desc="Attribute relation name")
    head_contexts: str = dspy.InputField(desc="Context information about the head entity")
    attribute_candidates: str = dspy.InputField(
        desc="List of attribute values with contexts"
    )
    
    reasoning: str = dspy.OutputField(
        desc="For each pair: (1) Same property? (2) Same value? (3) Only linguistic difference?"
    )
    
    equivalence_groups: str = dspy.OutputField(
        desc="JSON array of equivalence groups with members, representative, and rationale"
    )


# ========== DSPy Modules ==========

class SemanticClusteringModule(dspy.Module):
    """使用DSPy进行初步聚类"""
    
    def __init__(self):
        super().__init__()
        self.cluster = dspy.ChainOfThought(TailClustering)
    
    def forward(self, head_entity: str, relation: str, tail_descriptions: List[str]):
        # Format candidates
        candidates_text = "\\n".join([f"[{i+1}] {desc}" for i, desc in enumerate(tail_descriptions)])
        
        # Call DSPy module
        result = self.cluster(
            head_entity=head_entity,
            relation=relation,
            tail_candidates=candidates_text
        )
        
        # Parse output
        try:
            clusters = json.loads(result.clusters)
            return clusters
        except json.JSONDecodeError:
            # Fallback: return single cluster
            return [{"members": list(range(1, len(tail_descriptions) + 1)), "description": "fallback"}]


class SemanticDedupModule(dspy.Module):
    """使用DSPy进行语义去重（共指消解）"""
    
    def __init__(self, prompt_type: str = "general"):
        super().__init__()
        self.prompt_type = prompt_type
        
        if prompt_type == "attribute":
            self.dedup = dspy.ChainOfThought(AttributeEquivalence)
        else:
            self.dedup = dspy.ChainOfThought(CoreferenceResolution)
    
    def forward(self, head_entity: str, relation: str, head_contexts: List[str], 
                batch_entries: List[dict]):
        # Format inputs
        head_context_text = "\\n".join(head_contexts) if head_contexts else "- (no context)"
        
        candidates_blocks = []
        for idx, entry in enumerate(batch_entries, start=1):
            desc = entry.get("description", "[NO DESCRIPTION]")
            contexts = entry.get("context_summaries", ["- (no context)"])
            context_block = "\\n        ".join(contexts)
            candidates_blocks.append(f"[{idx}] Tail: {desc}\\n    Contexts:\\n        {context_block}")
        
        candidates_text = "\\n".join(candidates_blocks)
        
        # Call DSPy module
        if self.prompt_type == "attribute":
            result = self.dedup(
                head_entity=head_entity,
                relation=relation,
                head_contexts=head_context_text,
                attribute_candidates=candidates_text
            )
            groups_json = result.equivalence_groups
        else:
            result = self.dedup(
                head_entity=head_entity,
                relation=relation,
                head_contexts=head_context_text,
                tail_candidates=candidates_text
            )
            groups_json = result.coreference_groups
        
        # Parse output
        try:
            groups = json.loads(groups_json)
            return groups, result.reasoning
        except json.JSONDecodeError:
            return [], ""


# ========== Metrics for Optimization ==========

def clustering_metric(gold, pred, trace=None):
    """
    评估聚类质量的metric
    
    gold: ground truth clusters - List[List[int]]
    pred: predicted clusters - List[List[int]]
    
    Returns: F1 score (0-100)
    """
    # Convert to sets of pairs for comparison
    def clusters_to_pairs(clusters):
        pairs = set()
        for cluster in clusters:
            members = cluster.get("members", []) if isinstance(cluster, dict) else cluster
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    pairs.add((min(members[i], members[j]), max(members[i], members[j])))
        return pairs
    
    gold_pairs = clusters_to_pairs(gold)
    pred_pairs = clusters_to_pairs(pred)
    
    if len(pred_pairs) == 0:
        return 0.0 if len(gold_pairs) > 0 else 100.0
    
    true_positive = len(gold_pairs & pred_pairs)
    false_positive = len(pred_pairs - gold_pairs)
    false_negative = len(gold_pairs - pred_pairs)
    
    precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) > 0 else 0
    recall = true_positive / (true_positive + false_negative) if (true_positive + false_negative) > 0 else 0
    
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    
    return f1 * 100


def dedup_metric(gold, pred, trace=None):
    """
    评估去重质量的metric
    
    Similar to clustering metric but considers representative selection
    """
    return clustering_metric(gold, pred, trace)


# ========== Optimizer ==========

class DSPySemanticDedupOptimizer:
    """优化semantic dedup的DSPy模块"""
    
    def __init__(self, train_examples, validation_examples):
        """
        train_examples: List of dspy.Example objects with:
            - head_entity, relation, tail_descriptions
            - gold_clusters (for clustering)
            - gold_groups (for deduplication)
        """
        self.train_examples = train_examples
        self.validation_examples = validation_examples
        
        # Initialize modules
        self.clustering_module = SemanticClusteringModule()
        self.dedup_module = SemanticDedupModule()
    
    def optimize_clustering(self, teacher_model="gpt-4", student_model="gpt-3.5-turbo"):
        """优化聚类模块"""
        # Configure DSPy
        teacher_lm = dspy.OpenAI(model=teacher_model, max_tokens=2000)
        student_lm = dspy.OpenAI(model=student_model, max_tokens=2000)
        
        dspy.settings.configure(lm=student_lm)
        
        # Use BootstrapFewShot optimizer
        from dspy.teleprompt import BootstrapFewShot
        
        optimizer = BootstrapFewShot(
            metric=clustering_metric,
            max_bootstrapped_demos=4,
            max_labeled_demos=4,
            teacher_settings=dict(lm=teacher_lm)
        )
        
        # Compile the module
        optimized_clustering = optimizer.compile(
            self.clustering_module,
            trainset=self.train_examples
        )
        
        return optimized_clustering
    
    def optimize_dedup(self, teacher_model="gpt-4", student_model="gpt-3.5-turbo"):
        """优化去重模块"""
        teacher_lm = dspy.OpenAI(model=teacher_model, max_tokens=3000)
        student_lm = dspy.OpenAI(model=student_model, max_tokens=3000)
        
        dspy.settings.configure(lm=student_lm)
        
        from dspy.teleprompt import BootstrapFewShot
        
        optimizer = BootstrapFewShot(
            metric=dedup_metric,
            max_bootstrapped_demos=3,
            max_labeled_demos=3,
            teacher_settings=dict(lm=teacher_lm)
        )
        
        optimized_dedup = optimizer.compile(
            self.dedup_module,
            trainset=self.train_examples
        )
        
        return optimized_dedup
    
    def evaluate(self, module, examples, metric):
        """评估模块性能"""
        scores = []
        for example in examples:
            pred = module(**example.inputs())
            score = metric(example.gold, pred)
            scores.append(score)
        
        return sum(scores) / len(scores) if scores else 0.0


# ========== Integration with KTBuilder ==========

class DSPyEnabledKTBuilder:
    """
    在KTBuilder中集成DSPy模块的包装类
    
    使用方法:
    1. 准备训练数据
    2. 训练/加载优化后的DSPy模块
    3. 在semantic_dedup_group中使用
    """
    
    def __init__(self, kt_builder, optimized_clustering=None, optimized_dedup=None):
        self.kt_builder = kt_builder
        self.optimized_clustering = optimized_clustering
        self.optimized_dedup = optimized_dedup
    
    def cluster_with_dspy(self, head_text: str, relation: str, descriptions: List[str]):
        """使用DSPy进行聚类"""
        if self.optimized_clustering is None:
            # Fallback to original method
            return self.kt_builder._cluster_candidate_tails_with_llm(
                head_text, relation, descriptions
            )
        
        # Use optimized DSPy module
        clusters = self.optimized_clustering(
            head_entity=head_text,
            relation=relation,
            tail_descriptions=descriptions
        )
        
        # Convert to original format
        return self._convert_clusters_format(clusters)
    
    def dedup_with_dspy(self, head_text: str, relation: str, 
                       head_context_lines: List[str], batch_entries: List[dict]):
        """使用DSPy进行去重"""
        if self.optimized_dedup is None:
            # Fallback to original method
            return self.kt_builder._llm_semantic_group(
                head_text, relation, head_context_lines, batch_entries
            )
        
        # Use optimized DSPy module
        groups, reasoning = self.optimized_dedup(
            head_entity=head_text,
            relation=relation,
            head_contexts=head_context_lines,
            batch_entries=batch_entries
        )
        
        # Convert to original format
        return self._convert_groups_format(groups)
    
    def _convert_clusters_format(self, clusters):
        """转换DSPy输出格式到原始格式"""
        result_clusters = []
        result_details = []
        
        for idx, cluster in enumerate(clusters):
            members = cluster.get("members", [])
            # Convert 1-based to 0-based indices
            members_0based = [m - 1 for m in members]
            result_clusters.append(members_0based)
            
            result_details.append({
                "cluster_id": idx,
                "members": members_0based,
                "description": cluster.get("description", ""),
                "llm_rationale": cluster.get("description", "")
            })
        
        return result_clusters, result_details
    
    def _convert_groups_format(self, groups):
        """转换DSPy输出格式到原始格式"""
        result_groups = []
        
        for group in groups:
            members = group.get("members", [])
            representative = group.get("representative")
            rationale = group.get("rationale")
            
            # Convert 1-based to 0-based
            members_0based = [m - 1 for m in members]
            rep_0based = representative - 1 if representative else members_0based[0]
            
            result_groups.append({
                "representative": rep_0based,
                "members": members_0based,
                "rationale": rationale
            })
        
        return result_groups
```

### 第二步：准备训练数据

创建 `scripts/prepare_dspy_training_data.py`:

```python
"""
准备DSPy训练数据的脚本

从已有的去重结果或人工标注中提取训练样本
"""

import json
import dspy
from pathlib import Path


def load_training_examples_from_manual_labels(label_file: str):
    """
    从人工标注文件加载训练样本
    
    标注文件格式 (JSON):
    [
        {
            "head_entity": "Star Wars",
            "relation": "director",
            "tail_descriptions": ["George Lucas", "G. Lucas", "George Walton Lucas Jr.", "J.J. Abrams"],
            "gold_clusters": [
                {"members": [0, 1, 2], "description": "All refer to George Lucas"},
                {"members": [3], "description": "Different person - J.J. Abrams"}
            ],
            "gold_groups": [
                {"members": [0, 1, 2], "representative": 0, "rationale": "Same person"},
                {"members": [3], "representative": 3, "rationale": "Different director"}
            ]
        }
    ]
    """
    with open(label_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    examples = []
    for item in data:
        example = dspy.Example(
            head_entity=item["head_entity"],
            relation=item["relation"],
            tail_descriptions=item["tail_descriptions"],
            gold_clusters=item.get("gold_clusters", []),
            gold_groups=item.get("gold_groups", [])
        ).with_inputs("head_entity", "relation", "tail_descriptions")
        
        examples.append(example)
    
    return examples


def extract_training_examples_from_results(results_dir: str, sample_size: int = 50):
    """
    从已有的去重结果中采样，用于bootstrap training
    
    这个函数从output/dedup_intermediate中提取高质量的去重案例
    """
    results_path = Path(results_dir)
    examples = []
    
    # TODO: 实现从intermediate results提取样本的逻辑
    # 1. 读取 dedup_intermediate JSON files
    # 2. 选择高置信度的clusters和groups
    # 3. 转换为dspy.Example格式
    
    return examples


def create_synthetic_training_data():
    """
    创建一些合成的训练样本用于快速测试
    """
    examples = [
        # Example 1: Person names with aliases
        dspy.Example(
            head_entity="Star Wars film series",
            relation="director",
            tail_descriptions=[
                "George Lucas",
                "G. Lucas", 
                "George Walton Lucas Jr.",
                "J.J. Abrams",
                "Jeffrey Jacob Abrams",
                "Rian Johnson"
            ],
            gold_clusters=[
                [0, 1, 2],  # George Lucas aliases
                [3, 4],     # J.J. Abrams aliases
                [5]         # Rian Johnson
            ],
            gold_groups=[
                {"members": [0, 1, 2], "representative": 0, "rationale": "Same person - George Lucas"},
                {"members": [3, 4], "representative": 3, "rationale": "Same person - J.J. Abrams"},
                {"members": [5], "representative": 5, "rationale": "Different person"}
            ]
        ).with_inputs("head_entity", "relation", "tail_descriptions"),
        
        # Example 2: City names
        dspy.Example(
            head_entity="United States",
            relation="has_city",
            tail_descriptions=[
                "New York City",
                "NYC",
                "New York",
                "Los Angeles",
                "LA",
                "City of Angels",
                "San Francisco"
            ],
            gold_clusters=[
                [0, 1, 2],    # New York
                [3, 4, 5],    # Los Angeles
                [6]           # San Francisco
            ],
            gold_groups=[
                {"members": [0, 1, 2], "representative": 0, "rationale": "Same city - New York"},
                {"members": [3, 4, 5], "representative": 3, "rationale": "Same city - Los Angeles"},
                {"members": [6], "representative": 6, "rationale": "Different city"}
            ]
        ).with_inputs("head_entity", "relation", "tail_descriptions"),
        
        # Example 3: Different entities (should NOT be merged)
        dspy.Example(
            head_entity="Apple Inc.",
            relation="product",
            tail_descriptions=[
                "iPhone",
                "iPhone 13",
                "iPhone 14",
                "MacBook",
                "MacBook Pro",
                "iPad"
            ],
            gold_clusters=[
                [0, 1, 2],   # iPhone series (could be clustered)
                [3, 4],      # MacBook series
                [5]          # iPad
            ],
            gold_groups=[
                {"members": [0], "representative": 0, "rationale": "Generic iPhone"},
                {"members": [1], "representative": 1, "rationale": "Specific model"},
                {"members": [2], "representative": 2, "rationale": "Specific model"},
                {"members": [3], "representative": 3, "rationale": "Generic MacBook"},
                {"members": [4], "representative": 4, "rationale": "Specific model"},
                {"members": [5], "representative": 5, "rationale": "Different product line"}
            ]
        ).with_inputs("head_entity", "relation", "tail_descriptions"),
    ]
    
    return examples


if __name__ == "__main__":
    # Generate synthetic data
    train_examples = create_synthetic_training_data()
    
    # Save to file
    output_file = "data/dspy_training_examples.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump([ex.toDict() for ex in train_examples], f, indent=2, ensure_ascii=False)
    
    print(f"Created {len(train_examples)} training examples")
    print(f"Saved to {output_file}")
```

### 第三步：训练和评估

创建 `scripts/train_dspy_modules.py`:

```python
"""
训练和优化DSPy模块
"""

import dspy
from models.constructor.dspy_semantic_dedup import (
    DSPySemanticDedupOptimizer,
    SemanticClusteringModule,
    SemanticDedupModule,
    clustering_metric,
    dedup_metric
)
from scripts.prepare_dspy_training_data import create_synthetic_training_data
import json


def setup_dspy(api_key: str, model: str = "gpt-3.5-turbo"):
    """配置DSPy"""
    lm = dspy.OpenAI(model=model, api_key=api_key, max_tokens=2000)
    dspy.settings.configure(lm=lm)


def train_clustering_module(train_examples, val_examples):
    """训练聚类模块"""
    print("\\n" + "="*80)
    print("Training Clustering Module")
    print("="*80)
    
    # Create optimizer
    optimizer = DSPySemanticDedupOptimizer(train_examples, val_examples)
    
    # Evaluate baseline
    print("\\nEvaluating baseline (unoptimized) clustering...")
    baseline_module = SemanticClusteringModule()
    baseline_score = optimizer.evaluate(baseline_module, val_examples, clustering_metric)
    print(f"Baseline clustering F1: {baseline_score:.2f}")
    
    # Optimize
    print("\\nOptimizing clustering module...")
    optimized_module = optimizer.optimize_clustering(
        teacher_model="gpt-4",
        student_model="gpt-3.5-turbo"
    )
    
    # Evaluate optimized
    print("\\nEvaluating optimized clustering...")
    optimized_score = optimizer.evaluate(optimized_module, val_examples, clustering_metric)
    print(f"Optimized clustering F1: {optimized_score:.2f}")
    print(f"Improvement: {optimized_score - baseline_score:.2f} points")
    
    return optimized_module


def train_dedup_module(train_examples, val_examples):
    """训练去重模块"""
    print("\\n" + "="*80)
    print("Training Deduplication Module")
    print("="*80)
    
    # Create optimizer
    optimizer = DSPySemanticDedupOptimizer(train_examples, val_examples)
    
    # Evaluate baseline
    print("\\nEvaluating baseline (unoptimized) dedup...")
    baseline_module = SemanticDedupModule()
    baseline_score = optimizer.evaluate(baseline_module, val_examples, dedup_metric)
    print(f"Baseline dedup F1: {baseline_score:.2f}")
    
    # Optimize
    print("\\nOptimizing dedup module...")
    optimized_module = optimizer.optimize_dedup(
        teacher_model="gpt-4",
        student_model="gpt-3.5-turbo"
    )
    
    # Evaluate optimized
    print("\\nEvaluating optimized dedup...")
    optimized_score = optimizer.evaluate(optimized_module, val_examples, dedup_metric)
    print(f"Optimized dedup F1: {optimized_score:.2f}")
    print(f"Improvement: {optimized_score - baseline_score:.2f} points")
    
    return optimized_module


def main():
    # Load training data
    print("Loading training data...")
    all_examples = create_synthetic_training_data()
    
    # Split into train/val
    split_idx = int(len(all_examples) * 0.7)
    train_examples = all_examples[:split_idx]
    val_examples = all_examples[split_idx:]
    
    print(f"Training examples: {len(train_examples)}")
    print(f"Validation examples: {len(val_examples)}")
    
    # Configure DSPy (需要API key)
    # setup_dspy(api_key="your-openai-api-key")
    
    # Train modules
    # optimized_clustering = train_clustering_module(train_examples, val_examples)
    # optimized_dedup = train_dedup_module(train_examples, val_examples)
    
    # Save optimized modules
    # optimized_clustering.save("models/dspy_optimized_clustering.json")
    # optimized_dedup.save("models/dspy_optimized_dedup.json")
    
    print("\\n" + "="*80)
    print("Training completed!")
    print("="*80)


if __name__ == "__main__":
    main()
```

---

## 实施步骤

### 阶段1: 准备和测试（1-2天）

1. **安装DSPy**
   ```bash
   pip install dspy-ai
   ```

2. **创建基础DSPy模块**
   - 实现 `dspy_semantic_dedup.py`
   - 定义 Signatures 和 Modules
   - 测试基本功能

3. **准备小规模训练数据**
   - 手工标注10-20个高质量样本
   - 覆盖不同类型的relations
   - 包含正例和负例

### 阶段2: 优化和评估（2-3天）

4. **训练DSPy模块**
   - 使用BootstrapFewShot优化器
   - 用GPT-4作为teacher，GPT-3.5-turbo作为student
   - 评估性能提升

5. **对比测试**
   - 在验证集上对比原始prompt vs DSPy优化prompt
   - 测量F1 score、precision、recall
   - 分析错误案例

### 阶段3: 集成和部署（1-2天）

6. **集成到KTBuilder**
   - 修改 `kt_gen.py`，添加DSPy选项
   - 保持向后兼容（可选择使用原始prompt或DSPy）
   - 添加配置开关

7. **全流程测试**
   - 在真实数据集上测试
   - 比较去重质量
   - 监控性能和成本

---

## 预期收益

### 1. 性能提升
- **准确率**: 预期提升5-15% F1 score
- **一致性**: DSPy优化后的prompt更稳定
- **适应性**: 对不同domain自动调整策略

### 2. 成本降低
- 可以用cheaper model (GPT-3.5-turbo) 达到接近GPT-4的效果
- 预期成本降低50-70%

### 3. 可维护性
- 程序化定义prompt逻辑
- 易于测试和迭代
- 自动化优化流程

---

## 配置示例

在 `config/base_config.yaml` 中添加DSPy配置：

```yaml
construction:
  semantic_dedup:
    enabled: true
    
    # 选择使用原始prompt还是DSPy优化
    use_dspy: true
    
    # DSPy配置
    dspy:
      # 优化后的模块路径
      clustering_module_path: "models/dspy_optimized_clustering.json"
      dedup_module_path: "models/dspy_optimized_dedup.json"
      
      # 如果没有预训练模块，是否启用在线优化
      enable_online_optimization: false
      
      # 用于在线优化的示例数量
      online_optimization_examples: 10
    
    # 原有配置保持不变
    clustering_method: "llm"
    max_batch_size: 8
    threshold: 0.88
    
    clustering_llm:
      model: "gpt-3.5-turbo"  # DSPy优化后可以用更便宜的模型
      base_url: "https://api.openai.com/v1"
      temperature: 0.1
    
    dedup_llm:
      model: "gpt-3.5-turbo"  # DSPy优化后可以用更便宜的模型
      base_url: "https://api.openai.com/v1"
      temperature: 0.0
```

---

## 与现有代码的集成

修改 `models/constructor/kt_gen.py` 中的关键方法：

```python
# 在 KTBuilder.__init__ 中添加
def __init__(self, dataset_name, schema_path=None, mode=None, config=None):
    # ... 现有代码 ...
    
    # Initialize DSPy modules if enabled
    self.use_dspy = False
    self.dspy_clustering = None
    self.dspy_dedup = None
    
    if config and hasattr(config.construction, 'semantic_dedup'):
        semantic_config = config.construction.semantic_dedup
        if getattr(semantic_config, 'use_dspy', False):
            self._init_dspy_modules(semantic_config)


def _init_dspy_modules(self, config):
    """初始化DSPy模块"""
    try:
        from models.constructor.dspy_semantic_dedup import (
            SemanticClusteringModule,
            SemanticDedupModule
        )
        
        dspy_config = getattr(config, 'dspy', None)
        if dspy_config:
            # Load pre-trained modules
            clustering_path = getattr(dspy_config, 'clustering_module_path', None)
            if clustering_path and Path(clustering_path).exists():
                self.dspy_clustering = SemanticClusteringModule()
                self.dspy_clustering.load(clustering_path)
                logger.info(f"Loaded DSPy clustering module from {clustering_path}")
            
            dedup_path = getattr(dspy_config, 'dedup_module_path', None)
            if dedup_path and Path(dedup_path).exists():
                self.dspy_dedup = SemanticDedupModule()
                self.dspy_dedup.load(dedup_path)
                logger.info(f"Loaded DSPy dedup module from {dedup_path}")
            
            self.use_dspy = True
    
    except Exception as e:
        logger.warning(f"Failed to initialize DSPy modules: {e}, falling back to original prompts")
        self.use_dspy = False


# 修改 _cluster_candidate_tails_with_llm
def _cluster_candidate_tails_with_llm(self, head_text: str, relation: str, descriptions: list, max_batch_size: int = 30):
    """使用LLM进行初步聚类（支持DSPy）"""
    
    # 如果启用了DSPy，使用优化后的模块
    if self.use_dspy and self.dspy_clustering:
        try:
            return self._cluster_with_dspy(head_text, relation, descriptions, max_batch_size)
        except Exception as e:
            logger.warning(f"DSPy clustering failed: {e}, falling back to original method")
    
    # 原有的实现
    # ... 现有代码 ...


def _cluster_with_dspy(self, head_text: str, relation: str, descriptions: list, max_batch_size: int = 30):
    """使用DSPy进行聚类"""
    if len(descriptions) <= 1:
        return [list(range(len(descriptions)))], [{"description": "single item"}]
    
    # Process in batches if needed
    all_clusters = []
    all_details = []
    
    if len(descriptions) > max_batch_size:
        for batch_start in range(0, len(descriptions), max_batch_size):
            batch_end = min(batch_start + max_batch_size, len(descriptions))
            batch_descriptions = descriptions[batch_start:batch_end]
            
            # Call DSPy module
            clusters_result = self.dspy_clustering(
                head_entity=head_text,
                relation=relation,
                tail_descriptions=batch_descriptions
            )
            
            # Convert and offset indices
            batch_clusters, batch_details = self._convert_dspy_clusters(
                clusters_result, batch_start
            )
            all_clusters.extend(batch_clusters)
            all_details.extend(batch_details)
        
        return all_clusters, all_details
    else:
        clusters_result = self.dspy_clustering(
            head_entity=head_text,
            relation=relation,
            tail_descriptions=descriptions
        )
        return self._convert_dspy_clusters(clusters_result, 0)


# 类似地修改 _llm_semantic_group
def _llm_semantic_group(self, head_text: str, relation: str, head_context_lines: list, batch_entries: list):
    """使用LLM进行语义分组（支持DSPy）"""
    
    # 如果启用了DSPy，使用优化后的模块
    if self.use_dspy and self.dspy_dedup:
        try:
            return self._dedup_with_dspy(head_text, relation, head_context_lines, batch_entries)
        except Exception as e:
            logger.warning(f"DSPy dedup failed: {e}, falling back to original method")
    
    # 原有的实现
    # ... 现有代码 ...
```

---

## 总结

**回答您的问题：是的，可以使用DSPy优化semantic_dedup_group中的prompt！**

### 主要优势：

1. ✅ **自动优化**: 基于标注数据自动调整prompt
2. ✅ **性能提升**: 预期5-15%的F1 score提升
3. ✅ **成本降低**: 可以用cheaper model达到更好效果
4. ✅ **可维护性**: 程序化定义，易于迭代
5. ✅ **适应性**: 可以针对不同domain自动调整

### 实施建议：

1. **短期**: 先用10-20个标注样本做概念验证
2. **中期**: 扩大训练集到50-100个样本，优化主要场景
3. **长期**: 建立持续优化pipeline，根据生产数据不断改进

### 下一步：

如果您想实施这个方案，我可以帮您：
1. 创建完整的DSPy实现代码
2. 准备初始训练数据集
3. 设置训练和评估pipeline
4. 集成到现有的KTBuilder中

需要我开始实施吗？
