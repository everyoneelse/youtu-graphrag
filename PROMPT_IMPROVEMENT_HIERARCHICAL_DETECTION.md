# Prompt改进：增强上下位关系（Hierarchical Relationship）检测

## 问题案例

**误判示例：**
```json
{
  "Entity 1": {
    "name": "伪影",  // 通用概念
    "chunk": "魔角效应伪影，在短TE序列上较为显著..."  // chunk讲的是特定概念
  },
  "Entity 2": {
    "name": "魔角伪影",  // 特定概念
    "chunk": "魔角伪影主要影响肌腱、韧带..."
  },
  "判断结果": "应该合并",  // ❌ 错误
  "正确结果": "应该KEEP SEPARATE"  // ✓ 正确（上下位关系）
}
```

## 根本原因

LLM在判断时**过度依赖chunk内容的相似性**，而**忽略了entity名称的语义层级差异**：

- 当Entity 1的名称是"伪影"（通用），但chunk内容在讲"魔角伪影"（特定）时
- LLM看到两个chunk都在讲"魔角伪影"
- 就错误地认为它们指向同一对象

实际上：
- "伪影"是上位词（hypernym），包括：魔角伪影、化学位移伪影、运动伪影等
- "魔角伪影"是下位词（hyponym），是"伪影"的一个特定类型
- 这是**上下位关系（Is-A relationship）**，应该KEEP SEPARATE

## 改进方案

### 在STEP 1: REFERENTIAL IDENTITY CHECK中增加"名称语义层级检查"

```yaml
STEP 1: REFERENTIAL IDENTITY CHECK

Question: Do Entity 1 and Entity 2 refer to the EXACT SAME real-world object?

Use evidence from:
- Source text contexts (how they are described and used)
- Graph relationships (their connections to other entities)  
- Domain knowledge (what you know about this domain)

Tests:
✓ Same object with different names → Potentially yes (go to Step 2)
✗ Different objects (even if related) → No, KEEP SEPARATE
✗ Part-whole relationship → No, KEEP SEPARATE  
✗ Hierarchical relationship → No, KEEP SEPARATE
✗ ANY contradicting evidence → No, KEEP SEPARATE

# ========== 新增：名称语义层级检查 ==========
CRITICAL: Name Semantic Level Check

Before proceeding to Step 2, ALWAYS check if entity names have hierarchical relationship:

⚠️ WARNING SIGNS of Hierarchical Relationship:
  
  A. GENERIC vs SPECIFIC pattern:
     - One name is GENERIC (通用概念)
     - Other name is SPECIFIC (特定概念)
     - Example: "伪影" (generic) vs "魔角伪影" (specific)
     - Example: "artifact" (generic) vs "magic angle artifact" (specific)
     → This is HYPERNYM-HYPONYM relationship → KEEP SEPARATE ✗

  B. SUBSTRING pattern with semantic expansion:
     - One name is substring of the other
     - The longer name adds semantic specificity
     - Example: "带宽" vs "读出带宽" (adds "readout" specificity)
     - Example: "bandwidth" vs "readout bandwidth"
     → This is TYPE-SUBTYPE relationship → KEEP SEPARATE ✗

  C. CATEGORY-MEMBER pattern:
     - One name represents a CATEGORY/CLASS
     - Other name represents a MEMBER/INSTANCE of that category
     - Example: "病人" (category) vs "张三" (specific patient)
     - Example: "fruit" (category) vs "apple" (specific fruit)
     → This is CLASS-INSTANCE relationship → KEEP SEPARATE ✗

📋 Hierarchical Relationship Detection Procedure:

1. Compare entity NAMES first (ignore chunk content temporarily)
   
2. Ask: "Is Entity 1's name a BROADER/GENERIC concept that includes Entity 2?"
   - If YES → Hierarchical relationship detected → OUTPUT: is_coreferent = false, STOP
   
3. Ask: "Is Entity 2's name a BROADER/GENERIC concept that includes Entity 1?"
   - If YES → Hierarchical relationship detected → OUTPUT: is_coreferent = false, STOP

4. Domain-specific check:
   - In medical/technical domains, check if one term is standard terminology
     and the other is a specialized subtype
   - Example: "MRI伪影" (general) vs "魔角伪影" (specialized subtype)

5. Only if BOTH names are at THE SAME SEMANTIC LEVEL → Proceed to chunk comparison

# ========== 重要：处理名称-内容不一致 ==========

⚠️ IMPORTANT: Handling Name-Content Inconsistency

If you notice that:
  • Entity 1's NAME is generic (e.g., "伪影")
  • But Entity 1's CHUNK content describes something specific (e.g., "魔角效应伪影")
  
This indicates an ENTITY EXTRACTION ERROR in the upstream process.

In this case:
  1. PRIORITIZE the entity NAME for semantic level comparison
  2. Do NOT let chunk content override the name's semantic level
  3. If names show hierarchical relationship → KEEP SEPARATE
  
Rationale: 
  - Even if chunks describe similar content, the entity NAMES define
    their role and scope in the knowledge graph
  - "伪影" should represent ALL types of artifacts in the graph
  - "魔角伪影" should represent ONE SPECIFIC type
  - Merging them would LOSE the hierarchical structure

# ==============================================

If referentially different → OUTPUT: is_coreferent = false, STOP
```

### 增加具体示例

在EXAMPLES部分增加hierarchical relationship的示例：

```yaml
Example 4 - Hierarchical Relationship (MUST KEEP SEPARATE):

Entity 1 (entity_400): "伪影"
Graph relationships:
  • member_of → 脊柱解剖与诊断
  • 表现形式为 → (relationship, but no specific target shown)
Source text:
  "{'title': '魔角效应：', 'content': '魔角效应伪影，在短TE序列上较为显著...'}"

Entity 2 (entity_500): "魔角伪影"  
Graph relationships:
  • has_attribute → 定义:肌腱、韧带等平行纤维结构与主磁场B0成55°夹角时信号增强的现象
  • 表现形式为 → 信号增强
  • 常见部位或组织为 → 肌腱
Source text:
  "{'title': '13.6 魔角效应', 'content': '魔角伪影主要影响肌腱、韧带...'}"

Analysis:
→ NAME SEMANTIC LEVEL CHECK:
  • Entity 1 name: "伪影" - GENERIC concept (encompasses ALL types of MRI artifacts)
  • Entity 2 name: "魔角伪影" - SPECIFIC concept (ONE particular type of artifact)
  • Relationship: "魔角伪影" is a SUBTYPE of "伪影" 
  • Pattern: HYPERNYM (伪影) - HYPONYM (魔角伪影) relationship detected ✗

→ HIERARCHICAL RELATIONSHIP DETECTED:
  • "伪影" includes: 魔角伪影, 化学位移伪影, 运动伪影, 金属伪影, etc.
  • "魔角伪影" is ONE specific member of the "伪影" category
  • This is IS-A relationship (魔角伪影 IS-A 伪影)
  
→ NOTE ON CHUNK CONTENT:
  • Entity 1's chunk happens to describe "魔角效应伪影"
  • This indicates an ENTITY EXTRACTION ERROR (should have extracted "魔角伪影" not "伪影")
  • However, we MUST respect the entity NAME as it defines the scope in the graph
  • Do NOT let chunk similarity override name-level semantic hierarchy

→ SUBSTITUTION TEST (if we ignored hierarchy):
  • Replacing "伪影" with "魔角伪影" in other contexts would LOSE generality
  • "伪影的分类" → "魔角伪影的分类" (wrong! loses other artifact types)
  • Asymmetric relationship: specific cannot replace generic

→ is_coreferent: false
→ information_identity: false
→ preferred_representative: null
→ Rationale: "These entities have a HIERARCHICAL RELATIONSHIP (hypernym-hyponym). 
   Entity 1 '伪影' is a GENERIC term representing ALL types of MRI artifacts, while 
   Entity 2 '魔角伪影' is a SPECIFIC subtype. Although Entity 1's chunk content 
   describes magic angle artifact specifically (indicating an upstream extraction error), 
   we must prioritize the entity NAME for semantic level comparison. In the knowledge 
   graph structure, '伪影' should be preserved as the general category node, with 
   '魔角伪影' as a specialized subtype node. Merging them would collapse the 
   hierarchical structure and lose the ability to represent other artifact types under 
   the general '伪影' category. This violates the fundamental principle: hierarchical 
   relationships must be kept separate to preserve semantic distinctions."

Example 5 - Generic-Specific Pattern (MUST KEEP SEPARATE):

Entity 1 (entity_600): "带宽"
Source text: "提高带宽可以减少伪影"

Entity 2 (entity_700): "读出带宽"
Source text: "读出带宽的增加能改善化学位移伪影"

Analysis:
→ NAME SEMANTIC LEVEL CHECK:
  • Entity 1: "带宽" (generic - could mean any bandwidth)
  • Entity 2: "读出带宽" (specific - specifies which bandwidth)
  • Pattern: Entity 2 adds semantic specificity ("读出") to Entity 1
  
→ HIERARCHICAL RELATIONSHIP:
  • "带宽" is broader concept that includes: 读出带宽, 射频带宽, 接收带宽, etc.
  • "读出带宽" is ONE specific type

→ INFORMATION ASYMMETRY:
  • Test 1→2: "提高带宽" → "提高读出带宽" 
    Adds specificity that may not exist in original context ✗
  • Test 2→1: "读出带宽的增加" → "带宽的增加"
    Loses precision about which bandwidth ✗

→ is_coreferent: false
→ Rationale: "Hierarchical relationship detected. '带宽' is a generic term that encompasses 
   multiple types of bandwidth parameters in MRI, while '读出带宽' specifically refers to 
   readout gradient bandwidth. They represent different levels of semantic granularity. 
   Merging them would lose the distinction between generic and specific bandwidth concepts."
```

## 实现要点

### 1. 在代码层面的改进

在`_build_head_dedup_prompt_v2`方法中，可以考虑增加实体名称的预处理：

```python
def _detect_hierarchical_relationship(self, name1: str, name2: str) -> dict:
    """
    Detect if two entity names have hierarchical relationship.
    
    Returns:
        {
            "is_hierarchical": bool,
            "type": "hypernym-hyponym" | "substring" | "category-member" | None,
            "explanation": str
        }
    """
    # Check substring pattern
    if name1 in name2 and name1 != name2:
        return {
            "is_hierarchical": True,
            "type": "substring",
            "explanation": f"'{name1}' is contained in '{name2}'"
        }
    if name2 in name1 and name1 != name2:
        return {
            "is_hierarchical": True,
            "type": "substring",
            "explanation": f"'{name2}' is contained in '{name1}'"
        }
    
    # Check generic-specific pattern (domain-specific)
    generic_terms = ["伪影", "artifact", "带宽", "bandwidth", "序列", "sequence"]
    if name1 in generic_terms and name2 not in generic_terms and name1 in name2:
        return {
            "is_hierarchical": True,
            "type": "hypernym-hyponym",
            "explanation": f"'{name1}' is generic, '{name2}' is specific"
        }
    if name2 in generic_terms and name1 not in generic_terms and name2 in name1:
        return {
            "is_hierarchical": True,
            "type": "hypernym-hyponym", 
            "explanation": f"'{name2}' is generic, '{name1}' is specific"
        }
    
    return {
        "is_hierarchical": False,
        "type": None,
        "explanation": ""
    }
```

### 2. 在Prompt中提供检测结果

将检测结果注入到prompt中，给LLM提供明确的提示：

```python
def _build_head_dedup_prompt_v2(self, node_id_1: str, node_id_2: str) -> str:
    # ... existing code ...
    
    name1 = self.graph.nodes[node_id_1].get("name", "")
    name2 = self.graph.nodes[node_id_2].get("name", "")
    
    hierarchy_check = self._detect_hierarchical_relationship(name1, name2)
    
    if hierarchy_check["is_hierarchical"]:
        hierarchy_warning = f"""
⚠️ HIERARCHICAL RELATIONSHIP DETECTED:
  Type: {hierarchy_check["type"]}
  Explanation: {hierarchy_check["explanation"]}
  
CRITICAL: According to merge rules, hierarchical relationships MUST be kept separate.
Please verify this relationship carefully before making a decision.
"""
    else:
        hierarchy_warning = ""
    
    # Include hierarchy_warning in the prompt
    prompt = f"""
{base_prompt}

{hierarchy_warning}

{rest_of_prompt}
"""
    return prompt
```

## 总结

### 关键改进点：

1. **增加名称语义层级检查**：在判断referential identity之前，先检查名称是否存在上下位关系

2. **处理名称-内容不一致**：当entity名称和chunk内容语义层级不一致时，优先考虑名称层级

3. **增加hierarchical relationship示例**：提供具体的generic-specific、hypernym-hyponym案例

4. **可选的代码层辅助**：通过代码预检测hierarchical relationship，给LLM提供明确提示

### 预期效果：

- 减少将上下位关系误判为共指关系的情况
- 保护知识图谱的层次结构
- 提高对通用概念vs特定概念的区分能力
- 更好地处理实体提取阶段的错误遗留问题
