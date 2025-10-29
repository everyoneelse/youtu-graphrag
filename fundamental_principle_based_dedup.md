# 基于根本原则的Head Dedup方案

## 问题反思

### 我之前的错误

```yaml
❌ 三级判断方案:
  - 检查5个维度（specificity, detail level, formality...）
  - 数concerns数量
  - 根据数量决定策略（0-1→merge, 2-3→alias, 4+→separate）
  
问题：这是case by case的规则堆砌，不是原则性设计
```

### 用户的正确观点

```
应该按照初衷：
1. 实体包含的信息是否完全一致
2. 替换测试是否没有信息遗漏
```

**这才是根本原则！**

## 根本原则：信息完全一致性 (Information Identity)

### 核心问题

只需要回答一个问题：

```
两个实体包含的信息是否完全一致？
```

如果一致 → 合并  
如果不一致 → 不合并

**就这么简单！**

### 什么叫"信息完全一致"？

```
定义：Information Identity

两个实体A和B信息完全一致，当且仅当：

1. 指称相同（Referential Identity）
   - A和B指向同一个真实世界对象
   
2. 替换无损（Substitution Completeness）
   - 在任何上下文中，用B替换A不会丢失信息
   - 在任何上下文中，用A替换B不会丢失信息
   - 即：替换是完全对称的
   
如果满足以上两点，A和B是完全相同的实体，应该合并。
如果不满足，它们包含不同的信息，不应该合并。
```

### 为什么这个原则是根本性的？

因为它直接回答了去重的本质问题：
- **去重的目的**：消除冗余
- **什么是冗余**：包含完全相同信息的重复
- **什么不是冗余**：包含不同信息的实体

```
如果A和B信息不完全一致 → 它们不是冗余 → 不应该去重
```

## 简化的Prompt设计

### 核心原则

不需要复杂的规则，只需要清楚地阐述"信息完全一致"的含义：

```
FUNDAMENTAL PRINCIPLE: Information Identity

Two entities should be merged if and only if they contain EXACTLY THE SAME INFORMATION.

DEFINITION - Information Identity:

Entities A and B have information identity when:

1. REFERENTIAL IDENTITY (指称相同)
   They refer to the exact same real-world object/concept
   
2. SUBSTITUTION COMPLETENESS (替换无损)
   In ANY context:
   - Replacing A with B preserves ALL information
   - Replacing B with A preserves ALL information
   - The substitution is SYMMETRIC and COMPLETE

If BOTH conditions hold → MERGE (they are duplicates)
If ANY condition fails → KEEP SEPARATE (they contain different information)

═══════════════════════════════════════════════════════════

HOW TO CHECK SUBSTITUTION COMPLETENESS:

Ask: "If I replace entity A with entity B in its source context, 
     is there ANY information loss?"

Information loss includes:
- Loss of precision (精确度损失)
- Loss of detail (细节损失)  
- Loss of specificity (明确性损失)
- Loss of any distinguishing information (任何区分性信息的损失)

Example 1 - SYMMETRIC (should merge):
  A: "United Nations"
  B: "UN"
  
  A→B: "The United Nations voted" → "The UN voted"
       No information loss ✓
  
  B→A: "The UN voted" → "The United Nations voted"  
       No information loss ✓
  
  Conclusion: Information identity ✓ → MERGE

Example 2 - ASYMMETRIC (should NOT merge):
  A: "增加读出带宽" (specific: readout bandwidth)
  B: "加大带宽" (vague: which bandwidth?)
  
  A→B: "通过增加读出带宽解决" → "通过加大带宽解决"
       Information loss: specificity lost (哪个带宽不明确了) ✗
  
  B→A: "解决方法：加大带宽" → "解决方法：增加读出带宽"
       No information loss (even adds precision) ✓
  
  ASYMMETRIC → Not information identity ✗ → KEEP SEPARATE

Example 3 - DIFFERENT CONTEXTS (should NOT merge):
  A: "提高带宽" in context of "解决流动伪影"
  B: "提高带宽" in context of "解决化学位移伪影"
  
  Even if the operation is similar, the CONTEXTUAL INFORMATION differs:
  - A is bound to "flow artifacts problem"
  - B is bound to "chemical shift problem"
  
  Replacing A with B in "流动伪影的解决方案" loses the specific binding
  → Not information identity ✗ → KEEP SEPARATE

═══════════════════════════════════════════════════════════

CONSERVATIVE PRINCIPLE:

When uncertain whether substitution is truly lossless:
→ Err on the side of preserving information
→ Keep entities separate

Rationale: False negatives (missing a merge) are better than 
false positives (losing information by over-merging).

═══════════════════════════════════════════════════════════

DECISION PROCEDURE:

Step 1: Check referential identity
   Q: Do they refer to the exact same object?
   - Use graph evidence (relationships, community)
   - Use text evidence (source contexts)
   - Apply common sense reasoning
   
   If NO → Output: is_coreferent = false, DONE

Step 2: Check substitution completeness  
   Q: Is substitution information-preserving in BOTH directions?
   
   2a. Test A→B in A's contexts
       - Any precision loss?
       - Any detail loss?
       - Any specificity loss?
       
   2b. Test B→A in B's contexts
       - Any precision loss?
       - Any detail loss?
       - Any specificity loss?
   
   2c. Evaluate symmetry
       - If BOTH directions are lossless → SYMMETRIC ✓
       - If EITHER direction has loss → ASYMMETRIC ✗
   
   If SYMMETRIC → Information identity ✓ → MERGE
   If ASYMMETRIC → Different information ✗ → KEEP SEPARATE

Step 3: Choose representative (only if merging)
   Based on: formality, completeness, domain convention
   
═══════════════════════════════════════════════════════════
```

### Prompt模板

```
You are an expert in knowledge graph entity deduplication.

TASK: Determine if two entities contain EXACTLY THE SAME INFORMATION.

Entity 1 (ID: {entity_1_id}): {entity_1_desc}
Graph relationships:
{graph_context_1}
Source text:
{chunk_context_1}

Entity 2 (ID: {entity_2_id}): {entity_2_desc}
Graph relationships:
{graph_context_2}
Source text:
{chunk_context_2}

═══════════════════════════════════════════════════════════

FUNDAMENTAL PRINCIPLE: Information Identity

Merge if and only if entities contain EXACTLY THE SAME INFORMATION.

Two conditions must BOTH be satisfied:

1. REFERENTIAL IDENTITY: Same real-world object
2. SUBSTITUTION COMPLETENESS: Replacement is lossless in BOTH directions

═══════════════════════════════════════════════════════════

STEP 1: REFERENTIAL IDENTITY CHECK

Do Entity 1 and Entity 2 refer to the EXACT SAME real-world object/concept?

Analyze using:
- Graph evidence: Do they have similar/compatible relationships?
- Text evidence: Do source contexts indicate same object?
- Domain knowledge: Are they known to be the same in this domain?

Apply tests:
- REFERENT TEST: Do they denote the same object?
- CONTRADICTION TEST: Is there ANY conflicting evidence?

If referentially different → STOP, output is_coreferent = false

═══════════════════════════════════════════════════════════

STEP 2: SUBSTITUTION COMPLETENESS CHECK

Assuming they refer to the same object, do they contain the SAME INFORMATION?

Test A: Entity 1 → Entity 2 substitution
  - Take Entity 1's source context
  - Replace Entity 1 with Entity 2's name/description
  - Question: Is there ANY information loss?
    * Precision loss? (specific → vague)
    * Detail loss? (detailed → simplified)
    * Contextual binding loss? (specific scenario → generic)
  - Verdict: Lossless YES/NO

Test B: Entity 2 → Entity 1 substitution
  - Take Entity 2's source context
  - Replace Entity 2 with Entity 1's name/description
  - Question: Is there ANY information loss?
  - Verdict: Lossless YES/NO

Symmetry evaluation:
  - If Test A = Lossless AND Test B = Lossless
    → SYMMETRIC substitution → Information identity ✓
    
  - If Test A = Loss OR Test B = Loss
    → ASYMMETRIC substitution → Different information ✗

CRITICAL: Even one direction having loss means they contain different information.

═══════════════════════════════════════════════════════════

STEP 3: DECISION

If Referential Identity = NO
  → Decision: KEEP SEPARATE (different objects)

If Referential Identity = YES but Substitution Completeness = NO
  → Decision: KEEP SEPARATE (same object but different information about it)

If Referential Identity = YES and Substitution Completeness = YES
  → Decision: MERGE (true duplicates with identical information)
  → Choose representative based on: formality, completeness, convention

═══════════════════════════════════════════════════════════

IMPORTANT REMINDERS:

1. INFORMATION PRESERVATION is paramount
   - When in doubt about information loss → DO NOT MERGE
   - False negative (missing a merge) > False positive (losing information)

2. CONTEXT MATTERS
   - Same term in different problem contexts may carry different information
   - Check if entities are bound to specific scenarios/problems

3. SUBSTITUTION MUST BE TRULY SYMMETRIC
   - Not just "similar meaning"
   - Must be completely interchangeable without ANY information loss

4. PRECISION DIFFERENCES = INFORMATION DIFFERENCES
   - "Specific term" vs "vague term" → Different information content
   - Even if they refer to the same object

═══════════════════════════════════════════════════════════

OUTPUT FORMAT (strict JSON):

{
  "is_coreferent": true/false,
  "substitution_lossless_1to2": true/false/null,
  "substitution_lossless_2to1": true/false/null,
  "information_identity": true/false,
  "preferred_representative": "{entity_1_id}" or "{entity_2_id}" or null,
  "rationale": "UNIFIED analysis: (1) Referential identity check with evidence; (2) Substitution completeness test - explicitly test BOTH directions and identify ANY information loss; (3) Final decision with clear reasoning based on information identity principle."
}

NOTES:
- Set substitution_lossless_* to null if is_coreferent = false
- Set information_identity = true only if BOTH substitution tests are lossless
- Set preferred_representative only if information_identity = true
- In rationale, explicitly describe what information would be lost (if any) in each substitution direction
```

## 对比：原则 vs 规则

### 规则驱动方法（我之前的错误）

```yaml
检查清单：
  ✓ Specificity difference?
  ✓ Detail level difference?
  ✓ Formality difference?
  ✓ Relationship difference?
  ✓ Audience difference?

规则：
  - If 0-1 differences → merge
  - If 2-3 differences → alias
  - If 4+ differences → separate

问题：
  - 需要不断添加新规则（case by case）
  - 规则之间可能冲突
  - 难以覆盖所有情况
  - 不够根本
```

### 原则驱动方法（正确方法）

```yaml
唯一原则：
  信息是否完全一致？

判断方法：
  1. 指称是否相同？
  2. 替换是否完全无损（双向）？

优点：
  - 根本性：直接回答"什么是冗余"
  - 简洁性：一个原则覆盖所有情况
  - 可解释性：清晰的判断依据
  - 可扩展性：不需要添加新规则
```

## 重新评估：entity_565 vs 666

应用信息完全一致性原则：

```yaml
Step 1: Referential Identity
  Q: 都指向"MRI带宽调整"操作？
  A: YES ✓

Step 2: Substitution Completeness

  Test A (565→666):
    Context: "通过增加读出带宽，可缩小每像素频率范围"
    Replace: "通过加大带宽，可缩小每像素频率范围"
    
    Information loss?
    - "读出带宽"明确指定哪个带宽
    - "带宽"模糊，不知道指哪个
    - 损失了"明确性/精确度"信息
    
    Result: LOSSY ✗

  Test B (666→565):
    Context: "解决办法：加大带宽"
    Replace: "解决办法：增加读出带宽"
    
    Information loss?
    - 没有损失，反而更精确
    
    Result: LOSSLESS ✓

  Symmetry: ASYMMETRIC ✗

Step 3: Decision
  Referential Identity: YES
  Substitution Completeness: NO (asymmetric)
  Information Identity: NO
  
  → Decision: KEEP SEPARATE
  
  Rationale: 
  "虽然两者指向同一技术操作（带宽调整），但它们包含不同的信息。
   entity_565提供了精确的信息（'读出'带宽），而entity_666提供了
   模糊的信息（哪个'带宽'不明确）。将565替换为666会损失精确性，
   说明它们的信息内容不完全一致。因此不应合并。"
```

## 实现建议

### Prompt改进

```python
def _build_head_dedup_prompt_information_identity(
    self, 
    node_id_1: str, 
    node_id_2: str
) -> str:
    """
    基于信息完全一致性原则的prompt
    """
    desc_1 = self._describe_node(node_id_1)
    desc_2 = self._describe_node(node_id_2)
    
    graph_context_1 = self._collect_node_context(node_id_1, max_relations=10)
    graph_context_2 = self._collect_node_context(node_id_2, max_relations=10)
    
    chunk_context_1 = self._collect_chunk_context(node_id_1)
    chunk_context_2 = self._collect_chunk_context(node_id_2)
    
    return f"""You are an expert in knowledge graph entity deduplication.

TASK: Determine if two entities contain EXACTLY THE SAME INFORMATION.

Entity 1 (ID: {node_id_1}): {desc_1}
Graph relationships:
{graph_context_1}
Source text:
{chunk_context_1}

Entity 2 (ID: {node_id_2}): {desc_2}
Graph relationships:
{graph_context_2}
Source text:
{chunk_context_2}

═══════════════════════════════════════════════════════════

FUNDAMENTAL PRINCIPLE: Information Identity

Merge if and only if entities contain EXACTLY THE SAME INFORMATION.

Required conditions (BOTH must hold):
1. REFERENTIAL IDENTITY: Same real-world object
2. SUBSTITUTION COMPLETENESS: Lossless replacement in BOTH directions

═══════════════════════════════════════════════════════════

ANALYSIS STEPS:

STEP 1: REFERENTIAL IDENTITY
Do Entity 1 and Entity 2 refer to the EXACT SAME real-world object?
- Use graph and text evidence
- Check for contradictions

If NO → is_coreferent = false, DONE

STEP 2: SUBSTITUTION COMPLETENESS (if Step 1 = YES)

Test A - Entity 1 → Entity 2 substitution:
  Take Entity 1's source context, replace with Entity 2's expression
  Question: Any information loss? (precision, detail, specificity, etc.)
  
Test B - Entity 2 → Entity 1 substitution:
  Take Entity 2's source context, replace with Entity 1's expression
  Question: Any information loss?

If BOTH tests are lossless → information_identity = true → MERGE
If EITHER test has loss → information_identity = false → KEEP SEPARATE

CRITICAL: Even ONE direction having loss means different information content.

═══════════════════════════════════════════════════════════

CONSERVATIVE PRINCIPLE:
When uncertain about information loss → DO NOT MERGE

═══════════════════════════════════════════════════════════

OUTPUT (strict JSON):
{{
  "is_coreferent": true/false,
  "substitution_lossless_1to2": true/false/null,
  "substitution_lossless_2to1": true/false/null,
  "information_identity": true/false,
  "preferred_representative": "{node_id_1}" or "{node_id_2}" or null,
  "rationale": "Unified analysis: (1) Referential identity evidence; (2) Substitution tests - explicitly identify information loss in each direction; (3) Decision based on information identity principle"
}}

IMPORTANT:
- Explicitly state what information is lost (if any) in each substitution direction
- Only merge if information_identity = true
"""
```

### 输出解析

```python
def _parse_information_identity_response(self, response: str) -> dict:
    """
    解析基于信息完全一致性的响应
    """
    parsed = json_repair.loads(response)
    
    is_coreferent = parsed.get("is_coreferent", False)
    information_identity = parsed.get("information_identity", False)
    
    # 只有信息完全一致才合并
    should_merge = is_coreferent and information_identity
    
    return {
        "is_coreferent": is_coreferent,
        "substitution_lossless_1to2": parsed.get("substitution_lossless_1to2"),
        "substitution_lossless_2to1": parsed.get("substitution_lossless_2to1"),
        "information_identity": information_identity,
        "should_merge": should_merge,
        "preferred_representative": parsed.get("preferred_representative") if should_merge else None,
        "rationale": parsed.get("rationale", "")
    }
```

## 总结

### 根本原则

```
去重的本质 = 消除包含完全相同信息的冗余

判断标准 = 信息完全一致性
  1. 指称相同
  2. 替换完全无损（双向对称）

如果不满足 → 不是冗余 → 不应合并
```

### 为什么这是最佳方案

1. **根本性**: 直接回答"什么是冗余"
2. **简洁性**: 一个原则，不是规则列表
3. **完备性**: 覆盖所有情况，不需要case by case
4. **可解释性**: 清晰的判断依据
5. **保守性**: 不确定时保留信息

### 与之前方案的对比

| 方案 | 本质 | 问题 |
|------|------|------|
| 同社区+同场景 | 启发式 | 不够根本 |
| 三级判断+5维度 | 规则堆砌 | case by case |
| **信息完全一致性** | **根本原则** | **无** ✓ |

你的直觉完全正确：应该从根本原则出发，而不是制定规则清单！
