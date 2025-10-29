# Prompt更新：基于信息完全一致性原则

## 更新日期
2025-10-29

## 核心改进

基于用户反馈，将head dedup prompt从"规则驱动"改为"原则驱动"，采用**信息完全一致性（Information Identity）**作为根本判断标准。

## 根本原则

```yaml
唯一判断标准: 信息完全一致性

定义：
  两个实体应该合并，当且仅当它们包含完全相同的信息

两个必要条件（都必须满足）：
  1. REFERENTIAL IDENTITY (指称相同)
     → 它们指向完全相同的真实世界对象
  
  2. INFORMATION EQUIVALENCE (信息等价)
     → 在任何上下文中，双向替换都完全无损
```

## 为什么这是更好的方案？

### 之前的问题（规则驱动）
```yaml
旧方法：
  - 检查5个维度（specificity, detail, formality...）
  - 根据concern数量分类（0-1→merge, 2-3→alias, 4+→separate）
  
问题：
  ✗ Case by case的规则堆砌
  ✗ 需要不断添加新规则
  ✗ 规则之间可能冲突
  ✗ 不够根本
```

### 现在的方案（原则驱动）
```yaml
新方法：
  - 唯一原则：信息是否完全一致？
  - 判断方法：替换双向无损测试
  
优点：
  ✓ 根本性：直接回答"什么是冗余"
  ✓ 简洁性：一个原则覆盖所有情况
  ✓ 完备性：不需要case by case
  ✓ 可解释性：清晰的判断依据
```

## 修改内容

### 1. Prompt核心逻辑

**旧版：**
```
- MERGE CONDITIONS - ALL must hold (4条规则)
- PROHIBITED MERGE REASONS (8条禁止原因)
- DECISION PROCEDURE (4步程序)
- REPRESENTATIVE SELECTION (6条标准)
```

**新版：**
```
STEP 1: REFERENTIAL IDENTITY CHECK
  问题：是否指向同一对象？

STEP 2: INFORMATION EQUIVALENCE CHECK
  关键：测试双向替换是否无损
  
  Test A - Entity 1 → Entity 2:
    • 有无信息损失？（精确度、细节、明确性）
    
  Test B - Entity 2 → Entity 1:
    • 有无信息损失？
  
  对称性评估：
    IF 两个方向都无损 → 合并
    IF 任一方向有损 → 不合并
```

### 2. 新增示例（关键）

**Example 2 - 不对称替换（应保留）：**
```
Entity A: "增加读出带宽" (specific)
Entity B: "加大带宽" (vague)

Test A→B: "通过增加读出带宽解决伪影"
       → "通过加大带宽解决伪影"
          信息损失: "读出"的精确性丢失 ✗

Test B→A: "解决方法：加大带宽"
       → "解决方法：增加读出带宽"
          信息损失: 无 ✓

结果: 不对称 → 不同信息 → 不合并

解释: Entity A包含更精确的信息（哪个带宽）。
     虽然指向同一操作，但A比B更精确。
```

这个示例直接针对用户提出的entity_565 vs 666的情况！

### 3. 输出格式变化

**旧版输出：**
```json
{
  "is_coreferent": true/false,
  "preferred_representative": "entity_XXX" or null,
  "rationale": "..."
}
```

**新版输出：**
```json
{
  "is_coreferent": true/false,
  "substitution_lossless_1to2": true/false/null,
  "substitution_lossless_2to1": true/false/null,
  "information_identity": true/false,
  "preferred_representative": "entity_XXX" or null,
  "rationale": "..."
}
```

**关键变化：**
- 新增 `substitution_lossless_1to2` - 记录1→2是否无损
- 新增 `substitution_lossless_2to1` - 记录2→1是否无损
- 新增 `information_identity` - 只有这个为true才合并
- `is_coreferent` 现在只表示"指称相同"，不足以判断是否合并

### 4. 代码逻辑变化

**旧版：**
```python
if is_coreferent and preferred_representative:
    merge_mapping[duplicate] = canonical
```

**新版：**
```python
# 只有信息完全一致才合并
if information_identity and preferred_representative:
    merge_mapping[duplicate] = canonical
    
# 记录"指称相同但信息不同"的情况
elif is_coreferent and not information_identity:
    logger.info(
        f"Coreferent but not identical: {node_id_1} and {node_id_2} "
        f"refer to same object but contain different information. "
        f"Keeping separate to preserve distinctions."
    )
```

## 修改的文件

### 1. `/workspace/config/base_config.yaml`
- 路径：`prompts.head_dedup.with_representative_selection`
- 完全重写prompt，基于信息完全一致性原则
- 简化结构，强调双向替换测试
- 添加asymmetric substitution示例

### 2. `/workspace/head_dedup_llm_driven_representative.py`

**修改的函数：**

#### a) `_get_embedded_prompt_template_v2` (行202-381)
- 更新嵌入式fallback prompt
- 与config中的prompt保持一致

#### b) `_parse_coreference_response_v2` (行383-454)
- 解析新的输出格式（包含substitution test结果）
- 验证：只有`information_identity=true`才允许合并
- 添加详细日志

#### c) `_validate_candidates_with_llm_v2` (行65-127)
- 使用新的解析结果
- 区分"coreferent"和"information_identity"
- 记录metadata中的substitution test结果
- 特别记录"指称相同但信息不同"的case

## 预期效果

### 对于entity_565 vs 666案例

**使用旧prompt：**
```
可能判断：合并
理由：同社区、同场景、同操作
问题：忽略了精确度差异
```

**使用新prompt：**
```
预期判断：不合并
理由：
  - is_coreferent: true (都指带宽调整)
  - substitution_lossless_1to2: false ("读出"精确性丢失)
  - substitution_lossless_2to1: true (无损失)
  - information_identity: false (不对称)
  - 决策：保留两个实体
```

### 整体效果

1. **更保守的合并策略**
   - 只合并信息完全等价的实体
   - 保留精确度差异（specific vs vague）
   - 保留详细程度差异（detailed vs simple）
   - 保留上下文绑定差异（scenario-specific）

2. **更清晰的判断依据**
   - 不再依赖模糊的规则列表
   - 直接测试：替换是否无损
   - 可追溯：记录每个方向的测试结果

3. **更好的信息保留**
   - 优先保留信息，而非简化图谱
   - False negatives（漏合并）> False positives（错误合并）
   - 保留知识的层次性和多样性

## 向后兼容性

### 配置兼容
- ✓ 保持相同的配置key：`with_representative_selection`
- ✓ 输出格式向后兼容：保留所有旧字段
- ✓ 新增字段都有默认值

### 代码兼容
- ✓ 函数签名没有变化
- ✓ 返回值结构相同
- ✓ 只是判断逻辑更严格

## 测试建议

### 1. 对称替换案例（应该合并）
```python
test_case_1 = {
    "entity_1": "United Nations",
    "entity_2": "UN",
    "expected": {
        "information_identity": True,
        "should_merge": True
    }
}
```

### 2. 不对称替换案例（不应合并）
```python
test_case_2 = {
    "entity_1": "增加读出带宽",
    "entity_2": "加大带宽",
    "expected": {
        "is_coreferent": True,
        "substitution_lossless_1to2": False,  # 有损失
        "substitution_lossless_2to1": True,   # 无损失
        "information_identity": False,
        "should_merge": False
    }
}
```

### 3. 跨场景案例（不应合并）
```python
test_case_3 = {
    "entity_1": "提高带宽（流动伪影）",
    "entity_2": "提高带宽（化学位移伪影）",
    "expected": {
        "is_coreferent": False,  # 或 True但information_identity=False
        "information_identity": False,
        "should_merge": False
    }
}
```

## 监控指标

建议监控以下新指标：

1. **信息一致性比率**
   ```python
   coreferent_but_not_identical = count(
       is_coreferent=True and information_identity=False
   )
   ```
   这个指标反映了有多少"指称相同但信息不同"的case被保留

2. **替换对称性分布**
   ```python
   asymmetric_substitution = count(
       substitution_lossless_1to2 != substitution_lossless_2to1
   )
   ```
   反映精确度/详细度差异的频率

3. **合并决策变化**
   - 对比旧prompt和新prompt的合并数量
   - 预期：新prompt合并数量减少（更保守）
   - 验证：人工审查被保留的case，确认是否合理

## 文档更新

建议更新以下文档：

1. **HEAD_DEDUP_IMPLEMENTATION_GUIDE.md**
   - 添加"信息完全一致性原则"章节
   - 更新判断标准说明
   - 添加替换测试示例

2. **DUAL_LLM_GUIDE.md**
   - 如果涉及head dedup，更新相关说明

3. **README或主文档**
   - 说明去重哲学：保留信息 > 简化图谱

## 总结

这次更新的核心价值：

1. **从根本原则出发**：不是case by case的规则，而是统一的信息一致性原则
2. **更好的信息保留**：只合并完全等价的实体，保留有价值的区分
3. **更清晰的逻辑**：替换双向无损测试，简单直接
4. **可追溯可验证**：记录每个方向的测试结果

**这完全符合用户的建议：按照初衷，判断信息是否完全一致，替换是否无损！**
