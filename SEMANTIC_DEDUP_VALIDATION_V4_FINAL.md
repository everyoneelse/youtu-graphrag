# Semantic Dedup Validation V4.0 - 真正的原则驱动

## 📅 日期: 2025-10-23

## 🎯 问题

V1/V2/V3都是**case by case**的设计：

### V1-V3的问题

```python
# ❌ 列举具体短语
"可合并", "应合并", "完全一致", "归入一组", "故归入一组"...

# ❌ 列举具体案例
"振铃伪影", "边缘振荡伪影", "54.7°角度"...

# ❌ 具体的检测步骤
Step 1: 检查是否有"故归入一组"
Step 2: 检查members是否包含...
```

### 根本问题

> **"如果采用case by case的方式修改，那要修改到什么时候？"**

永远列举不完所有可能的：
- 表达方式（可合并、应合并、宜合并、建议合并、推荐合并...）
- 语言变体（中文、英文、繁体、口语、书面语...）
- 具体场景（医学、技术、商业...）

## ✅ V4.0 解决方案：真正的原则驱动

### 核心原则（唯一的规则）

```
A group is CONSISTENT when:
  rationale's intended action = actual grouping

That's it. Nothing more.
```

### V4.0 Prompt（完整）

```python
You are validating semantic deduplication results.

INPUT:
{dedup_results}

TASK:
Check if each group's rationale is consistent with its members array.

CONSISTENCY RULE:
A group is CONSISTENT when the rationale's intended action matches the actual grouping.

Examples:
  ✅ Rationale expresses intent to merge with another group
     → Members array includes that group's items
  
  ✅ Rationale expresses intent to keep this group independent
     → Members array contains only this group's items
  
  ❌ Rationale expresses intent to merge
     → But members array shows items are still separate
  
  ❌ Rationale expresses intent to stay independent
     → But members array includes items from other groups

HOW TO VALIDATE:
1. Read the rationale and understand what action it intends (merge or stay separate)
2. Look at the members array and see what actually happened
3. If intent ≠ reality, report inconsistency

IMPORTANT:
- Use your language understanding to determine the rationale's intent
- Don't look for specific keywords - understand the meaning
- Focus only on structural consistency (intent vs actual grouping)
- Ignore content accuracy issues (whether rationale correctly describes original text)

OUTPUT FORMAT:
Return strict JSON:
{
  "has_inconsistencies": true/false,
  "inconsistencies": [...],
  "corrected_groups": [...]
}
```

**总长度**: ~30行（vs V3的80行）

## 🔑 关键设计决策

### 1. 信任LLM的理解能力

**Before (V1-V3)**:
```
列举短语: "可合并", "应合并", "故归入一组"...
→ 暗示: LLM需要我告诉它什么短语表示"合并"
```

**After (V4)**:
```
"Use your language understanding to determine the rationale's intent"
→ 信任: LLM已经懂中文，它知道什么叫"合并"
```

### 2. 只给原则，不给模式

**Before (V1-V3)**:
```python
if rationale.contains("可合并"):
    check_if_merged()
elif rationale.contains("故归入一组"):
    check_if_merged()
elif rationale.contains("应该合并"):
    check_if_merged()
# ... 永远列举不完
```

**After (V4)**:
```python
intent = understand_rationale_meaning(rationale)
reality = check_members_array(members)
return intent == reality
```

### 3. 去除所有具体内容

**Removed**:
- ❌ 短语列表
- ❌ 关键词标注
- ❌ 具体案例
- ❌ Step-by-step演示
- ❌ 语言标注（English/Chinese）

**Kept**:
- ✅ 核心原则：intent = reality
- ✅ 任务说明
- ✅ 输出格式

## 📊 版本对比

| 方面 | V1 | V2 | V3 | V4 |
|------|----|----|----|----|
| **行数** | 150 | 150 | 80 | 30 |
| **短语列表** | 有 | 有 | 有 | 无 |
| **具体案例** | 有 | 有 | 有 | 无 |
| **关键词标注** | 有 | 有 | 有 | 无 |
| **设计方式** | Case | Case | Case | Principle |
| **信任LLM** | 低 | 低 | 中 | 高 |

## 💡 设计哲学

### "授人以鱼 vs 授人以渔"

**V1-V3 (授人以鱼)**:
```
我告诉你：
- "可合并"表示要合并
- "故归入一组"表示要合并
- "应该合并"表示要合并
- ...
```

**V4 (授人以渔)**:
```
我告诉你：
- 理解rationale的意图
- 看看实际是否这样做了
- 不一致就报告
```

### "Don't Repeat Yourself"原则

LLM已经被训练理解：
- ✅ "可合并" = can merge
- ✅ "故归入一组" = should be grouped
- ✅ "保持独立" = keep independent

我不需要再教一遍！

### Occam's Razor（奥卡姆剃刀）

> "如无必要，勿增实体"

如果LLM能理解自然语言，为什么要列举所有可能的表达方式？

## 🎯 V4.0的核心

只有**一个规则**：

```
intent(rationale) == reality(members) → CONSISTENT
intent(rationale) != reality(members) → INCONSISTENT
```

Everything else is just noise.

## 🧪 测试期望

对于用户的案例：
```python
{
  'members': [4],
  'rationale': '...故归入一组'
}
```

LLM应该能够：
1. 理解"故归入一组"的意图是MERGE
2. 看到members=[4]说明实际是SEPARATE
3. 判断MERGE ≠ SEPARATE
4. 报告inconsistency

**不需要我告诉它"故归入一组"是什么意思！**

## 📝 V4.0完整Prompt

```
You are validating semantic deduplication results.

INPUT:
{dedup_results}

TASK:
Check if each group's rationale is consistent with its members array.

CONSISTENCY RULE:
A group is CONSISTENT when the rationale's intended action matches the actual grouping.

Examples:
  ✅ Rationale expresses intent to merge → Members show merged
  ✅ Rationale expresses intent to stay separate → Members show separate
  ❌ Rationale expresses intent to merge → Members show separate
  ❌ Rationale expresses intent to stay separate → Members show merged

HOW TO VALIDATE:
1. Understand what the rationale intends
2. See what actually happened in members array
3. If intent ≠ reality, report it

IMPORTANT:
- Use your language understanding
- Don't look for keywords - understand meaning
- Focus on structural consistency only
- Ignore content accuracy

OUTPUT: JSON with has_inconsistencies, inconsistencies, corrected_groups
```

**就这么简单！**

## 🚀 为什么V4会成功

1. **LLM已经懂语言** - 不需要我教它"故归入一组"是什么意思
2. **原则永恒** - intent vs reality这个原则永远有效
3. **可维护** - 30行vs 150行，简单10倍
4. **可扩展** - 任何语言、任何领域都适用

## ⚠️ 如果V4仍然失败

那说明不是prompt的问题，而是：
1. LLM能力不足（换更强的模型）
2. 任务本身太难（需要分步调用）
3. 输入格式有问题（检查数据格式）

但**不应该**再去列举更多短语和案例！

---

**版本**: V4.0 - The Final Version  
**原则**: Trust the LLM. Give principles, not patterns.  
**行数**: 30 (vs V1的150)  
**状态**: ✅ Ready to test
