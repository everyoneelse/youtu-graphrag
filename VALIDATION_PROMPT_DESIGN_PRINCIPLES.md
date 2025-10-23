# 校验Prompt设计原则

## 问题：Case-by-Case设计的局限

### ❌ 错误的方式：列举具体模式

```python
# 不好的设计
PROMPT = """
检测以下不一致模式：
1. Description说"合并"但members是分开的
2. Description说"相同"但不在同一个cluster
3. Description说"不同"但在同一个cluster
...
"""
```

**问题：**
- 限制了LLM的思考范围
- 只能检测列举的模式
- 遗漏未预见的不一致类型
- 随着新case出现，需要不断添加规则

### ✅ 正确的方式：原则驱动设计

```python
# 好的设计
PROMPT = """
核心原则：
- 检查description和members是否逻辑一致
- 如果description说items相同/相似，它们应该在同一个cluster
- 如果description说items不同，它们应该在不同cluster
- 使用常识和语义理解，不要局限于预定义模式
- 发现任何类型的不一致
"""
```

**优势：**
- LLM可以发现任何类型的不一致
- 利用LLM的语义理解能力
- 不需要穷举所有可能的case
- 更具泛化能力

## 改进后的Prompt设计

### 核心理念

**从"模式匹配"转向"原则理解"**

| 维度 | Case-by-Case | 原则驱动 |
|------|--------------|----------|
| 检测范围 | 仅限列举的模式 | 任何不一致 |
| 泛化能力 | 差 | 强 |
| 维护成本 | 高（需不断添加） | 低（原则不变） |
| LLM自由度 | 低 | 高 |
| 遗漏风险 | 高 | 低 |

### 设计要点

#### 1. 强调核心原则

```
CONSISTENCY PRINCIPLE:
A cluster is CONSISTENT when:
  ✅ Description accurately reflects WHO is in the cluster
  ✅ If description says items are "same", they ARE in the same cluster
  ✅ Members array matches what description claims
```

**而不是：**
```
PATTERNS TO DETECT:
1. Pattern A
2. Pattern B
3. Pattern C
```

#### 2. 鼓励语义理解

```
VALIDATION APPROACH:
- Use your understanding of semantics, not just keyword matching
- Consider the INTENT behind the description
- Use common sense and logical reasoning
```

#### 3. 明确"不要限制"

```
IMPORTANT:
- Do NOT limit yourself to predefined patterns
- Find ANY inconsistency
- Use logical reasoning
```

#### 4. 提供指导性例子（而非穷举）

```
EXAMPLE (for reference only - find ANY type of inconsistency):
[一个例子说明什么是不一致]
```

**注意：**例子只是"for reference"，不是完整列表

## 实际应用

### 改进前后对比

**改进前（Case-by-Case）：**
```python
"INCONSISTENCY PATTERNS TO DETECT:\n"
"1. ❌ CONTRADICTION: Description says 'merged' but SEPARATE\n"
"2. ❌ SINGLETON MISMATCH: Says 'same as X' but only 1 member\n"
"3. ❌ IMPROPER GROUPING: Says 'distinct' but SAME cluster\n"
```

**改进后（原则驱动）：**
```python
"CONSISTENCY PRINCIPLE:\n"
"✅ Description and members match logically\n"
"✅ If description says 'same', they ARE together\n"
"✅ If description says 'different', they ARE separate\n"
"❌ ANY logical mismatch is inconsistent\n"
"\n"
"IMPORTANT:\n"
"- Do NOT limit to predefined patterns\n"
"- Find ANY inconsistency using common sense\n"
```

### 效果预期

| 不一致类型 | Case-by-Case | 原则驱动 |
|-----------|--------------|----------|
| 列举的模式 | ✅ 能检测 | ✅ 能检测 |
| 未列举的模式 | ❌ 检测不到 | ✅ 能检测 |
| 新出现的case | ❌ 需要更新prompt | ✅ 自动适应 |
| 复杂语义不一致 | ❌ 可能遗漏 | ✅ LLM理解 |

## 通用设计原则

### 1. 强调"为什么"而非"是什么"

❌ **不好：**列举所有不一致的情况  
✅ **好：**解释什么叫"一致"，让LLM推导出不一致

### 2. 使用原则而非规则

❌ **不好：**如果X则Y，如果A则B...  
✅ **好：**核心原则是Z，用Z判断一切

### 3. 鼓励推理而非匹配

❌ **不好：**查找这些关键词...  
✅ **好：**理解语义，使用常识...

### 4. 开放而非封闭

❌ **不好：**只检测以下3种模式  
✅ **好：**发现任何不一致

### 5. 示例是参考而非边界

❌ **不好：**检测以下情况：[例子1, 例子2, 例子3]  
✅ **好：**例如这种情况：[例子]（仅供参考，不限于此）

## 代码实现

### 当前实现

```python
DEFAULT_CLUSTERING_VALIDATION_PROMPT = (
    # ...
    "CONSISTENCY PRINCIPLE:\n"
    "A cluster is CONSISTENT when:\n"
    "  ✅ Description accurately reflects WHO is in the cluster\n"
    "  ✅ If description says 'same/similar', they ARE together\n"
    "  ✅ Members array matches description's claim\n\n"
    
    "A cluster is INCONSISTENT when:\n"
    "  ❌ Description and members contradict\n"
    "  ❌ ANY logical mismatch\n\n"
    
    "VALIDATION APPROACH:\n"
    "- Use semantic understanding, not just keywords\n"
    "- Consider INTENT\n"
    "- Use common sense\n\n"
    
    "IMPORTANT:\n"
    "- Do NOT limit to predefined patterns\n"
    "- Find ANY inconsistency\n"
    # ...
)
```

### 关键特性

1. **原则清晰**：什么是一致/不一致
2. **方法指导**：如何检查（语义理解）
3. **明确开放**：不限于预定义模式
4. **鼓励推理**：使用常识和逻辑

## 泛化到其他Prompt

这个设计原则适用于所有需要LLM判断的场景：

### 聚类Prompt

❌ **不好：**
```
把以下情况归为一组：
- 同义词
- 拼写变体
- 缩写
...
```

✅ **好：**
```
核心原则：语义相同的归为一组
使用你的语言理解能力判断
```

### 去重Prompt

❌ **不好：**
```
以下是重复的标准：
1. 完全相同
2. 只有标点不同
3. 只有大小写不同
...
```

✅ **好：**
```
核心原则：指向同一实体/概念的是重复
考虑语义而非表面形式
```

## 实践建议

### 设计新Prompt时

1. ✅ 先明确**核心原则**
2. ✅ 解释**为什么**这样判断
3. ✅ 提供**思考方法**
4. ✅ 强调**不要限制**
5. ❌ 避免列举所有可能case

### 检查现有Prompt

问自己：
- 是否列举了具体模式？ → 改为原则
- 是否限制了LLM的思考？ → 开放边界
- 是否只是关键词匹配？ → 强调语义
- 是否需要不断添加case？ → 重构为原则驱动

### 测试Prompt质量

好的原则驱动prompt应该能：
- ✅ 处理训练中从未见过的case
- ✅ 发现意料之外的不一致
- ✅ 不需要频繁更新
- ✅ 泛化到新领域

## 总结

### 核心思想

**授人以鱼不如授人以渔**

- Case-by-Case = 给LLM一堆鱼（具体模式）
- 原则驱动 = 教LLM钓鱼（理解原则）

### 关键区别

| 维度 | Case-by-Case | 原则驱动 |
|------|--------------|----------|
| 覆盖范围 | 有限 | 无限 |
| 维护成本 | 高 | 低 |
| LLM能力 | 模式匹配 | 语义理解 |
| 泛化能力 | 差 | 强 |
| 新case应对 | 需要更新 | 自动适应 |

### 最佳实践

1. **原则优先** - 明确核心原则
2. **开放边界** - 不限制范围
3. **语义理解** - 利用LLM能力
4. **逻辑推理** - 鼓励常识判断
5. **示例参考** - 而非穷举

---

**设计日期**: 2025-10-23  
**适用范围**: 所有需要LLM判断的Prompt设计  
**核心理念**: 授人以渔，而非授人以鱼
