# 改进建议：移除LLM Confidence要求

**日期**: 2025-10-27  
**问题**: Head去重prompt要求LLM输出confidence，但这可能是不必要的  
**建议**: 参考现有tail去重的做法，移除confidence要求

---

## 🔍 问题发现

用户提出关键问题：
> "你在prompt中要求输出分数的要求的依据是什么，是因为当前的方法都是依据相似度来的么"

这个问题揭示了设计中的一个问题。

---

## 📊 现状分析

### 现有Tail去重（成熟、实战验证）

**Prompt输出**:
```json
{
  "groups": [
    {
      "members": [1, 3],
      "representative": 3,
      "rationale": "Why the members belong together."
    }
  ]
}
```
**✓ 没有confidence**

### 当前Head去重（新设计）

**Prompt输出**:
```json
{
  "is_coreferent": true/false,
  "confidence": 0.0-1.0,  ← 问题在这里
  "rationale": "Clear explanation"
}
```
**✗ 要求了confidence**

---

## ❌ 为什么confidence有问题？

### 1. LLM输出的confidence不可靠

**主观性强**:
```python
# 对同一个判断，不同LLM或同一LLM的不同运行
判断1: is_coreferent=true, confidence=0.92
判断2: is_coreferent=true, confidence=0.78
判断3: is_coreferent=true, confidence=0.85

# confidence差异大，但判断都是true
```

**没有校准**:
- LLM没有经过专门的confidence校准训练
- 0.92和0.78的实际差异无法解释
- 不同任务、不同数据集的confidence不可比

### 2. 与客观相似度混淆

**Embedding相似度（客观）**:
```python
# 数学计算，稳定可靠
similarity = cosine_similarity(emb1, emb2)  # 0.87
# 含义明确：向量夹角余弦值
# 可重复：每次计算结果一致
```

**LLM Confidence（主观）**:
```python
# LLM估计，不稳定
confidence = llm_output["confidence"]  # 0.87?
# 含义模糊：LLM"觉得"的把握度
# 不可重复：每次可能不同
```

**我犯的错误**: 把两者等同了，以为都可以作为threshold判断依据。

### 3. 与现有实践不一致

**Tail去重**:
```python
# 经过实战检验的做法
def _deduplicate_exact(self, ...):
    # LLM只负责分组，不输出confidence
    groups = llm_output["groups"]
    for group in groups:
        merge_group(group["members"], group["representative"])
```

**Head去重**（当前）:
```python
# 我设计的做法
def _validate_candidates_with_llm(self, ...):
    is_coreferent = llm_output["is_coreferent"]
    confidence = llm_output["confidence"]  # ← 多余的
    
    if is_coreferent and confidence >= threshold:  # ← 可疑的判断
        merge()
```

如果tail去重不需要confidence，为什么head去重需要？

### 4. 增加Prompt复杂度

**当前prompt**:
```yaml
OUTPUT FORMAT (strict JSON):
{
  "is_coreferent": true/false,
  "confidence": 0.0-1.0,  # ← 需要额外解释
  "rationale": "..."
}

# 需要解释：
# - confidence是什么？
# - 如何评估confidence？
# - 0.8和0.9有什么区别？
```

**简化后**:
```yaml
OUTPUT FORMAT (strict JSON):
{
  "is_coreferent": true/false,
  "rationale": "..."
}

# 简单明了，LLM只需判断是/否
```

---

## ✅ 改进方案

### 方案A: 完全移除confidence（推荐）⭐

#### Prompt改进

```yaml
prompts:
  head_dedup:
    general: |-
      You are an expert in knowledge graph entity resolution.
      
      TASK: Determine if the following two entities refer to the SAME real-world object.
      
      Entity 1: {entity_1}
      Related knowledge about Entity 1:
      {context_1}
      
      Entity 2: {entity_2}
      Related knowledge about Entity 2:
      {context_2}
      
      CRITICAL RULES:
      1. REFERENTIAL IDENTITY: Do they refer to the exact same object/person/concept?
      2. SUBSTITUTION TEST: Can you replace one with the other without changing meaning?
      3. TYPE CONSISTENCY: Check entity types/categories
      4. CONSERVATIVE PRINCIPLE: When uncertain → answer NO
      
      OUTPUT FORMAT (strict JSON):
      {
        "is_coreferent": true/false,
        "rationale": "Clear explanation based on referential identity test"
      }
      
      # 移除了confidence字段
```

#### 代码改进

```python
def _validate_candidates_with_llm(self, candidates, threshold=0.85):
    """Validate candidate pairs using LLM.
    
    Args:
        candidates: List of (node_id_1, node_id_2, embedding_similarity)
        threshold: Not used for LLM (kept for API compatibility)
    """
    # ... 构建prompts ...
    
    responses = self._concurrent_llm_calls(prompts, return_json=True)
    
    merge_mapping = {}
    metadata = {}
    
    for response, meta in zip(responses, candidates_meta):
        parsed = self._parse_coreference_response(response)
        
        # 简化判断逻辑
        if parsed.get("is_coreferent", False):
            node_id_1 = meta["node_id_1"]
            node_id_2 = meta["node_id_2"]
            
            merge_mapping[node_id_1] = {
                "merge_into": node_id_2,
                "rationale": parsed.get("rationale", ""),
                "embedding_similarity": meta.get("embedding_similarity", 0.0),
                "method": "llm"
            }
    
    return merge_mapping, metadata


def _parse_coreference_response(self, response: str) -> dict:
    """Parse LLM response for entity coreference."""
    try:
        parsed = json.loads(response)
        return {
            "is_coreferent": bool(parsed.get("is_coreferent", False)),
            "rationale": str(parsed.get("rationale", ""))
            # 移除了confidence
        }
    except Exception as e:
        logger.warning(f"Failed to parse coreference response: {e}")
        return {
            "is_coreferent": False,
            "rationale": "Parse error"
        }
```

#### Human Review改进

不基于LLM的confidence（不可靠），而基于embedding相似度（客观）：

```python
def export_head_merge_candidates_for_review(
    self,
    output_path: str,
    min_similarity: float = 0.70,  # 改用embedding相似度
    max_similarity: float = 0.90
):
    """Export merge candidates for human review.
    
    Args:
        output_path: Output CSV file path
        min_similarity: Minimum embedding similarity (inclusive)
        max_similarity: Maximum embedding similarity (inclusive)
    
    Exports candidates with medium embedding similarity for human review.
    High similarity (>0.90): Auto-merge, likely correct
    Medium similarity (0.70-0.90): Human review needed
    Low similarity (<0.70): Auto-reject, likely incorrect
    """
    logger.info(f"Exporting head merge candidates (similarity: {min_similarity}-{max_similarity})...")
    
    candidates = []
    
    for node_id, data in self.graph.nodes(data=True):
        if data.get("label") == "entity":
            merge_history = data.get("properties", {}).get("head_dedup", {}).get("merge_history", [])
            
            for merge_record in merge_history:
                # 使用客观的embedding相似度，而不是LLM的主观confidence
                similarity = merge_record.get("embedding_similarity", 1.0)
                
                if min_similarity <= similarity <= max_similarity:
                    candidates.append({
                        "canonical_node_id": node_id,
                        "canonical_name": data.get("properties", {}).get("name", ""),
                        "merged_node_ids": ",".join(merge_record.get("merged_from", [])),
                        "embedding_similarity": similarity,  # 客观指标
                        "method": merge_record.get("method", "unknown"),
                        "rationale": merge_record["rationale"]
                    })
    
    # 按相似度排序，优先审核边界案例
    candidates.sort(key=lambda x: abs(x["embedding_similarity"] - 0.80))
    
    # 导出CSV
    # ...
```

---

### 方案B: 保留但不使用（折中）

如果担心完全移除会丢失信息：

```yaml
OUTPUT FORMAT (strict JSON):
{
  "is_coreferent": true/false,
  "rationale": "...",
  "confidence_note": "optional subjective estimate, not used for decision"
}
```

```python
# 代码中只看is_coreferent，不使用confidence
if parsed.get("is_coreferent", False):
    merge()  # 不检查confidence

# confidence只记录，不判断
metadata[pair] = {
    "llm_confidence_note": parsed.get("confidence_note", ""),  # 仅供参考
    "embedding_similarity": similarity  # 用这个做判断
}
```

---

## 📊 对比总结

| 维度 | 当前方案（有confidence）| 方案A（无confidence）| 方案B（有但不用）|
|------|---------------------|-------------------|----------------|
| **Prompt复杂度** | 高（需解释confidence）| 低 | 中 |
| **LLM负担** | 重（判断+估计把握）| 轻（只判断）| 中 |
| **输出稳定性** | 低（confidence波动）| 高 | 中 |
| **与tail一致性** | 不一致 | 一致 ✓ | 中 |
| **Human review依据** | LLM confidence（不可靠）| Embedding similarity（可靠）✓ | 可靠 ✓ |
| **代码复杂度** | 高 | 低 ✓ | 中 |

**推荐**: 方案A（完全移除）⭐

---

## 🎯 实施建议

### 立即改进（优先级高）

1. **修改prompt**
   - 移除confidence字段
   - 简化输出格式

2. **修改代码**
   - `_validate_candidates_with_llm`: 移除confidence判断
   - `_parse_coreference_response`: 移除confidence解析
   - `export_head_merge_candidates_for_review`: 改用embedding_similarity

3. **更新配置**
   ```yaml
   head_dedup:
     # 移除confidence相关配置
     # review_confidence_range: [0.70, 0.90]  # 删除
     review_similarity_range: [0.70, 0.90]  # 新增
   ```

### 后续优化（优先级中）

1. **Human review策略**
   ```python
   # 基于多个客观指标
   if method == "llm":
       # LLM判断的，看embedding相似度
       if 0.70 <= embedding_similarity <= 0.90:
           export_for_review()
   
   elif method == "embedding":
       # Embedding判断的，看相似度和关系匹配度
       if 0.75 <= similarity <= 0.88:
           if relation_match_ratio < 0.6:  # 关系匹配少
               export_for_review()
   ```

2. **可解释性增强**
   ```python
   # 而不是依赖LLM的confidence
   merge_quality = {
       "embedding_similarity": 0.87,
       "common_relations": ["capital_of", "located_in"],
       "conflicting_relations": [],
       "llm_rationale": "Both refer to the same city"
   }
   ```

---

## 🤔 为什么我最初加了confidence？

### 反思

1. **类比错误**
   ```python
   # Embedding有分数
   similarity = 0.87
   if similarity > threshold:
       merge()
   
   # 我想LLM也有分数
   confidence = 0.87  # ← 错误类比
   if is_coreferent and confidence > threshold:
       merge()
   ```

2. **过度设计**
   想象了一个"confidence区间人工审核"的机制，但：
   - LLM confidence不可靠
   - 现有tail去重不需要
   - Embedding similarity已足够

3. **忽略先例**
   没有仔细参考tail去重的成熟做法

---

## ✅ 正确理解

### Embedding相似度 ≠ LLM Confidence

| 指标 | Embedding Similarity | LLM Confidence |
|------|---------------------|----------------|
| 性质 | 客观计算 | 主观估计 |
| 稳定性 | 高（每次一样）| 低（每次可能不同）|
| 可解释性 | 向量夹角余弦值 | LLM"感觉"的把握度 |
| 可比性 | 可比（0-1连续值）| 不可比（LLM间不同）|
| 用途 | ✓ 作为阈值判断 | ✗ 不适合阈值判断 |
| 用途 | ✓ Human review依据 | ✗ 不适合 |

### LLM的正确角色

**应该做**:
- ✓ 定性判断：是/否
- ✓ 给出理由：rationale
- ✓ 处理复杂情况：Embedding处理不了的

**不应该做**:
- ✗ 定量估计：confidence分数
- ✗ 作为阈值判断依据
- ✗ 作为human review筛选依据

### 正确的Pipeline

```
阶段1: Exact Matching
  → 名称标准化完全匹配
  → 置信度: 100%（确定性高）

阶段2: Embedding Filtering
  → 计算向量相似度
  → 高相似度(>0.90): 直接合并
  → 中相似度(0.70-0.90): LLM验证或人工审核
  → 低相似度(<0.70): 不合并

阶段3: LLM Validation (可选)
  → 对中等相似度的候选对
  → LLM给出 is_coreferent (是/否) + rationale (理由)
  → 不要求confidence！

阶段4: Human Review
  → 基于embedding similarity（客观）
  → 不基于LLM confidence（主观）
  → 导出0.70-0.90相似度的案例
```

---

## 📝 结论

用户的问题非常有价值，指出了设计中的一个关键问题：

**问题**: 为什么要求LLM输出confidence？  
**答案**: 没有充分理由，这是一个设计失误

**根本原因**: 
- 把Embedding的客观相似度和LLM的主观confidence混淆了
- 没有参考现有tail去重的成熟做法
- 过度设计了基于confidence的review机制

**改进建议**:
- ✅ 移除prompt中的confidence要求
- ✅ 代码只判断is_coreferent，不判断confidence
- ✅ Human review基于embedding similarity
- ✅ 与tail去重的做法保持一致

---

**状态**: 改进建议  
**优先级**: 中（不影响功能，但可以简化设计）  
**实施难度**: 低（主要是prompt和少量代码修改）

---

**感谢用户提出这个问题！** 这种质疑帮助我们发现设计中的不合理之处。
