# Head Deduplication 层级关系误判修复

## 问题描述

### 用户报告的案例

LLM 将以下两个实体判断为应该合并：

```json
{
  "duplicate_name": "伪影",
  "canonical_name": "魔角伪影",
  "metadata": {
    "rationale": "（1）指称同一性：两条实体均描述'当肌腱、韧带等平行纤维结构与主磁场成约55°夹角时，MRI短TE序列出现信号增强、易被误诊为病理'的物理现象...",
    "confidence": 1.0,
    "embedding_similarity": 0.8474055758000711,
    "method": "llm_v2",
    "llm_chosen_representative": "entity_188"
  }
}
```

### 问题分析

**这是一个严重的误判！**

- **"伪影"**：通用概念，泛指所有 MRI 伪影（流动伪影、化学位移伪影、魔角伪影等）
- **"魔角伪影"**：特定类型的伪影，是"伪影"的一个子类

这是典型的**上下位关系**（hierarchical relationship），根据 Information Identity 原则，**绝对不应该合并**！

### 为什么 LLM 会误判？

#### 1. **过度依赖 chunk context 的局部相似性**

如果两个实体在相同或相似的 chunk 中被讨论：

```
原文："魔角伪影是MRI成像中的一种伪影，出现在肌腱与主磁场成55°夹角时..."
```

LLM 看到两个实体都在描述"55°夹角、肌腱、信号增强"等相同特征，被这种**局部文本一致性**误导，认为它们指称同一对象。

#### 2. **没有充分重视名称本身的语义信息**

名称差异携带关键信息：
- "伪影" vs "魔角伪影"
- "魔角伪影" = "魔角" + "伪影"（修饰词 + 基础概念）

这不是简单的缩写或别名，而是**明显的特定化**（specialization）关系。

#### 3. **双向替换测试没有正确执行**

虽然 prompt 要求双向替换测试，但 LLM 可能没有意识到：

**Test A: "伪影" → "魔角伪影"**
```
原文："MRI成像中的伪影有多种类型，包括流动伪影、化学位移伪影等"
替换："MRI成像中的魔角伪影有多种类型，包括流动伪影、化学位移伪影等"
```
❌ **严重的信息损失**：丢失了通用性，从"所有伪影"变成"特指魔角伪影"

**Test B: "魔角伪影" → "伪影"**
```
原文："魔角伪影出现在肌腱与主磁场成55°夹角时"
替换："伪影出现在肌腱与主磁场成55°夹角时"
```
❌ **严重的信息损失**：丢失了特定性，读者无法知道是哪种伪影

## 解决方案

### 核心改进：添加 STEP 1 - 名称语义分析

在检查上下文之前，**先分析名称本身**，识别层级关系：

```
STEP 1: NAME SEMANTIC ANALYSIS (CRITICAL)

Before checking contexts, analyze the NAMES themselves:

Question: Do the names reveal a hierarchical or specialization relationship?

CRITICAL PATTERNS TO DETECT:

Pattern 1: Generic vs Specific
  • "X" vs "[Modifier] + X" → HIERARCHICAL, KEEP SEPARATE
  Examples:
    - "伪影" vs "魔角伪影" ❌ (generic artifact vs specific type)
    - "带宽" vs "读出带宽" ❌ (generic vs specific bandwidth)
    - "癌症" vs "肺癌" ❌ (generic vs specific cancer)

Pattern 2: Base Concept vs Specialized Term
  • Entity 1 name is a SUBSTRING of Entity 2 name → Likely hierarchical
  • Entity 2 = [Modifier] + Entity 1 → Entity 2 is a SUBTYPE of Entity 1

⚠️ CRITICAL RULE:
If one entity name is clearly a SPECIALIZATION of the other:
  → They are in HIERARCHICAL relationship
  → OUTPUT: is_coreferent = false, STOP immediately
  → Do NOT proceed to context analysis

Why? Because:
- Generic term ("伪影") refers to ALL types of artifacts
- Specific term ("魔角伪影") refers to ONE type
- They refer to DIFFERENT SCOPE of objects
- Merging them loses critical categorical information
```

### 改进 2：强调上下文相似性不足以判断合并

```
STEP 2: REFERENTIAL IDENTITY CHECK (only if Step 1 passed)

⚠️ CONTEXT SIMILARITY IS NOT ENOUGH:
- If two entities appear in similar contexts, it does NOT mean they are the same
- "伪影" and "魔角伪影" might be discussed together, but they are NOT the same
- Similar usage patterns do NOT override name semantic differences
```

### 改进 3：添加明确的层级关系示例

```
Example 3 - Hierarchical Relationship (KEEP SEPARATE):
  Entity A: "伪影" (artifact - generic)
  Entity B: "魔角伪影" (magic angle artifact - specific type)
  
  NAME ANALYSIS:
    "魔角伪影" = "魔角" + "伪影"
    → Entity B is a SPECIALIZATION of Entity A
    → HIERARCHICAL relationship detected
  
  SCOPE ANALYSIS:
    Entity A: Refers to ALL types of MRI artifacts (流动伪影, 化学位移伪影, 魔角伪影, etc.)
    Entity B: Refers to ONE specific type (magic angle artifact only)
  
  SUBSTITUTION TEST:
    A→B: "MRI中的伪影包括多种类型" → "MRI中的魔角伪影包括多种类型"
          Information loss? YES, loses generic scope ✗
    B→A: "魔角伪影出现在55°角时" → "伪影出现在55°角时"
          Information loss? YES, loses type specificity ✗
  
  Result: HIERARCHICAL → KEEP SEPARATE
  
  CRITICAL: Even if they appear in similar contexts or are discussed together,
  they represent different LEVELS of abstraction and must remain separate.
```

### 改进 4：增强保守原则

```
CONSERVATIVE PRINCIPLE:

CRITICAL WARNINGS:
⚠️ Do NOT merge entities just because they appear in similar contexts
⚠️ Do NOT merge entities just because they are discussed together
⚠️ Do NOT let context similarity override clear name semantic differences
⚠️ Always prioritize NAME SEMANTICS over CONTEXT SIMILARITY
```

## 修改的文件

1. **`head_dedup_llm_driven_representative.py`**
   - `_get_embedded_prompt_template_v2()` 方法中的 prompt

2. **`config/base_config.yaml`**
   - `prompts.head_dedup.with_representative_selection` 模板

## 预期效果

使用改进后的 prompt，LLM 应该：

1. **首先分析名称语义**：识别"魔角伪影"是"伪影"的特定化
2. **立即判断为层级关系**：不需要进入上下文分析
3. **输出**：`is_coreferent = false`，保持两个实体分离

### 示例输出（正确判断）

```json
{
  "is_coreferent": false,
  "substitution_lossless_1to2": null,
  "substitution_lossless_2to1": null,
  "information_identity": false,
  "preferred_representative": null,
  "rationale": "NAME SEMANTIC ANALYSIS: '魔角伪影' = '魔角' + '伪影'，Entity 2 是 Entity 1 的特定化。'伪影'是通用概念，指代所有MRI伪影类型；'魔角伪影'是特定类型，仅指一种伪影。这是明显的层级关系（hierarchical relationship）。根据 STEP 1 规则，检测到层级关系后应立即停止，不进行合并。双方指称的对象范围不同：Entity 1 涵盖多种伪影类型，Entity 2 仅指其中一种。"
}
```

## 类似案例

以下案例也应该被正确识别为层级关系，**不应合并**：

| Entity 1 (通用) | Entity 2 (特定) | 关系 |
|----------------|----------------|------|
| 伪影 | 魔角伪影 | 上下位 |
| 伪影 | 流动伪影 | 上下位 |
| 伪影 | 化学位移伪影 | 上下位 |
| 带宽 | 读出带宽 | 特定化 |
| 带宽 | 接收带宽 | 特定化 |
| 成像 | T1加权成像 | 特定化 |
| 癌症 | 肺癌 | 上下位 |
| MRI序列 | 梯度回波序列 | 上下位 |

## 测试建议

建议创建测试用例验证修复效果：

```python
def test_hierarchical_relationship_detection():
    """Test that generic vs specific entity pairs are not merged."""
    
    test_cases = [
        ("伪影", "魔角伪影", False),  # Should NOT merge
        ("伪影", "流动伪影", False),  # Should NOT merge
        ("带宽", "读出带宽", False),  # Should NOT merge
        ("UN", "United Nations", True),  # Should merge (synonym)
    ]
    
    for entity1, entity2, should_merge in test_cases:
        result = head_dedup_llm_v2(entity1, entity2)
        assert result["is_coreferent"] == should_merge
```

## 总结

通过添加**名称语义分析**步骤，并明确**名称语义优先于上下文相似性**的原则，我们可以有效避免将上下位关系误判为同指关系的问题。

这一改进确保了知识图谱保留重要的层级结构，避免信息损失。

---

**日期**: 2025-10-29  
**问题报告者**: User  
**修复者**: AI Assistant
