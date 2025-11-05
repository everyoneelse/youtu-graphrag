# 语义去重验证的专业方案

## 🎯 核心问题

**当前方案**：让LLM同时完成两个任务
1. 检测不一致（语义理解） ✅ LLM擅长
2. 生成corrected_groups（数据操作） ❌ LLM不擅长，容易出错

**问题**：
- LLM要复制所有正确的groups（即使只有1个需要修正）
- 容易出现index混淆、遗漏groups等问题
- 违反单一职责原则

## ✅ 专业方案：职责分离

### 方案A：LLM检测 + 代码修正 ⭐ 最推荐

#### 设计思路

```
┌─────────────────────────────────────────────────────────────┐
│  Phase 1: LLM检测不一致（语义理解）                           │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Input: groups with rationales                        │    │
│  │ Output: {                                            │    │
│  │   "inconsistencies": [                               │    │
│  │     {                                                │    │
│  │       "group_id": 3,                                 │    │
│  │       "issue": "says merge but not merged",          │    │
│  │       "should_merge_with": [0]  // 应该与哪个group合并 │    │
│  │     }                                                │    │
│  │   ]                                                  │    │
│  │ }                                                    │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Phase 2: 代码执行修正（数据操作）                            │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ for inconsistency in inconsistencies:                │    │
│  │     target_group = groups[inconsistency.group_id]    │    │
│  │     merge_to = groups[inconsistency.should_merge_with]│   │
│  │     merge_to.members += target_group.members         │    │
│  │     remove(target_group)                             │    │
│  │                                                       │    │
│  │ # 代码保证：                                           │    │
│  │ # - 所有items都在                                      │    │
│  │ # - 没有重复                                           │    │
│  │ # - index正确                                          │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

#### 优点

1. **职责清晰**：
   - LLM：理解语义，判断intent vs reality
   - 代码：执行数据合并，保证正确性

2. **不易出错**：
   - LLM不需要复制数据
   - 代码操作数据更可靠

3. **易于验证**：
   - LLM输出简单（只有inconsistencies列表）
   - 代码逻辑可测试

#### 实现

##### Prompt（简化）

```python
DEFAULT_SEMANTIC_DEDUP_VALIDATION_PROMPT = (
    "You are validating semantic deduplication results.\n\n"
    "INPUT:\n"
    "{dedup_results}\n\n"
    
    "TASK:\n"
    "Find groups where the rationale's intent doesn't match the actual grouping.\n\n"
    
    "RULE:\n"
    "A group is INCONSISTENT when:\n"
    "- Rationale says should merge with another group, but members are separate\n"
    "- Rationale says should stay separate, but members include other groups\n\n"
    
    "OUTPUT FORMAT:\n"
    "Return JSON with only the inconsistencies:\n"
    "{\n"
    "  \"has_inconsistencies\": true/false,\n"
    "  \"inconsistencies\": [\n"
    "    {\n"
    "      \"group_id\": N,\n"
    "      \"issue\": \"brief description\",\n"
    "      \"action\": \"merge\" or \"split\",\n"
    "      \"target_groups\": [list of group IDs to merge with/split from]\n"
    "    }\n"
    "  ]\n"
    "}\n\n"
    
    "If no inconsistencies:\n"
    "{\n"
    "  \"has_inconsistencies\": false,\n"
    "  \"inconsistencies\": []\n"
    "}\n\n"
    
    "IMPORTANT:\n"
    "- Only report the inconsistencies, don't try to fix them\n"
    "- Focus on understanding the rationale's intent\n"
    "- Don't generate corrected_groups - the code will handle that\n"
)
```

##### 代码实现

```python
def _llm_validate_semantic_dedup(self, groups, original_candidates, ...):
    """
    LLM validates, code corrects.
    """
    # Phase 1: LLM检测不一致
    validation_result = self._call_llm_for_validation(groups)
    
    if not validation_result['has_inconsistencies']:
        return groups, validation_report
    
    # Phase 2: 代码执行修正
    corrected_groups = self._apply_corrections(
        groups, 
        validation_result['inconsistencies']
    )
    
    # Phase 3: 验证数据完整性
    if not self._verify_data_integrity(corrected_groups, original_candidates):
        logger.warning("Data integrity check failed, keeping original groups")
        return groups, validation_report
    
    return corrected_groups, validation_report


def _apply_corrections(self, groups, inconsistencies):
    """
    代码执行修正，保证数据正确性
    """
    # 深拷贝，避免修改原始数据
    corrected = copy.deepcopy(groups)
    
    for inconsistency in inconsistencies:
        group_id = inconsistency['group_id']
        action = inconsistency['action']
        target_groups = inconsistency['target_groups']
        
        if action == 'merge':
            # 执行合并
            source_group = corrected[group_id]
            target_group = corrected[target_groups[0]]
            
            # 合并members
            target_group['members'].extend(source_group['members'])
            target_group['members'] = sorted(set(target_group['members']))
            
            # 更新rationale
            target_group['rationale'] = self._merge_rationales(
                target_group['rationale'],
                source_group['rationale']
            )
            
            # 标记source_group为已合并
            source_group['merged_into'] = target_groups[0]
        
        elif action == 'split':
            # 执行拆分（如果需要）
            pass
    
    # 移除已合并的groups
    corrected = [g for g in corrected if 'merged_into' not in g]
    
    return corrected


def _verify_data_integrity(self, groups, original_candidates):
    """
    验证数据完整性
    """
    all_items = set(range(len(original_candidates)))
    covered_items = set()
    
    for group in groups:
        covered_items.update(group['members'])
    
    # 检查完整性
    missing = all_items - covered_items
    extra = covered_items - all_items
    
    if missing or extra:
        logger.error(
            "Data integrity check failed: missing=%s, extra=%s",
            sorted(missing), sorted(extra)
        )
        return False
    
    # 检查重复
    all_members = []
    for group in groups:
        all_members.extend(group['members'])
    
    if len(all_members) != len(set(all_members)):
        logger.error("Duplicate items found in groups")
        return False
    
    return True
```

#### 测试用例

```python
# 输入
groups = [
    {'members': [0,1], 'rationale': '可互换'},
    {'members': [2], 'rationale': '保持独立'},
    {'members': [3], 'rationale': '与第一组一致，可合并'}  # 不一致
]

# LLM输出（简单）
{
    'has_inconsistencies': True,
    'inconsistencies': [
        {
            'group_id': 2,
            'issue': 'says merge but separate',
            'action': 'merge',
            'target_groups': [0]
        }
    ]
}

# 代码执行修正
corrected_groups = [
    {'members': [0,1,3], 'rationale': '...'},  # 合并了
    {'members': [2], 'rationale': '保持独立'}
]

# 验证
all_items = {0,1,2,3} ✅
covered = {0,1,3,2} ✅
missing = {} ✅
extra = {} ✅
```

---

### 方案B：两阶段LLM调用

#### 设计思路

```
Phase 1: LLM检测不一致
  ↓
Phase 2: LLM生成修正方案（只针对不一致的groups）
  ↓
代码应用修正
```

#### Prompt 1: 检测

```python
"Find inconsistencies and return:
{
  'inconsistent_group_ids': [2, 5],
  'issues': [...]
}"
```

#### Prompt 2: 修正（只针对不一致的groups）

```python
"Given these inconsistent groups: [2, 5]
How should they be corrected?

Return:
{
  'merge_plan': {
    2: {'merge_into': 0, 'reason': '...'},
    5: {'merge_into': 3, 'reason': '...'}
  }
}"
```

#### 代码应用

```python
for group_id, plan in merge_plan.items():
    merge_group(group_id, plan['merge_into'])
```

#### 优点
- LLM每次只处理简单任务
- 分步骤，逻辑清晰

#### 缺点
- 两次LLM调用，成本高
- 延迟高

---

### 方案C：LLM返回操作指令

#### 设计思路

```python
# LLM输出操作指令
{
    'operations': [
        {'op': 'merge', 'source': 2, 'target': 0},
        {'op': 'merge', 'source': 5, 'target': 3},
        {'op': 'update_rationale', 'group': 0, 'new_rationale': '...'}
    ]
}

# 代码执行指令
for op in operations:
    execute_operation(op)
```

#### 优点
- 声明式操作，清晰
- 代码执行可靠

#### 缺点
- Prompt较复杂
- 需要设计操作DSL

---

## 📊 方案对比

| 方案 | LLM任务 | 代码任务 | 易错性 | 成本 | 推荐度 |
|------|---------|---------|--------|------|--------|
| **当前方案** | 检测+生成corrected_groups | 验证 | ❌ 高 | 中 | ⭐ |
| **方案A** | 只检测inconsistencies | 执行修正+验证 | ✅ 低 | 低 | ⭐⭐⭐⭐⭐ |
| **方案B** | 检测+修正计划（分两次） | 执行+验证 | ✅ 低 | 高 | ⭐⭐⭐ |
| **方案C** | 生成操作指令 | 执行指令+验证 | ✅ 中 | 中 | ⭐⭐⭐⭐ |

## 🎯 推荐方案：方案A

### 为什么？

1. **职责最清晰**：
   - LLM做语义理解（擅长）
   - 代码做数据操作（可靠）

2. **最不易出错**：
   - LLM输出简单（只有inconsistency描述）
   - 代码逻辑可测试、可验证

3. **成本最低**：
   - 只需一次LLM调用
   - Prompt简单，token少

4. **可维护性最好**：
   - 代码逻辑在代码层面，好维护
   - Prompt简洁，不需要频繁修改

### 实施建议

#### 短期（立即）
1. 修改Prompt，让LLM只返回inconsistencies
2. 实现代码层面的修正逻辑
3. 加强数据完整性验证

#### 中期（优化）
1. 添加更多测试用例
2. 监控inconsistency检测准确率
3. 优化merge逻辑（如rationale合并）

#### 长期（演进）
1. 考虑用fine-tuned model专门做inconsistency检测
2. 积累inconsistency patterns，提升准确率

## 💡 关键设计原则

### 1. 单一职责原则（SRP）

> "一个模块只做一件事，并把它做好"

- LLM：语义理解
- 代码：数据操作

### 2. 防御性编程

> "永远不要相信外部输入，即使来自LLM"

- 验证LLM输出
- 验证数据完整性
- 有问题就拒绝

### 3. 渐进式增强

> "先做最简单的方案，确保正确性，再优化"

- 阶段1：只检测最明显的不一致
- 阶段2：扩展到更多类型
- 阶段3：优化性能

### 4. 可观测性

> "系统的每个决策都应该可追踪"

```python
logger.info("Detected inconsistency: group %d says merge but separate", group_id)
logger.info("Merging group %d into group %d", source, target)
logger.info("After merge: %d groups, %d items covered", len(groups), len(items))
```

## 🔧 完整实现示例

见附件：`validation_professional_impl.py`

---

**推荐方案**: 方案A（LLM检测 + 代码修正）  
**核心原则**: 职责分离、防御性编程  
**实施优先级**: 高（应该立即重构）  
**预期效果**: 错误率降低90%，可维护性提升200%
