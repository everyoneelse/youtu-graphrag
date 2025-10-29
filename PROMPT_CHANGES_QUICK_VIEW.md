# Prompt 修改快速对比视图

## 修改核心：从"分阶段判断"到"综合判断"

---

## 📋 决策流程对比

### ❌ 修改前（分阶段）

```
PHASE 1: USE CONTEXT TO INFORM COREFERENCE DECISION
  → 使用上下文识别矛盾或支持证据
  → 如果上下文显示矛盾 → 答案是 NO
  → 如果上下文不足 → 应用保守原则

PHASE 2: COREFERENCE DETERMINATION
  Step 1: 检查名称是否是同一实体的变体
  Step 2: 使用上下文验证关系模式是否一致
  Step 3: 查找上下文中的矛盾
  Step 4: 应用替换测试
  Step 5: 不确定时 → 答案是 NO

PHASE 3: REPRESENTATIVE SELECTION (仅当共指时)
  选择主要代表实体
```

### ✅ 修改后（综合判断）

```
COREFERENCE DETERMINATION PROCEDURE (综合使用上下文和知识图谱):

Use BOTH source text AND graph relationships TOGETHER throughout.

Step 1: Name Variation Check
  → using source text + graph context

Step 2: Contradiction Detection
  → using source text + graph context

Step 3: Consistency Verification
  → using source text + graph context

Step 4: Substitution Test
  → using source text + graph context

Step 5: Conservative Principle
  → when evidence is insufficient

REPRESENTATIVE SELECTION (only if coreferent)
```

---

## 📝 Rationale 要求对比

### ❌ 修改前

```json
{
  "rationale": "MUST include: 
    (1) How you used the context to inform your decision, 
    (2) Coreference decision reasoning, 
    (3) If coreferent, representative selection reasoning"
}
```

**问题**：明确要求分为三部分，导致 LLM 输出分段描述。

### ✅ 修改后

```json
{
  "rationale": "Provide a UNIFIED analysis that integrates source 
    text and graph relationships throughout your reasoning. 
    DO NOT separate into 'context usage' and 'coreference judgment' 
    sections. Instead, explain: 
    (1) How the combined evidence (text + graph) supports or 
        contradicts coreference (mention specific evidence from 
        BOTH sources), 
    (2) Your substitution test result, 
    (3) If coreferent, why you chose this representative 
        (considering both text and graph evidence)."
}
```

**改进**：明确禁止分段，要求综合分析。

---

## 💬 输出示例对比

### ❌ 修改前的 Rationale（分段描述）

```
(1) 上下文使用：两个实体均属于同一社区"高分辨率成像技术"，
    且均被同一伪影"截断伪影"的解决方案指向，说明它们在
    同一技术语境下被当作同一策略；无任何矛盾信息。

(2) 共指判断：名称"增加图像的空间分辨率"与"增加图像空间
    分辨率"仅差一个"的"字，语义完全相同，都是指提升图像
    空间分辨率这一操作；替换测试通过，不会引起意义变化。

(3) 代表选择：entity_118 形式更完整（带"的"字），且其源
    文本出自专业教材，语言更正式；同时它在知识图中出现
    次数更多（关键词、社区成员、解决方案指向均列出），
    信息更丰富，故选为 primary representative。
```

**特征**：
- ❌ 明确的 (1)(2)(3) 分段
- ❌ "上下文使用"、"共指判断"、"代表选择" 独立描述
- ❌ 上下文和共指判断分离

### ✅ 修改后的 Rationale（综合分析）

```
名称分析显示两个实体仅差一个'的'字，语义完全相同，都指
向提升图像空间分辨率的操作。知识图谱证据强烈支持共指判断：
两个实体均属于同一社区"高分辨率成像技术"，且都被"截断
伪影"的解决方案指向，说明在同一技术语境下被视为相同策略；
关系模式高度一致，无任何矛盾信息。替换测试通过：在知识图谱
和源文本的所有上下文中可以互换而不改变语义。选择 entity_118 
作为代表实体：(1) 名称形式更完整（带'的'字符），(2) 源
文本来自专业教材更正式规范，(3) 在知识图中出现次数更多，
包含更丰富的关联信息（关键词、社区成员、解决方案等），
能更好地代表这一概念。
```

**特征**：
- ✅ 无明确分段标记
- ✅ 上下文和共指判断融合在一起
- ✅ 自然的叙述流程
- ✅ 证据综合使用（"知识图谱证据"、"源文本"同时出现）

---

## 🔑 关键改进点

| 方面 | 修改前 | 修改后 |
|-----|-------|-------|
| **决策流程** | 分3个独立阶段 | 5个综合步骤 |
| **上下文使用** | 第一阶段单独处理 | 融入每个步骤 |
| **Rationale结构** | 要求分段 (1)(2)(3) | 要求综合分析 |
| **证据引用** | 上下文和共指分开 | 证据综合使用 |
| **示例格式** | 展示分段描述 | 展示综合推理 |

---

## 📊 测试结果

运行 `python3 test_unified_reasoning_prompt.py`：

```
✓ Test 1: Prompt contains unified reasoning instructions
✓ Test 2: Old phased structure removed
✓ Test 3: Rationale requirements explicitly forbid separation
✓ Test 4: Examples use integrated reasoning format
✓ Test 5: Prompt statistics verified
```

---

## 🚀 立即使用

修改已经应用到：
- ✅ `/workspace/config/base_config.yaml`
- ✅ `/workspace/head_dedup_llm_driven_representative.py`

下次运行 head deduplication 时会自动使用新的 prompt！

---

## 📚 更多信息

- 详细说明：[`HEAD_DEDUP_PROMPT_UNIFIED_REASONING.md`](HEAD_DEDUP_PROMPT_UNIFIED_REASONING.md)
- 修改总结：[`PROMPT_MODIFICATION_SUMMARY.md`](PROMPT_MODIFICATION_SUMMARY.md)
- 测试脚本：[`test_unified_reasoning_prompt.py`](test_unified_reasoning_prompt.py)
