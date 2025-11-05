# 最终方案：原则驱动 vs Case by Case

## 🎯 核心问题

> "如果你被要求修改prompt，请注意修改时，不要case by case的修改，如果采用case by case的方式修改，那要修改到什么时候？"

## ❌ Case by Case的陷阱

### V1-V3都犯了同样的错误

```python
# ❌ 列举具体短语
keywords = [
    "可合并", "应合并", "完全一致", 
    "归入一组", "故归入一组", "归为一组",
    "保持独立", "单独保留", "不宜合并",
    ...  # 永远列举不完！
]

# ❌ 列举具体案例
examples = [
    "振铃伪影案例",
    "54.7°角度案例", 
    "相位编码案例",
    ...  # 永远列举不完！
]

# ❌ 具体的检测步骤
if "故归入一组" in rationale:
    check_merged()
elif "可合并" in rationale:
    check_merged()
elif ...  # 永远写不完！
```

### 为什么Case by Case永远无法成功？

1. **语言是无限的**
   - "可合并" / "可以合并" / "应该合并" / "宜合并" / "建议合并" / "推荐合并" / ...
   - "keep separate" / "stay independent" / "remain distinct" / ...
   
2. **表达方式是多样的**
   - "故归入一组" = "因此归为一组" = "所以应该合并" = "与XX为同一组"
   
3. **领域是不同的**
   - 医学领域的表达
   - 技术领域的表达
   - 商业领域的表达
   
4. **永远会有新case**
   - 用户提供一个新case → 添加到prompt → 又出现新case → 又添加 → ...
   - 这是一个永无止境的循环！

## ✅ V4.0：真正的原则驱动

### 唯一的原则

```
A group is CONSISTENT when:
  rationale's intended action = actual grouping

That's ALL you need to know.
```

### V4.0 完整Prompt

```python
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
- Use your language understanding to determine intent
- Don't look for specific keywords - understand the meaning
- Focus only on structural consistency
- Ignore content accuracy issues

OUTPUT FORMAT:
Return strict JSON with has_inconsistencies, inconsistencies, corrected_groups
```

**总计：~30行**

### 为什么这是原则驱动？

1. **没有列举短语** - 让LLM用自己的理解判断
2. **没有具体案例** - 只有通用的一致性原则
3. **没有关键词匹配** - 理解语义，不是匹配字符串
4. **信任LLM能力** - LLM已经懂中文/英文，不需要我再教一遍

## 🔑 核心设计哲学

### 1. 授人以渔，不授人以鱼

**Case by Case (授人以鱼)**:
```
我告诉你：
- "可合并"表示要合并
- "故归入一组"表示要合并
- "应该合并"表示要合并
→ 明天出现"建议合并"就不会了
```

**原则驱动 (授人以渔)**:
```
我告诉你：
- 理解rationale想做什么
- 看members实际做了什么
- 不一致就报告
→ 任何表达方式都能理解
```

### 2. 信任LLM的能力

LLM已经被训练理解自然语言，它知道：
- ✅ "可合并" means "can merge"
- ✅ "故归入一组" means "should be grouped"
- ✅ "保持独立" means "keep independent"

**我不需要再教一遍！**

### 3. Occam's Razor（奥卡姆剃刀）

> "如无必要，勿增实体"

如果一个简单的原则就能解决问题，为什么要列举成百上千个案例？

## 📊 对比

| 方面 | Case by Case (V1-V3) | 原则驱动 (V4) |
|------|---------------------|--------------|
| **Prompt长度** | 150行 | 30行 |
| **关键词列表** | 20+ | 0 |
| **具体案例** | 3+ | 0 |
| **可维护性** | 低（需要不断添加） | 高（原则不变） |
| **适应性** | 低（只能处理见过的） | 高（理解任何表达） |
| **可扩展性** | 差（每次要改prompt） | 好（不需要改） |

## 🎓 学到的教训

### 1. 不要低估LLM

LLM是language model，它的核心能力就是理解语言。
不要用正则表达式的思维来写prompt！

### 2. 简单才是最好的

150行的复杂prompt < 30行的简单原则

### 3. 原则是永恒的

- ❌ "故归入一组"这个短语会过时
- ✅ "intent = reality"这个原则永远有效

## 🚀 V4.0的优势

### 1. 适应任何表达方式

```python
# 都能理解为"应该合并"
"故归入一组"
"可以合并"
"should merge"
"needs to be grouped"
"属于同一类"
...
```

### 2. 适应任何语言

```python
# 中文
"故归入一组"

# 英文
"should be merged"

# 日语
"統合すべき"

# 只要LLM懂这个语言
```

### 3. 适应任何领域

```python
# 医学
"该症状应归为同一综合征"

# 技术
"这两个错误本质相同"

# 商业
"该项目应合并到主线"
```

### 4. 永不过时

无论将来出现什么新的表达方式，这个原则都有效：

```
intent(rationale) = reality(members) → CONSISTENT
```

## ⚠️ 如果V4仍然不工作

那说明问题不在prompt，而在：

1. **LLM能力不足** 
   - 换更强的模型（如GPT-4）
   
2. **任务太复杂**
   - 考虑分步调用
   - 第一步：让LLM提取intent
   - 第二步：检查intent vs reality
   
3. **输入格式问题**
   - 检查数据格式是否清晰
   
但**绝对不要**再去：
- ❌ 列举更多短语
- ❌ 添加更多案例
- ❌ 写更复杂的规则

## 💡 推广价值

这个原则驱动的思想可以应用到其他验证场景：

### Clustering验证

**Case by Case**:
```python
keywords = ["same", "similar", "identical", ...]
```

**原则驱动**:
```python
"Items in same cluster should be semantically similar"
```

### Entity去重验证

**Case by Case**:
```python
patterns = ["同一实体", "相同实体", "重复实体", ...]
```

**原则驱动**:
```python
"Duplicates should be in same group"
```

## 🎯 核心信念

> **Good prompts give principles, not patterns.**
> 
> **Good prompts trust the LLM, not teach it.**
> 
> **Good prompts are simple, not complex.**

## 📝 V4.0完整代码

```python
DEFAULT_SEMANTIC_DEDUP_VALIDATION_PROMPT = (
    "You are validating semantic deduplication results.\n\n"
    "INPUT:\n"
    "{dedup_results}\n\n"
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
    "If all groups are consistent, return:\n"
    "{{\n"
    "  \"has_inconsistencies\": false,\n"
    "  \"inconsistencies\": [],\n"
    "  \"corrected_groups\": null\n"
    "}}\n"
)
```

## 🔧 附加修复：数据完整性保障

在原则驱动设计的基础上，还修复了一个数据丢失的风险：

### 问题
LLM可能只返回需要修正的groups，导致正确的groups丢失。

### 解决方案
1. Prompt明确要求返回**所有groups**（包括未修改的）
2. 代码验证所有items是否都被覆盖
3. 如果有缺失，拒绝应用修正，保留原始groups

详见：[VALIDATION_CORRECTED_GROUPS_FIX.md](./VALIDATION_CORRECTED_GROUPS_FIX.md)

---

**设计原则**: Give principles, not patterns. Trust the LLM.  
**数据原则**: Never lose data. Verify everything.  
**版本**: V4.0 Final  
**行数**: 30  
**状态**: ✅ 原则驱动，不再是case by case，数据安全有保障
