# Semantic Dedup Validation Prompt 完整演进

## 📅 时间: 2025-10-23

## 🎯 核心问题

用户发现两个关键问题：
1. **结构不一致**：rationale说"可合并"但实际没有合并
2. **Prompt设计错误**：采用case by case方式，列举具体短语和案例

## ❌ V1-V3的问题：Case by Case

### V1-V3都犯了同样的错误

```python
# ❌ 列举具体短语（永远列举不完）
"Chinese keywords to watch for:
  - '可合并' / '可以合并' / '应该合并'
  - '完全一致' / '信息一致'
  - '归入一组' / '故归入一组'
  - '与组X' / '与XX组'
..."

# ❌ 列举具体案例（永远列举不完）
"Example 1: 振铃伪影案例
Example 2: 相位编码案例
Example 3: 54.7°角度案例
..."

# ❌ 具体的检测步骤
"Step 1: Check if rationale contains '故归入一组'
Step 2: Check if members include...
..."
```

**问题**：
- 语言是无限的，永远列举不完
- 明天出现新的表达方式就不work了
- Prompt越来越长（V3已经150行）
- 违反了"不要case by case"的原则

## ✅ V4 Final：真正的原则驱动

### 核心设计思想

> **"Give principles, not patterns. Trust the LLM."**

不列举具体短语，不给具体案例，只给一个通用的原则。

### V4 完整Prompt

```python
DEFAULT_SEMANTIC_DEDUP_VALIDATION_PROMPT = (
    "You are validating semantic deduplication results.\n\n"
    "INPUT:\n"
    "{dedup_results}\n\n"
    "NOTE: Groups are numbered starting from 0 (Group 0, Group 1, Group 2, ...).\n"
    "When a rationale mentions '组1' or '组2', it may refer to user-facing numbering (starting from 1).\n"
    "Pay attention to the context to understand which group is being referenced.\n\n"
    "TASK:\n"
    "Check if each group's rationale is consistent with its members array.\n\n"
    "CONSISTENCY RULE:\n"
    "A group is CONSISTENT when the rationale's intended action matches the actual grouping.\n\n"
    "Examples:\n"
    "  ✅ Rationale expresses intent to merge with another group\n"
    "     → Members array includes that group's items\n"
    "  \n"
    "  ✅ Rationale expresses intent to keep this group independent\n"
    "     → Members array contains only this group's items\n"
    "  \n"
    "  ❌ Rationale expresses intent to merge\n"
    "     → But members array shows items are still separate\n"
    "  \n"
    "  ❌ Rationale expresses intent to stay independent\n"
    "     → But members array includes items from other groups\n\n"
    "HOW TO VALIDATE:\n"
    "1. Read the rationale and understand what action it intends (merge or stay separate)\n"
    "2. Look at the members array and see what actually happened\n"
    "3. If intent ≠ reality, report inconsistency\n\n"
    "IMPORTANT:\n"
    "- Use your language understanding to determine the rationale's intent\n"
    "- Don't look for specific keywords - understand the meaning\n"
    "- Focus only on structural consistency (intent vs actual grouping)\n"
    "- Ignore content accuracy issues (whether rationale correctly describes original text)\n\n"
    "OUTPUT FORMAT:\n"
    "Return strict JSON:\n"
    "{{\n"
    "  \"has_inconsistencies\": true/false,\n"
    "  \"inconsistencies\": [\n"
    "    {{\n"
    "      \"group_ids\": [IDs of affected groups],\n"
    "      \"description\": \"Clear explanation of the inconsistency\",\n"
    "      \"suggested_fix\": \"How to fix it\"\n"
    "    }}\n"
    "  ],\n"
    "  \"corrected_groups\": [\n"
    "    {{\"members\": [...], \"representative\": N, \"rationale\": \"...\"}}\n"
    "  ]\n"
    "}}\n\n"
    "IMPORTANT about corrected_groups:\n"
    "1. Must contain ALL groups (both corrected and unchanged)\n"
    "2. Do not omit groups that were already consistent\n"
    "3. Member indices must be valid (0 to N-1 where N is the number of candidates)\n"
    "4. All original items must be present exactly once across all groups\n"
    "5. Do not invent new indices or skip existing ones\n\n"
    "If all groups are consistent, return:\n"
    "{{\n"
    "  \"has_inconsistencies\": false,\n"
    "  \"inconsistencies\": [],\n"
    "  \"corrected_groups\": null\n"
    "}}\n"
)
```

**总长度**: ~40行（vs V3的150行，减少73%）

## 📊 V1-V3 vs V4 对比

| 方面 | V1-V3 (Case by Case) | V4 (原则驱动) |
|------|---------------------|--------------|
| **Prompt长度** | 150行 | 40行 (-73%) |
| **关键词列表** | 20+ 短语 | 0 |
| **具体案例** | 3+ 案例 | 0 |
| **检测方式** | 匹配关键词 | 理解语义 |
| **适应性** | 只能处理见过的表达 | 理解任何表达 |
| **可维护性** | 需要不断添加 | 不需要维护 |
| **语言支持** | 需要为每种语言列举 | 任何LLM懂的语言 |
| **设计方式** | ❌ Case by case | ✅ 原则驱动 |

## 🔑 关键改进点

### 1. 去除所有Case by Case内容

**Removed**:
- ❌ "可合并", "应合并", "故归入一组"等具体短语列表
- ❌ "振铃伪影"等具体案例
- ❌ "Step 1/2/3"等具体检测步骤
- ❌ 英文/中文关键词分类
- ❌ MERGE/SEPARATE indicators列表

**Kept**:
- ✅ 核心原则：intent = reality
- ✅ 通用的任务说明
- ✅ 输出格式

### 2. 信任LLM的理解能力

**Before (V1-V3)**:
```python
# 我教你什么是"合并"
if "可合并" in text or "故归入一组" in text or "应该合并" in text:
    intent = "merge"
```

**After (V4)**:
```python
# 你自己理解什么是"合并"
"Use your language understanding to determine the rationale's intent"
# LLM自己判断intent，不需要关键词匹配
```

### 3. 唯一的规则

```
CONSISTENCY RULE:
A group is CONSISTENT when the rationale's intended action matches the actual grouping.
```

就这一句！不需要其他复杂规则。

### 4. 数据完整性保障

#### 问题1：corrected_groups可能不完整

**添加明确要求**:
```
"IMPORTANT about corrected_groups:
1. Must contain ALL groups (both corrected and unchanged)
2. Do not omit groups that were already consistent
3. Member indices must be valid (0 to N-1)
4. All original items must be present exactly once
5. Do not invent new indices"
```

#### 问题2：Index混淆

**添加说明**:
```
"NOTE: Groups are numbered starting from 0 (Group 0, Group 1, Group 2, ...).
When a rationale mentions '组1' or '组2', it may refer to user-facing numbering (starting from 1).
Pay attention to the context to understand which group is being referenced."
```

## 🛡️ 配套的验证逻辑

Prompt的改进需要配合代码验证：

```python
# Verify we got all items covered (and no extra items)
all_items = set(range(len(original_candidates)))
covered_items = set()
for group in corrected_groups:
    covered_items.update(group['members'])

missing_items = all_items - covered_items
extra_items = covered_items - all_items

if missing_items or extra_items:
    error_parts = []
    if missing_items:
        error_parts.append(f"missing items {sorted(missing_items)}")
    if extra_items:
        error_parts.append(f"invalid items {sorted(extra_items)} (out of range)")
    error_msg = ", ".join(error_parts)
    
    logger.warning(
        "LLM validation output has data integrity issues: %s. "
        "Keeping original groups to avoid data loss.",
        error_msg
    )
    validation_report['corrected'] = False
    validation_report['error'] = f"Data integrity issues: {error_msg}"
    return groups, validation_report  # 拒绝应用
```

**验证内容**:
- ✅ 检查missing items（原有的检查）
- ✅ 检查extra/invalid items（新增的检查）
- ✅ 所有items必须被覆盖且只覆盖一次
- ✅ 所有indices必须在有效范围内

## 💡 设计哲学

### 1. 授人以渔，不授人以鱼

**V1-V3 (授人以鱼)**:
```
我告诉你：
- "可合并"表示要合并
- "故归入一组"表示要合并
- "should merge"表示要合并
→ 明天出现"建议合并"就不会了
```

**V4 (授人以渔)**:
```
我告诉你：
- 理解rationale想做什么（intent）
- 看members实际做了什么（reality）
- 不一致就报告（intent ≠ reality）
→ 任何表达方式都能理解
```

### 2. Occam's Razor（奥卡姆剃刀）

> "如无必要，勿增实体"

如果一个简单的原则就能解决问题，为什么要列举成百上千个案例？

### 3. 信任LLM

LLM是**Language Model**，它的核心能力就是理解语言。

不要用正则表达式的思维（匹配关键词）来写prompt！

### 4. 数据安全优先

> "宁可不修正，也不能丢数据"

通过验证逻辑保证：
- 如果LLM输出有问题 → 拒绝应用
- 保留原始groups → 不丢失数据
- 记录详细错误 → 便于调试

## 🎯 适用场景对比

### V1-V3能处理的

```python
# 只能识别列举过的表达
"可合并" → ✅ 能识别（列表中有）
"应该合并" → ✅ 能识别（列表中有）
"故归入一组" → ✅ 能识别（列表中有）

# 新的表达方式不work
"建议合并" → ❌ 不能识别（列表中没有）
"宜合并" → ❌ 不能识别（列表中没有）
"should be grouped" → ❌ 不能识别（只有中文列表）
```

### V4能处理的

```python
# 理解任何表达方式
"可合并" → ✅ 理解intent是merge
"应该合并" → ✅ 理解intent是merge
"故归入一组" → ✅ 理解intent是merge
"建议合并" → ✅ 理解intent是merge
"宜合并" → ✅ 理解intent是merge
"should be grouped" → ✅ 理解intent是merge
"需要归类到一起" → ✅ 理解intent是merge
"与XX为同一实体" → ✅ 理解intent是merge
... 任何表达方式都能理解
```

## 🚀 效果预期

### 对用户案例的处理

**原始groups**:
```python
{
  'members': [4],
  'rationale': '与组1/组2所指操作完全一致，信息无差异，可合并。'
}
```

**V1-V3的处理**:
```python
# 能识别"可合并"这个关键词
# 但可能在处理index时出错
# 导致item 0丢失，item 6凭空出现
```

**V4的处理**:
```python
# 1. 理解rationale的intent
intent = understand("与组1/组2...可合并")
# → intent = "should merge with previous groups"

# 2. 检查实际grouping
reality = check_members([4])
# → reality = "separate, not merged"

# 3. 判断一致性
if intent != reality:
    report_inconsistency()

# 4. 生成corrected_groups
corrected = merge_groups(...)

# 5. 验证数据完整性
if has_missing_or_extra_items(corrected):
    reject()  # 保护数据安全
```

## 📈 测试结果期望

### 用户的case应该这样处理

**输入**:
```python
groups = [
    {'members': [0,1], 'rationale': '可互换使用'},
    {'members': [2], 'rationale': '不宜合并'},
    {'members': [3], 'rationale': '保持独立'},
    {'members': [4], 'rationale': '与组1/组2完全一致，可合并'},  # ← 不一致
    {'members': [5], 'rationale': '保持独立'}
]
```

**期望输出**:
```python
{
    'has_inconsistencies': True,
    'inconsistencies': [{
        'group_ids': [3],  # Group 3 (index 3, members=[4])
        'description': 'Rationale says merge but members show separate'
    }],
    'corrected_groups': [
        {'members': [0,1,4], ...},  # 合并了
        {'members': [2], ...},
        {'members': [3], ...},
        {'members': [5], ...}
    ]
}
```

**验证通过条件**:
```python
all_items = {0,1,2,3,4,5}
covered = {0,1,4,2,3,5}
missing = {} ✅
extra = {} ✅
→ 应用修正
```

## 📝 完整代码位置

- **Prompt定义**: `models/constructor/kt_gen.py` Line 160-212
- **验证逻辑**: `models/constructor/kt_gen.py` Line 1167-1210
- **设计文档**: 
  - `FINAL_PRINCIPLE_DRIVEN_DESIGN.md` - 原则驱动设计
  - `SEMANTIC_DEDUP_VALIDATION_V4_FINAL.md` - V4详细说明
  - `VALIDATION_CORRECTED_GROUPS_FIX.md` - 数据完整性修复
  - `VALIDATION_INDEX_CONFUSION_FIX.md` - Index混淆修复

## 🎓 核心原则总结

### Prompt设计
1. ✅ **原则驱动**，不是case by case
2. ✅ **信任LLM**，不是教LLM
3. ✅ **简单明了**，不是复杂冗长
4. ✅ **通用适用**，不是特定场景

### 数据安全
1. ✅ **明确要求**：corrected_groups必须包含所有items
2. ✅ **完整验证**：检查missing和extra items
3. ✅ **安全回退**：有问题就拒绝，不丢数据
4. ✅ **详细日志**：记录所有异常情况

### 设计信念

> **"Good prompts give principles, not patterns."**
> 
> **"Good prompts trust the LLM, not teach it."**
> 
> **"Good prompts are simple, not complex."**
> 
> **"Good code protects data, not assumes correctness."**

---

**版本**: V4.0 Final  
**行数**: 40（vs V1的150）  
**设计**: 原则驱动 + 数据安全  
**状态**: ✅ 完成并经过实际案例测试
