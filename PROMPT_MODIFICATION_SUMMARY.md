# Head Dedup Prompt 修改总结

## 修改日期
2025-10-29

## 问题描述

用户在使用 head_dedup 对知识图谱进行去重时，发现 LLM 的 rationale 将"上下文使用"和"共指判断"分开描述：

```json
{
  "rationale": "(1) 上下文使用：两个实体均属于同一社区...无任何矛盾信息。
                (2) 共指判断：名称...语义完全相同...
                (3) 代表选择：entity_118 形式更完整..."
}
```

**用户期望**：共指判断应该综合使用 entity 所在的 chunk 以及 entity 链接的知识图谱来判断，而不是分开判断。

## 根本原因

原 prompt 的结构将决策流程分为三个独立的 PHASE：
- PHASE 1: USE CONTEXT TO INFORM COREFERENCE DECISION
- PHASE 2: COREFERENCE DETERMINATION  
- PHASE 3: REPRESENTATIVE SELECTION

这种分阶段的结构引导 LLM 也在 rationale 中分段描述。

## 解决方案

### 核心改动

将分阶段的决策流程改为**综合判断流程**，在每个判断步骤中都同时使用源文本和图关系：

```
COREFERENCE DETERMINATION PROCEDURE (综合使用上下文和知识图谱):

Use BOTH the source text context AND the graph relationships 
together to make your coreference decision. These are not 
separate steps - they should inform your reasoning throughout.

Step 1: Name Variation Check (using source text + graph context)
Step 2: Contradiction Detection (using source text + graph context)
Step 3: Consistency Verification (using source text + graph context)
Step 4: Substitution Test (using source text + graph context)
Step 5: Conservative Principle
```

### Rationale 要求改动

**之前**：
```
"rationale": "MUST include: (1) How you used the context to inform 
your decision, (2) Coreference decision reasoning, (3) If coreferent, 
representative selection reasoning"
```

**之后**：
```
"rationale": "Provide a UNIFIED analysis that integrates source text 
and graph relationships throughout your reasoning. DO NOT separate 
into 'context usage' and 'coreference judgment' sections. Instead, 
explain: (1) How the combined evidence (text + graph) supports or 
contradicts coreference (mention specific evidence from BOTH sources), 
(2) Your substitution test result, (3) If coreferent, why you chose 
this representative (considering both text and graph evidence)."
```

### 示例改动

**之前的示例**（分段）：
```
"(Context Usage) Graph relationships show consistent information... 
(Coreference) 'UN' is standard abbreviation... 
(Representative) Choose entity_100..."
```

**之后的示例**（综合）：
```
"Names show 'UN' is the standard abbreviation of 'United Nations'. 
Graph evidence strongly supports this: both have founding/establishment 
year 1945, and members 'United States' and 'USA' are consistent. 
Entity_100 has more graph relationships (3 vs 2), indicating richer 
information. No contradictions in any evidence. Substitution test 
passes: can replace in all contexts. Choose entity_100 as 
representative due to more complete graph connections and widely 
recognized abbreviated form."
```

## 修改的文件

### 1. `/workspace/config/base_config.yaml`

修改位置：`prompts.head_dedup.with_representative_selection`

主要改动：
- 移除 "CONTEXT USAGE GUIDANCE" 和分阶段的 "PHASE 1/2/3" 结构
- 新增 "COREFERENCE DETERMINATION PROCEDURE (综合使用上下文和知识图谱)"
- 在每个判断步骤中明确标注 "(using source text + graph context)"
- 更新 rationale 输出要求，明确禁止分段描述
- 更新所有示例，展示综合推理方式

### 2. `/workspace/head_dedup_llm_driven_representative.py`

修改位置：`_get_embedded_prompt_template_v2()` 方法

主要改动：
- 更新 fallback prompt 以与配置文件保持一致
- 采用相同的综合判断流程结构
- 更新 rationale 输出要求

## 验证测试

创建了测试脚本 `/workspace/test_unified_reasoning_prompt.py`，验证结果：

```
✓ Test 1: Prompt contains unified reasoning instructions
✓ Test 2: Old phased structure removed
✓ Test 3: Rationale requirements explicitly forbid separation
✓ Test 4: Examples use integrated reasoning format
✓ Test 5: Prompt statistics (7557 characters, 4 examples)
```

## 预期效果

运行 head deduplication 后，rationale 应该呈现**综合分析**的格式：

```json
{
  "is_coreferent": true,
  "representative": "entity_118",
  "rationale": "名称分析显示两个实体仅差一个'的'字，语义完全相同，
                都指向提升图像空间分辨率的操作。知识图谱证据强烈支持
                共指判断：两个实体均属于同一社区'高分辨率成像技术'，
                且都被'截断伪影'的解决方案指向，说明在同一技术语境下
                被视为相同策略；关系模式高度一致，无任何矛盾信息。
                替换测试通过：在知识图谱和源文本的所有上下文中可以互换
                而不改变语义。选择 entity_118 作为代表实体：(1) 名称
                形式更完整（带'的'字符），(2) 源文本来自专业教材更
                正式规范，(3) 在知识图中出现次数更多，包含更丰富的
                关联信息（关键词、社区成员、解决方案等），能更好地
                代表这一概念。"
}
```

## 使用方法

### 1. 确保使用最新配置

```yaml
construction:
  semantic_dedup:
    head_dedup:
      enabled: true
      use_llm_validation: true
      use_hybrid_context: true  # 启用混合上下文（如果需要）
```

### 2. 运行 head deduplication

```python
from models.constructor.kt_gen import KnowledgeTreeGen

kt_gen = KnowledgeTreeGen(dataset_name, config)
stats = kt_gen.deduplicate_heads_with_llm_v2(
    enable_semantic=True,
    similarity_threshold=0.85
)
```

### 3. 验证输出

检查生成的 rationale 格式：

```python
import json

# 如果启用了 save_intermediate_results
with open("output/dedup_intermediate/head_dedup_semantic_results.json") as f:
    results = json.load(f)

for result in results:
    if result.get("is_coreferent"):
        rationale = result["rationale"]
        # 检查是否还有分段描述（如 "(1)", "(2)", "(3)"）
        if "上下文使用：" in rationale or "共指判断：" in rationale:
            print("⚠️ 仍然存在分段描述")
        else:
            print("✓ 综合分析格式正确")
```

## 注意事项

1. **LLM 遵循能力**：不同的 LLM 模型对 prompt 指令的遵循程度不同。如果某些模型仍然倾向于分段，可以考虑：
   - 在 system prompt 中进一步强调
   - 使用 few-shot learning 提供更多示例
   - 尝试使用更强大的 LLM 模型

2. **向后兼容**：修改只影响 `with_representative_selection` 这个 prompt template，旧的 `general` template 仍然可用。

3. **Token 使用**：由于 prompt 更详细，token 使用量可能略有增加。

4. **迭代优化**：如果发现 LLM 输出仍不理想，可以：
   - 调整 prompt 中的措辞
   - 增加更多示例
   - 在 rationale 要求中进一步强调

## 相关文档

- [`HEAD_DEDUP_PROMPT_UNIFIED_REASONING.md`](/workspace/HEAD_DEDUP_PROMPT_UNIFIED_REASONING.md) - 详细说明文档
- [`test_unified_reasoning_prompt.py`](/workspace/test_unified_reasoning_prompt.py) - 验证测试脚本

## 后续步骤

1. 在实际数据上运行 head deduplication
2. 检查 rationale 输出是否符合预期
3. 如有需要，进一步调整 prompt
4. 收集反馈并持续优化

---

**修改完成时间**: 2025-10-29  
**测试状态**: ✓ 所有测试通过  
**建议**: 请在真实数据上测试并观察 LLM 的实际输出效果
