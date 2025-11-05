# Semantic Dedup - Rationale与Members不一致问题分析

**创建时间**: 2025-11-05 05:46:17  
**问题类型**: LLM输出一致性问题

---

## 问题描述

在使用`semantic_dedup_group`进行去重时，LLM返回的结果经常出现**rationale（理由说明）与members（成员列表）不一致**的问题。

### 具体表现

以您提供的例子为例（batch_indices: [0, 1, 4, 7, 8, 11]）：

```json
{
  "groups": [
    {
      "members": [5],
      "representative": 5,
      "rationale": "该条目定义为'不同化学环境下质子共振频率的差异'，与[1]的表述角度一致但措辞不同；经替换测试，两者可互换而不丢失信息，因此视为同一实体的同义表达，予以合并。"
    },
    {
      "members": [6],
      "representative": 6,
      "rationale": "该条目用'质子的共振频率会因其分子环境不同而变化'来阐释化学位移，与[1][5]一样是对同一物理现象的定义性描述，可互相替换且信息无损，故与[5]合并为同一实体。"
    }
  ]
}
```

**问题点**：
- Group 5的rationale说"与[1]...予以合并"，但members只有[5]，没有包含[1]
- Group 6的rationale说"与[1][5]...故与[5]合并"，但members只有[6]，没有包含[1]和[5]

---

## 根本原因分析

### 1. **LLM理解偏差**

LLM在理解prompt时，可能将任务理解为：
- **顺序处理模式**：逐个分析每个候选项，决定它是否应该与之前的组合并
- 而不是**全局分组模式**：将所有相似的候选项放在同一个group中

这导致LLM在rationale中描述了"应该与组X合并"，但在输出JSON时，仍然将该候选项单独放在一个新的group中。

### 2. **Prompt指导不够清晰**

虽然当前prompt（`DEFAULT_SEMANTIC_DEDUP_PROMPT`）中已经包含了关键性的指导：

```python
"5. **CRITICAL CONSISTENCY**: Ensure your 'members' array MATCHES your 'rationale':
   - If rationale says 'X and Y refer to the same entity' or 'should be merged',
     then X and Y MUST be in the SAME group's members array
   - If rationale says 'distinct entities' or 'should be kept separate',
     then they MUST be in DIFFERENT groups
   - Do NOT put items in separate groups if your rationale says they are coreferent!
   - Do NOT reference merging with other groups if members are already separate"
```

但LLM仍然可能：
- **忽略这条规则**：在生成过程中没有严格遵守
- **理解错位**：认为"合并"是一个概念上的描述，而不是实际的操作指令

### 3. **中文prompt的理解问题**

从您的例子来看，rationale是用中文编写的。LLM在处理中文时，可能对"合并"、"予以合并"等表述的理解不够精确，特别是在需要将这种描述转换为具体的JSON结构时。

### 4. **输出格式的两阶段性**

LLM在生成JSON时，可能：
1. 先逐个分析每个候选项（内部思考）
2. 然后生成JSON输出（结构化）

在这两个阶段之间，**一致性检查**可能没有正确执行。

---

## 是否与结构化输出有关？

**回答：不太可能**

从代码分析来看（`call_llm_api.py`第37-62行）：

```python
def call_api(self, content: str, temperature: float = None) -> str:
    completion = self.client.chat.completions.create(
        model=self.llm_model,
        messages=[{"role": "user", "content": content}],
        temperature=temp
    )
```

当前实现**没有使用OpenAI的结构化输出功能**（如`response_format={"type": "json_object"}`或JSON Schema）。

因此，这个问题主要是：
- ❌ 不是结构化输出API的问题
- ✅ 是LLM对prompt理解和执行的问题

---

## 解决方案建议

### 🎯 方案1: 增强Prompt的明确性（推荐）

**修改策略**：
1. 在prompt开头就明确说明"每个group必须包含所有相同实体的候选项"
2. 增加更多的反例说明
3. 使用更强调的语言

**具体修改**：在`DEFAULT_SEMANTIC_DEDUP_PROMPT`中添加：

```python
"CRITICAL OUTPUT RULE:\n"
"- If you determine that candidates [1], [5], and [6] refer to the SAME entity,\n"
"  you MUST output ONE group with members: [1, 5, 6]\n"
"- NEVER output separate groups like:\n"
"  ❌ Group A: members=[1], rationale='...'\n"
"  ❌ Group B: members=[5], rationale='same as [1], should merge'\n"
"  ❌ Group C: members=[6], rationale='same as [1] and [5]'\n"
"- ALWAYS output:\n"
"  ✅ Group: members=[1, 5, 6], rationale='all refer to the same entity'\n\n"
```

### 🎯 方案2: 启用结构化输出（API层面）

如果使用的是支持结构化输出的模型（如OpenAI GPT-4），可以修改`call_llm_api.py`：

```python
def call_api(self, content: str, temperature: float = None, use_json_mode: bool = False) -> str:
    messages = [{"role": "user", "content": content}]
    
    kwargs = {
        "model": self.llm_model,
        "messages": messages,
        "temperature": temp
    }
    
    if use_json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    
    completion = self.client.chat.completions.create(**kwargs)
    ...
```

**优点**：
- 强制LLM输出有效的JSON
- 可能提高格式一致性

**缺点**：
- 不能完全解决逻辑一致性问题
- 需要模型支持

### 🎯 方案3: 后处理验证与修复（推荐）

**在代码层面添加验证**：在解析LLM响应后，检查rationale与members的一致性。

**实现位置**：`kt_gen.py`的`_parse_semantic_dedup_results`方法（第3932行）

**实现逻辑**：

```python
def _validate_and_fix_group_consistency(self, groups_raw: list) -> list:
    """
    验证并修复groups中rationale与members的不一致问题
    """
    fixed_groups = []
    
    for group in groups_raw:
        rationale = group.get("rationale", "")
        members = group.get("members", [])
        
        # 从rationale中提取引用的候选项索引
        # 例如：匹配 "[1]", "[5]", "[1][5]" 等
        referenced_indices = set()
        import re
        for match in re.finditer(r'\[(\d+)\]', rationale):
            referenced_indices.add(int(match.group(1)))
        
        # 检查是否提到"合并"、"merge"等关键词
        merge_keywords = ['合并', '一致', 'merge', 'same', 'identical', 'coreferent']
        mentions_merge = any(keyword in rationale.lower() for keyword in merge_keywords)
        
        # 如果rationale中引用了其他索引且提到合并，发出警告
        if referenced_indices and mentions_merge:
            missing_refs = referenced_indices - set(members)
            if missing_refs:
                logger.warning(
                    f"Inconsistency detected: rationale mentions merging with {missing_refs}, "
                    f"but members only contains {members}. Consider reviewing prompt."
                )
        
        fixed_groups.append(group)
    
    return fixed_groups
```

**注意**：这种方法只能检测问题，不能完全自动修复，因为不确定LLM的真实意图。

### 🎯 方案4: 两阶段LLM调用

**流程**：
1. **第一阶段**：让LLM分析哪些候选项是相同实体（只输出分组决策）
2. **第二阶段**：基于第一阶段的结果，生成rationale

**优点**：
- 降低任务复杂度
- 减少不一致性

**缺点**：
- 增加API调用次数和成本
- 增加处理时间

---

## 立即可行的解决方案

### ✅ 推荐做法

1. **增强Prompt**（修改`kt_gen.py`第23-94行的`DEFAULT_SEMANTIC_DEDUP_PROMPT`）
   
   在第75-87行的"CRITICAL CONSISTENCY"部分之前添加：

```python
"🚨 ABSOLUTE RULE - NO EXCEPTIONS:\n"
"When you write in your rationale that candidates X and Y 'should be merged', 'are the same', \n"
"'are coreferent', '予以合并', '视为同一实体', or any similar phrase:\n"
"→ Those candidates MUST appear together in the SAME group's members array\n"
"→ DO NOT create separate groups for them\n\n"
"CORRECT Example:\n"
"  If [1], [5], [6] are the same entity:\n"
"  ✅ {\"members\": [1, 5, 6], \"representative\": 1, \"rationale\": \"[1], [5], and [6] all refer to...\"}\n\n"
"INCORRECT Example (DO NOT DO THIS):\n"
"  ❌ {\"members\": [1], \"rationale\": \"...\"}\n"
"  ❌ {\"members\": [5], \"rationale\": \"与[1]一致，予以合并\"}  ← WRONG! [1] and [5] must be in same group\n"
"  ❌ {\"members\": [6], \"rationale\": \"与[1][5]合并\"}  ← WRONG! [1], [5], [6] must be in same group\n\n"
```

2. **添加后处理验证**（可选，但推荐）
   
   在`_parse_semantic_dedup_results`中添加一致性检查日志

3. **调整temperature**
   
   如果当前temperature较高（>0.5），考虑降低到0.1-0.3，使输出更确定性

---

## 测试建议

修改后，使用相同的输入数据测试：
- 观察LLM是否正确地将[1]、[5]、[6]放在同一个group中
- 检查rationale是否不再引用其他group

如果问题依然存在，可能需要：
- 切换到更强大的模型（如GPT-4o）
- 使用方案4的两阶段调用

---

## 总结

- **问题本质**：LLM在理解"合并"指令时，将其作为概念描述而非操作指令
- **主要原因**：Prompt中的一致性要求不够突出，LLM容易忽略
- **推荐方案**：增强prompt + 可选的后处理验证
- **与结构化输出的关系**：关系不大，主要是prompt设计问题

希望这个分析对您有帮助！如果修改后仍有问题，欢迎提供更多信息以便进一步诊断。
