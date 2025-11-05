# Prompt设计对比：Case by Case vs 基于原则

## 问题：什么是"Case by Case"？

"Case by Case"指的是在prompt中使用**具体领域的案例**来教LLM如何判断，而不是教授通用的判断原则。

### ❌ Case by Case的问题

1. **过度拟合**：LLM记住了具体案例的答案，而不是理解背后的原则
2. **泛化能力差**：遇到不同领域的问题时表现不一致
3. **提示答案**：如果输入恰好是例子中的案例，LLM直接照搬
4. **维护困难**：每个新领域都需要新例子

### ✓ 基于原则的优势

1. **通用性强**：适用于任何领域（医学、地理、技术、化学...）
2. **泛化能力好**：LLM学会了判断方法，而不是记忆答案
3. **一致性高**：基于相同原则做决策，结果更稳定
4. **易于维护**：不需要为每个领域添加例子

## 具体对比

### 对比1：错误示例

**❌ Case by Case版本：**
```
Example of WRONG reasoning:
- ECG门控、VCG门控、指脉门控 all use physiological signals for gating
- They achieve the same goal (reduce motion artifacts)
- ❌ WRONG: Merge them because they're similar
- ✓ CORRECT: Keep separate - they are THREE different techniques
```

**问题**：
- 直接使用了用户提供的具体案例
- 如果再遇到门控扫描，LLM可能直接照搬答案
- 对其他技术领域（如"不同的图像处理算法"）可能不适用

**✓ 基于原则版本：**
```
WRONG REASONING (common mistakes):
❌ "Entity_A and Entity_B serve the same purpose" → MERGE
❌ "Entity_A and Entity_B belong to the same category" → MERGE

CORRECT REASONING:
✓ "Entity_A and Entity_B are different names for THE SAME entity" → MERGE

The difference:
• SIMILAR entities: Method_1, Method_2, Method_3 (all solve Problem_X)
  → Three DIFFERENT methods → DO NOT MERGE
  
• SAME entity with different names: "Name_1", "Name_2", "Name_3" (all refer to Object_Y)
  → Three expressions of ONE entity → MERGE
```

**优点**：
- 使用抽象占位符（Method_1, Entity_A等）
- 教授判断原则，不是记忆案例
- 适用于任何领域

### 对比2：替换测试

**❌ Case by Case版本：**
```
TEST 1 - SUBSTITUTION:
If text says "研究使用了X", can you replace X with Y without changing the fact?
- "使用了ECG门控" → "使用了指脉门控" = ❌ CHANGES FACT → Different entities
- "位于New York" → "位于NYC" = ✓ SAME FACT → Same entity
```

**问题**：
- 又一次使用了门控扫描案例
- NYC例子虽然通用，但与医学领域混杂

**✓ 基于原则版本：**
```
╔════════════════════════════════════════════════════════════════════════╗
║ STEP 2: SUBSTITUTION TEST                                              ║
╚════════════════════════════════════════════════════════════════════════╝

Question: "If a text says 'Property holds for [i]', can I replace [i] with [j] 
without changing the truth value or losing information?"

Test scenarios:
• Scenario 1: "Study used [i]" → "Study used [j]"
  - If this changes which method/entity was used → DIFFERENT entities
  - If this just uses a different name for the same thing → SAME entity

Key question: Would the substitution change FACTS or just WORDING?
• Changes facts → Different entities
• Changes only wording → Same entity
```

**优点**：
- 使用抽象占位符[i], [j]
- 关注测试方法，不是具体案例
- 通用的测试场景

### 对比3：多值关系警告

**❌ Case by Case版本：**
```
TEST 2 - INFORMATION LOSS:
Would merging X and Y lose information?
- Merging "ECG门控" and "VCG门控" → ❌ YES, loses which technique was used
- Merging "New York City" and "NYC" → ✓ NO, just different spellings
```

**问题**：
- 第三次使用门控案例！
- LLM会过度记住这个特定案例

**✓ 基于原则版本：**
```
╔════════════════════════════════════════════════════════════════════════╗
║ STEP 3: INFORMATION LOSS TEST                                          ║
╚════════════════════════════════════════════════════════════════════════╝

Question: "If I merge [i] and [j], do I lose information about which specific 
entity/method/solution was involved?"

Test:
• If YES → They are DIFFERENT entities (information loss means distinct referents)
• If NO → They might be SAME entity (no loss means just different expressions)

Examples:
• Merging "Technique_A" and "Technique_B"
  → Lose information about which technique was used
  → They are DIFFERENT entities

• Merging "Organization_X_full_name" and "Organization_X_abbreviation"
  → No information loss, just different name lengths
  → They are SAME entity
```

**优点**：
- 使用通用占位符
- 给出了两种典型场景，但不针对特定领域
- 可以应用到任何"技术"、"组织"、"方法"等

## 统计对比

### Case by Case版本的问题统计

| 位置 | 具体案例 | 出现次数 |
|------|---------|----------|
| 开头警告 | ECG/VCG/指脉门控 | 1次 |
| TEST 1 | ECG/指脉门控 | 1次 |
| TEST 2 | ECG/VCG门控 | 1次 |
| TEST 3 | 解决方案/别名 | 具体关系类型 |
| 总计 | **门控案例** | **3次！** |

**风险**：如果系统70%的问题是门控扫描，LLM学到的是"遇到门控就分开"，而不是判断原则。

### 基于原则版本

| 位置 | 使用方法 | 通用性 |
|------|---------|--------|
| 开头警告 | Method_1/Entity_A等抽象占位符 | ✓ 完全通用 |
| TEST 1 | [i], [j]占位符 + 通用场景 | ✓ 完全通用 |
| TEST 2 | Technique_A/Organization_X等 | ✓ 完全通用 |
| TEST 3 | 基于原则的启发式方法 | ✓ 完全通用 |

**优势**：可以处理任何领域的去重问题，不依赖记忆。

## 实验验证

### 测试1：医学领域（药物）

**输入**：
```
Head: 高血压
Relation: 治疗药物
Tails: [阿司匹林, Aspirin, 布洛芬]
```

**预期结果**：
- 阿司匹林 + Aspirin → 合并（同一药物的中英文）
- 布洛芬 → 独立（不同的药物）

**基于原则的prompt**: ✓ 能正确处理（通过"不同语言测同一实体"原则）

**Case by case prompt**: ❌ 可能困惑（没见过药物案例）

### 测试2：地理领域（景点）

**输入**：
```
Head: 旅游目的地
Relation: 包括
Tails: [景点A, 景点B, 景点C]
```

**预期结果**：
- 三个景点各自独立（不同的地点）

**基于原则的prompt**: ✓ 能正确处理（"包括"是多值关系，自动警告）

**Case by case prompt**: ❌ 可能困惑（只见过门控扫描）

### 测试3：恰好是门控扫描

**输入**：
```
Head: 流动伪影
Relation: 解决方案
Tails: [ECG门控, VCG门控, 指脉门控]
```

**预期结果**：
- 三个门控技术各自独立

**基于原则的prompt**: ✓ 通过原则判断（三个不同技术）

**Case by case prompt**: ⚠️ 可能直接照抄例子（记住了答案，而不是理解原则）

## 核心设计原则

### ✓ DO: 应该这样设计

1. **使用抽象占位符**
   - Entity_A, Entity_B
   - Method_1, Method_2
   - [i], [j], [k]
   - Technique_X, Solution_Y

2. **教授判断方法，不是答案**
   - "如何判断是否为同一实体"
   - "三步决策流程"
   - "信息丢失测试"

3. **使用极简单、跨领域的概念**
   - 如果必须用例子，用最简单的
   - 例如：组织名称全称vs缩写
   - 例如：不同语言的相同物体名称

4. **关注原则和规律**
   - "多值关系的特征"
   - "相似性vs同一性的区别"
   - "替换测试的逻辑"

### ❌ DON'T: 不应该这样设计

1. **使用用户的具体案例**
   - ❌ 用户问的门控扫描案例
   - ❌ 用户问的化学位移案例

2. **使用特定领域的术语**
   - ❌ MRI技术术语
   - ❌ 医学专业术语
   - ❌ 任何需要领域知识才能理解的例子

3. **重复使用同一个例子**
   - ❌ 门控出现3次
   - 这会让LLM过度记忆

4. **混杂不同领域的例子**
   - ❌ 医学(门控) + 地理(NYC) + 化学
   - 没有一致的教学逻辑

## 如何检查Prompt是否Case by Case

### 自查清单

运行以下检查：

```bash
# 检查1：是否包含用户案例的关键词
grep -i "ECG\|VCG\|指脉\|门控\|化学位移" your_prompt.txt

# 检查2：是否包含过于具体的领域术语
grep -i "MRI\|CT\|磁共振\|伪影" your_prompt.txt

# 检查3：计算具体案例出现次数
grep -o "具体案例名称" your_prompt.txt | wc -l
```

如果任何检查返回结果，说明有case by case问题。

### 替换策略

| 发现 | 替换为 |
|------|--------|
| "ECG门控" | "Method_A" 或 "Technique_1" |
| "化学位移伪影" | "Phenomenon_X" 或 "Effect_Y" |
| "New York City" vs "NYC" | "Full_Name" vs "Abbreviation" |
| 任何专业术语 | 抽象占位符或通用概念 |

## 总结

### Case by Case方法
- ❌ 适用范围窄（只对训练案例有效）
- ❌ 泛化能力差（新领域需要新例子）
- ❌ 容易过拟合（记住答案而非原则）
- ❌ 维护成本高（不断添加例子）

### 基于原则方法
- ✓ 适用范围广（任何领域）
- ✓ 泛化能力强（自动应用到新案例）
- ✓ 学习原则（理解判断逻辑）
- ✓ 维护成本低（原则稳定）

## 建议

**立即采用**：`principle_based_semantic_dedup_prompt.py`

这个prompt：
- ✓ 完全避免了case by case
- ✓ 使用抽象原则和占位符
- ✓ 可以处理任何领域的去重
- ✓ 包含系统的决策流程
- ✓ 有明确的自检清单

**验证方法**：
1. 在医学领域测试（药物去重）
2. 在地理领域测试（地点去重）
3. 在技术领域测试（算法/方法去重）
4. 观察结果是否一致、准确

如果三个不同领域都表现良好，说明prompt设计成功！
