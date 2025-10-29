# Head Dedup Prompt Optimization: Unified Reasoning

## 问题描述

在使用 head_dedup 对知识图谱进行去重时，之前的 prompt 设计将"上下文使用"和"共指判断"分为两个独立的阶段（PHASE 1 和 PHASE 2），导致 LLM 在 rationale 中也分开描述这两部分。

### 之前的问题示例

```json
{
  "is_coreferent": true,
  "representative": "entity_118",
  "rationale": "(1) 上下文使用：两个实体均属于同一社区"高分辨率成像技术"，且均被同一伪影"截断伪影"的解决方案指向，说明它们在同一技术语境下被当作同一策略；无任何矛盾信息。(2) 共指判断：名称"增加图像的空间分辨率"与"增加图像空间分辨率"仅差一个"的"字，语义完全相同，都是指提升图像空间分辨率这一操作；替换测试通过，不会引起意义变化。(3) 代表选择：entity_118 形式更完整（带"的"字），且其源文本出自专业教材，语言更正式；同时它在知识图中出现次数更多（关键词、社区成员、解决方案指向均列出），信息更丰富，故选为 primary representative。"
}
```

可以看到 rationale 明确分为了三个部分：(1) 上下文使用、(2) 共指判断、(3) 代表选择。

## 修改内容

### 核心变更

将原来分阶段的决策流程改为**综合使用上下文和知识图谱的统一判断流程**：

#### 修改前的结构（分阶段）

```
PHASE 1: USE CONTEXT TO INFORM COREFERENCE DECISION
  → 使用上下文识别矛盾或支持证据
  
PHASE 2: COREFERENCE DETERMINATION
  → 检查名称变体
  → 使用上下文验证关系模式
  → 应用替换测试
  
PHASE 3: REPRESENTATIVE SELECTION
  → 选择代表实体
```

#### 修改后的结构（综合判断）

```
COREFERENCE DETERMINATION PROCEDURE (综合使用上下文和知识图谱):

Use BOTH the source text context AND the graph relationships 
together to make your coreference decision. These are not 
separate steps - they should inform your reasoning throughout.

Step 1: Name Variation Check (using source text + graph context)
Step 2: Contradiction Detection (using source text + graph context)
Step 3: Consistency Verification (using source text + graph context)
Step 4: Substitution Test (using source text + graph context)
Step 5: Conservative Principle (when evidence is insufficient)

REPRESENTATIVE SELECTION (only if entities are coreferent)
```

### Rationale 输出要求的变更

#### 修改前

```
"rationale": "MUST include: (1) How you used the context to inform your 
decision, (2) Coreference decision reasoning, (3) If coreferent, 
representative selection reasoning"
```

#### 修改后

```
"rationale": "Provide a UNIFIED analysis that integrates source text 
and graph relationships throughout your reasoning. DO NOT separate 
into 'context usage' and 'coreference judgment' sections. Instead, 
explain: (1) How the combined evidence (text + graph) supports or 
contradicts coreference (mention specific evidence from BOTH sources), 
(2) Your substitution test result, (3) If coreferent, why you chose 
this representative (considering both text and graph evidence)."
```

### 示例的变更

#### 修改前的示例（分段描述）

```
→ Rationale: "(Context Usage) Graph relationships show consistent 
information: founding year 1945 matches, members align. No contradictions. 
(Coreference) 'UN' is standard abbreviation of 'United Nations'. 
(Representative) Choose entity_100: more relationships and widely 
recognized form."
```

#### 修改后的示例（综合描述）

```
→ Rationale: "Names show 'UN' is the standard abbreviation of 
'United Nations'. Graph evidence strongly supports this: both have 
founding/establishment year 1945, and members 'United States' and 'USA' 
are consistent. Entity_100 has more graph relationships (3 vs 2), 
indicating richer information. No contradictions in any evidence. 
Substitution test passes: can replace in all contexts. Choose entity_100 
as representative due to more complete graph connections and widely 
recognized abbreviated form."
```

## 期望效果

修改后，LLM 应该生成**综合分析**的 rationale，而不是分段描述：

### 期望的输出格式

```json
{
  "is_coreferent": true,
  "representative": "entity_118",
  "rationale": "名称分析显示两个实体仅差一个'的'字，语义完全相同。知识图谱证据强烈支持共指：两个实体均属于同一社区'高分辨率成像技术'，且都被'截断伪影'的解决方案指向，说明在同一技术语境下被视为同一策略。源文本中两者都描述了提升图像空间分辨率的操作，无任何矛盾。替换测试通过：在所有上下文中可以互换而不改变语义。选择 entity_118 作为代表：(1) 形式更完整（带'的'字），(2) 源文本来自专业教材更正式，(3) 在知识图中出现次数更多，包含更丰富的关联信息。"
}
```

## 修改的文件

1. **`/workspace/config/base_config.yaml`**
   - 修改了 `prompts.head_dedup.with_representative_selection` 的完整内容
   - 将分阶段的决策流程改为综合判断流程
   - 更新了 rationale 输出要求
   - 更新了所有示例以展示综合推理方式

2. **`/workspace/head_dedup_llm_driven_representative.py`**
   - 更新了 `_get_embedded_prompt_template_v2()` 方法中的 fallback prompt
   - 确保嵌入式 prompt 与配置文件中的 prompt 保持一致

## 使用方法

### 1. 确保配置正确

在你的配置文件中启用 hybrid context（如果需要使用 chunk 文本）：

```yaml
construction:
  semantic_dedup:
    head_dedup:
      enabled: true
      use_llm_validation: true
      use_hybrid_context: true  # 启用混合上下文
```

### 2. 使用最新的 prompt

确保使用的是 `with_representative_selection` 这个 prompt template：

```python
from kt_gen import KnowledgeTreeGen

# 配置会自动加载最新的 prompt
kt_gen = KnowledgeTreeGen(dataset_name, config)

# 运行 head deduplication
stats = kt_gen.deduplicate_heads_with_llm_v2(
    enable_semantic=True,
    similarity_threshold=0.85
)
```

### 3. 验证输出

检查生成的 rationale 是否符合预期：

```python
# 查看 intermediate results（如果启用了保存）
import json

with open("output/dedup_intermediate/head_dedup_semantic_results.json") as f:
    results = json.load(f)

# 检查 rationale 格式
for result in results:
    if result.get("is_coreferent"):
        print("Rationale:", result["rationale"])
        # 应该看到综合分析，而不是分段描述
```

## 关键改进点总结

1. **统一的分析流程**：不再将"上下文使用"和"共指判断"分开，而是在每个判断步骤中都综合使用源文本和图关系。

2. **明确的指令**：在 prompt 中明确要求 "DO NOT separate into sections"，防止 LLM 分段描述。

3. **更好的示例**：提供了展示综合推理的示例，让 LLM 理解期望的输出格式。

4. **一致性**：确保配置文件和代码中的 fallback prompt 都使用相同的结构。

## 测试建议

运行 head deduplication 并检查输出：

```bash
# 运行测试
python example_use_llm_driven_head_dedup.py

# 查看结果中的 rationale，确认不再有分段描述
```

## 注意事项

1. **向后兼容性**：修改只影响 `with_representative_selection` 这个 prompt template，旧的 `general` template 仍然可用。

2. **Token 使用**：由于 prompt 更详细，token 使用量可能略有增加，但提供了更清晰的指导。

3. **LLM 适应性**：不同的 LLM 模型对指令的遵循程度可能不同，建议在实际数据上测试效果。

## 下一步

如果发现 LLM 仍然倾向于分段描述，可以考虑：

1. 在 system prompt 中加强"综合分析"的要求
2. 提供更多展示综合推理的示例
3. 使用 few-shot learning 的方式在每次调用时提供示例

---

**最后更新**: 2025-10-29  
**相关文件**: 
- `/workspace/config/base_config.yaml`
- `/workspace/head_dedup_llm_driven_representative.py`
