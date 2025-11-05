# 完整解决方案：分组思维 vs 归类思维

**创建时间**: 2025-11-05 06:16:26  
**核心发现**: LLM使用"归类思维"而非"分组思维"  
**重要性**: ⭐⭐⭐⭐⭐

---

## 问题演进过程

### 第一次发现（用户原始问题）
```json
{
  "members": [5],
  "rationale": "与[1]...予以合并"  // ← 说要合并，但members里没有[1]
}
```

**初步诊断**: rationale与members不一致

### 第二次发现（字段顺序）
```json
{
  "members": [3],
  "rationale": "...可合并；但当前组内仅含自身，故单独列出。"  // ← LLM自圆其说
}
```

**深入发现**: LLM先生成members，后生成rationale，导致无法回退修改

### 第三次发现（归类思维）
```json
{
  "rationale": "因此与第1组合并。",  // ← 归类语言
  "members": [6],
  "representative": 1  // ← representative是1，但members里没有1！
}
```

**根本原因**: LLM使用"归类思维"（decide which group it belongs to）而非"分组思维"（group same entities together）

---

## 根本问题：归类思维 vs 分组思维

### ❌ 错误的归类思维（Categorization）

LLM的内部流程：
```
处理候选项[1]: 这是定义A，创建组1
处理候选项[2]: 这是定义B，创建组2
处理候选项[3]: 这和定义A一样，它应该"归入"组1
处理候选项[4]: 这也和定义A一样，它应该"归入"组1
处理候选项[5]: 这和定义B一样，它应该"归入"组2
处理候选项[6]: 这和定义A一样，它应该"归入"组1
```

输出结果（错误）：
```json
{
  "groups": [
    {"rationale": "...", "members": [1], "representative": 1},
    {"rationale": "...", "members": [2], "representative": 2},
    {"rationale": "与第1组合并", "members": [3], "representative": 1},
    {"rationale": "与第1组合并", "members": [4], "representative": 1},
    {"rationale": "与第2组合并", "members": [5], "representative": 2},
    {"rationale": "与第1组合并", "members": [6], "representative": 1}
  ]
}
```

**问题**：
- 创建了6个separate groups
- rationale说"与X组合并"，但members只有自己
- representative不在members中（完全不合理）

### ✅ 正确的分组思维（Grouping）

正确的流程：
```
第1步: 浏览所有候选项[1-6]
第2步: 识别相同的实体
  - [1], [3], [4], [6] 都是定义A（同一实体）
  - [2], [5] 都是定义B（同一实体）
第3步: 创建groups
  - 组1: members [1, 3, 4, 6], representative 1
  - 组2: members [2, 5], representative 2
```

输出结果（正确）：
```json
{
  "groups": [
    {
      "rationale": "候选项[1]、[3]、[4]、[6]都给出定义A，指向同一概念...",
      "members": [1, 3, 4, 6],
      "representative": 1
    },
    {
      "rationale": "候选项[2]、[5]都给出定义B，指向同一概念...",
      "members": [2, 5],
      "representative": 2
    }
  ]
}
```

---

## 完整修改方案

### 修改1: 在prompt开头强调"分组思维"

**位置**: `DEFAULT_SEMANTIC_DEDUP_PROMPT`和`DEFAULT_ATTRIBUTE_DEDUP_PROMPT`开头

**新增内容**（26-51行）:
```
🚨 ABSOLUTE CONSISTENCY REQUIREMENT (READ THIS FIRST):

GROUPING MINDSET (NOT categorization):
❌ WRONG: Process each candidate one by one and decide "which group does it belong to?"
✅ CORRECT: Look at ALL candidates first, find which ones are the SAME entity, then create groups

Example with candidates [1], [2], [3], [4], [5], [6]:
❌ WRONG approach:
   - Process [1]: create group A
   - Process [2]: different from [1], create group B
   - Process [3]: same as [1], write "merge with group A" but only put [3] in members
   - Process [4]: same as [1], write "merge with group A" but only put [4] in members
   Result: Multiple separate groups with rationales saying "merge with..."

✅ CORRECT approach:
   - Survey ALL candidates: [1], [3], [4] are the same; [2], [5] are the same; [6] is unique
   - Create group 1: members [1, 3, 4], rationale "[1], [3], [4] all refer to..."
   - Create group 2: members [2, 5], rationale "[2], [5] both refer to..."
   - Create group 3: members [6], rationale "[6] is unique..."
```

### 修改2: 调整JSON字段顺序（rationale在前）

**位置**: JSON schema示例

**修改**:
```json
// 修改前
{"members": [1, 3], "representative": 3, "rationale": "..."}

// 修改后
{"rationale": "Candidates [1] and [3] refer to...", "members": [1, 3], "representative": 3}
```

**原因**: 
- LLM先生成rationale，必须明确说出"[1]和[3]应该在一起"
- 然后生成members时，自然会填[1, 3]
- 避免先生成members后无法回退的问题

### 修改3: 增强MANDATORY WORKFLOW

**位置**: OUTPUT REQUIREMENTS第5条（89-102行）

**新增内容**:
```
5. 🚨 **MANDATORY WORKFLOW** (Follow this order strictly):
   
   BEFORE generating JSON:
   Step 1: For each candidate, determine which OTHER candidates (if any) refer to the same entity
   Step 2: Mentally group candidates that are coreferent (e.g., [1,3,5] are same, [2,4] are same, [6] is unique)
   Step 3: For each group, formulate the rationale explaining why ALL members are coreferent
   
   WHEN generating JSON:
   Step 4: Write rationale FIRST - this forces you to explicitly state which candidates belong together
   Step 5: Write members array - include ALL candidates mentioned in the rationale
   Step 6: Verify consistency - does the members array match what the rationale says?
   
   ⚠️  CRITICAL: If your rationale says '[X] and [Y] are coreferent', you CANNOT output members: [X] only.
                You MUST output members: [X, Y] (or revise the rationale to not mention Y).
```

### 修改4: 绝对禁止"归类语言"

**位置**: RATIONALE WRITING GUIDELINES（108-123行）

**新增内容**:
```
🚫 ABSOLUTELY FORBIDDEN in rationale:
   ✗ "与第X组合并" / "merge with group X" / "归入第X组"
   ✗ "与候选项[X]合并" when X is NOT in the members array
   ✗ Any reference to candidates that are NOT in this group's members
   
   ✅ CORRECT rationale style:
   - "Candidates [1], [3], and [5] all refer to the same entity because..."
   - "候选项[1]、[3]、[5]都表示同一个概念..."
   
   ⚠️  If you want to say candidate [6] should merge with candidate [1]:
       → Create ONE group with members: [1, 6]
       → NOT: group A with members: [1], group B with members: [6] and rationale "merge with [1]"
```

---

## 候选项数量的影响

### 当前配置

从`base_config.yaml`：
```yaml
semantic_dedup:
  max_batch_size: 8        # 每批最多8个候选项进行semantic dedup
  max_candidates: 50       # 每个cluster最多处理50个候选项
  llm_clustering_batch_size: 30  # LLM clustering时每批30个
```

### 问题分析

**候选项数量与思维模式的关系**：

| 候选项数量 | LLM行为 | 结果质量 |
|-----------|---------|---------|
| 2-4个 | 全局分组思维 | ✅ 高质量 |
| 5-8个 | 混合（部分全局，部分顺序） | ⚠️ 中等 |
| 9-15个 | 倾向顺序处理（归类思维） | ❌ 容易出错 |
| >15个 | 明显的归类思维 | ❌❌ 高错误率 |

**为什么候选项多会导致归类思维？**

1. **注意力限制**: LLM难以同时在working memory中保持>10个候选项的比较
2. **顺序处理倾向**: 候选项多时，LLM自然倾向于逐个处理
3. **局部优化**: 每次只关注"当前候选项应该归到哪"，失去全局视角

### 建议的配置调整

根据您的数据特点选择：

#### 方案A: 降低batch size（推荐）

```yaml
semantic_dedup:
  max_batch_size: 5  # 从8降到5
  max_candidates: 50
```

**优点**:
- 强制LLM处理更小的批次
- 更容易保持全局分组思维
- 减少错误率

**缺点**:
- 增加API调用次数
- 略微增加处理时间

#### 方案B: 启用两阶段处理

```yaml
semantic_dedup:
  max_batch_size: 8
  max_candidates: 30  # 从50降到30
  clustering_method: llm  # 使用LLM clustering先分组
```

**优点**:
- 先通过clustering将相似候选项分到小cluster
- 每个cluster再进行semantic dedup（批次自然变小）
- 减轻LLM的全局规划负担

**缺点**:
- 增加一次LLM调用（clustering阶段）
- 成本略有增加

#### 方案C: 启用验证（兜底方案）

```yaml
semantic_dedup:
  max_batch_size: 8
  enable_semantic_dedup_validation: true  # 启用二次验证
```

**作用**:
- LLM完成dedup后，再次检查一致性
- 如果发现"与[X]合并"但members不包含X，会尝试修复
- 作为最后一道防线

**注意**: 这是配置文件第43-47行的功能，目前默认是false

---

## 实际数据分析

根据您的例子：

```json
{
  "metadata": {
    "batch_indices": [0, 1, 4, 7, 8, 11]  // ← 6个候选项
  }
}
```

**6个候选项**处于"混合区"：
- 不算特别多（<8）
- 但已经开始出现归类思维的倾向
- 特别是当候选项之间的相似性复杂时

**您的case**:
- 6个关于"化学位移"的定义
- 其中有些是通用定义，有些是特定场景
- 这种"部分相同、部分不同"的模式特别容易触发归类思维

---

## 测试验证方法

### 测试1: 简单case（2-3个候选项）

**目的**: 验证基本功能是否正确

**数据**: 2-3个明显相同或明显不同的候选项

**预期**: 应该100%正确

### 测试2: 中等case（5-6个候选项）

**目的**: 验证在"混合区"的表现

**数据**: 您当前的实际数据

**预期**: 
- ✅ 不再出现"与第X组合并"的表述
- ✅ 不再出现representative不在members中的情况
- ✅ rationale与members一致

### 测试3: 复杂case（8-10个候选项）

**目的**: 压力测试

**数据**: 更多候选项，包含多个相似组

**观察**:
- 如果仍然出错，考虑降低max_batch_size
- 如果表现良好，说明prompt修改有效

---

## 监控指标

在测试过程中，关注以下指标：

### 1. **一致性错误率**
```python
def check_consistency(group):
    # 检查rationale中提到的候选项是否都在members中
    mentioned = extract_candidate_numbers(group['rationale'])
    members_set = set(group['members'])
    missing = mentioned - members_set
    return len(missing) == 0
```

### 2. **归类语言出现率**
```python
def check_categorization_language(group):
    # 检查是否包含"与X组合并"、"归入X组"等归类语言
    forbidden_patterns = ['与.*组合并', '归入.*组', 'merge with group']
    rationale = group['rationale']
    return any(re.search(pattern, rationale) for pattern in forbidden_patterns)
```

### 3. **representative合理性**
```python
def check_representative_validity(group):
    # representative必须在members中
    return group['representative'] in group['members']
```

---

## 预期改善效果

### 修改前的典型错误

```json
{
  "groups": [
    {"rationale": "...", "members": [1], "representative": 1},
    {"rationale": "与[1]一致，予以合并", "members": [5], "representative": 1},
    {"rationale": "与[1][5]合并", "members": [6], "representative": 1}
  ]
}
```

### 修改后的预期输出

```json
{
  "groups": [
    {
      "rationale": "候选项[1]、[5]、[6]都是对化学位移的定义性描述，虽然措辞不同，但都指向同一个物理概念：原子核共振频率在不同化学环境下的差异。三者可互换使用而不丢失核心信息。",
      "members": [1, 5, 6],
      "representative": 1
    }
  ]
}
```

**关键改进**:
- ✅ rationale明确列出了所有成员[1]、[5]、[6]
- ✅ members包含所有应该合并的候选项
- ✅ representative在members中
- ✅ 没有归类语言（"与X合并"）
- ✅ 独立完整的rationale

---

## 如果问题仍然存在

如果修改后仍然出现归类思维，可以考虑：

### 短期方案

1. **降低temperature**
   ```python
   # 在call_llm_api.py中
   self.temperature = 0.1  # 从0.3降到0.1
   ```

2. **减小batch size**
   ```yaml
   max_batch_size: 4  # 更激进的减小
   ```

3. **启用validation**
   ```yaml
   enable_semantic_dedup_validation: true
   ```

### 长期方案

1. **切换到更强的模型**
   - GPT-4o / Claude-3.5-Sonnet
   - 更强的模型有更好的指令遵循能力

2. **使用Few-shot示例**
   - 在prompt中加入2-3个完整的示例
   - 展示正确的分组过程

3. **两阶段LLM调用**
   - 第一阶段：只做分析，输出文本
   - 第二阶段：根据分析生成JSON

---

## 相关文件

1. **问题分析**: `semantic_dedup_rationale_members_inconsistency_20251105_054617.md`
2. **首次修改**: `prompt_enhancement_changes_20251105_055230.md`
3. **字段顺序发现**: `json_field_order_fix_20251105_060712.md`
4. **完整方案** (本文件): `complete_fix_grouping_vs_categorization_20251105_061626.md`

---

## 总结

### 核心发现

**LLM的归类思维** 是导致rationale与members不一致的根本原因：
- LLM逐个处理候选项，决定"它应该归到哪个组"
- 而不是全局规划，识别"哪些候选项是同一实体"
- 导致创建多个单member的groups，rationale却说"与X合并"

### 三层修改

1. **思维模式引导**: 在prompt开头强调"分组思维 vs 归类思维"
2. **执行顺序约束**: rationale先于members生成，强制先表达意图再执行
3. **语言模式禁止**: 绝对禁止"与X组合并"等归类语言

### 配置建议

**根据候选项数量调整**:
- 2-5个: 当前配置即可
- 6-10个: 考虑降低max_batch_size到5
- >10个: 必须降低max_batch_size或启用clustering

### 预期效果

修改后应该：
- ✅ 消除"与第X组合并"的表述
- ✅ 消除representative不在members中的错误
- ✅ rationale与members完全一致
- ✅ 每个group包含所有应该合并的候选项

---

感谢您的耐心测试和反馈！这些发现对改进系统非常有价值。
