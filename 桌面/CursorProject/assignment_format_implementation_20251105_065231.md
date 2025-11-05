# Assignment格式实现 - 修改总结

**修改时间**: 2025-11-05 06:52:31  
**修改类型**: 输出格式重构 + 跨batch支持  
**核心目标**: 解决rationale与members不一致问题

---

## 背景与动机

### 原有问题

**Groups格式**（修改前）：
```json
{
  "groups": [
    {"members": [1, 3, 5], "representative": 1, "rationale": "..."}
  ]
}
```

**问题表现**：
1. LLM容易忘记在members中包含所有应该合并的候选项
2. 出现rationale说"与[1]合并"，但members只有[5]的情况
3. 出现representative不在members中的错误

### 用户提议的解决方案

**Assignment格式**（修改后）：
```json
{
  "assignments": [
    {"candidate": 1, "representative": 1, "rationale": "..."},
    {"candidate": 3, "representative": 1, "rationale": "..."},
    {"candidate": 5, "representative": 1, "rationale": "..."}
  ]
}
```

**优势**：
- ✅ 符合LLM的归类思维（为每个候选项找代表）
- ✅ 避免填写members数组的复杂性
- ✅ 输出结构固定（N个候选项 = N个assignments）
- ✅ 容易验证完整性

---

## 修改内容

### 1. Prompt修改

#### 1.1 DEFAULT_SEMANTIC_DEDUP_PROMPT（第23-137行）

**修改前结构**：
```
- 强调分组思维 vs 归类思维
- 输出format: {"groups": [...]}
- 大量禁止模式和检查清单
```

**修改后结构**：
```
🚨 TASK: For each candidate, determine its REPRESENTATIVE

CORE CONCEPT:
- If candidates refer to the SAME entity → they share the same representative
- If a candidate is unique → it represents itself
- Representative = the most informative/authoritative candidate

WORKFLOW:
Step 1: Survey ALL candidates to identify equivalence groups
Step 2: For each group, choose the best candidate as representative
Step 3: Assign each candidate to its representative

Example: [1,2,3,4,5,6] → Analysis → Assignments

{previous_representatives}  ← 支持跨batch

OUTPUT REQUIREMENTS:
1. For EACH candidate, assign exactly ONE representative
2. Representatives must be chosen from the candidate list
3. Candidates referring to the SAME entity must have the SAME representative

ASSIGNMENT RULES:
✅ CORRECT: candidate 3 → representative 1 (same as [1])
❌ FORBIDDEN: Representative not in candidate list, circular assignments

Respond with:
{
  "assignments": [
    {"candidate": 1, "representative": 1, "rationale": "..."},
    {"candidate": 3, "representative": 1, "rationale": "..."}
  ]
}
```

**关键变化**：
- 任务从"创建groups"改为"为每个candidate分配representative"
- 输出从groups改为assignments
- 简化了prompt结构，更直接
- 添加{previous_representatives}占位符用于跨batch

#### 1.2 DEFAULT_ATTRIBUTE_DEDUP_PROMPT（第140-257行）

**类似修改**：
- 任务改为为每个attribute value分配representative
- 输出format改为assignments
- 添加{previous_representatives}占位符

### 2. Prompt构建修改

#### 2.1 _build_semantic_dedup_prompt（第1855-1913行）

**新增参数**：
```python
def _build_semantic_dedup_prompt(
    self,
    head_text: str,
    relation: str,
    head_context_lines: list,
    batch_entries: list,
    previous_representatives: dict = None,  # ← 新增
) -> str:
```

**新增逻辑**（第1876-1884行）：
```python
# Build previous representatives context
prev_rep_text = ""
if previous_representatives:
    prev_rep_lines = ["PREVIOUS BATCH REPRESENTATIVES (from earlier batches):"]
    for rep_idx, rep_desc in previous_representatives.items():
        prev_rep_lines.append(f"  - Representative [{rep_idx}]: {rep_desc}")
    prev_rep_lines.append("\nIf the current candidates match any previous representative, assign them to that representative.")
    prev_rep_text = "\n".join(prev_rep_lines)
```

**作用**：
- 在批次2及以后的prompt中包含批次1的代表信息
- 帮助LLM将后续候选项正确映射到之前的代表

### 3. 解析逻辑修改

#### 3.1 _llm_semantic_group（第1915-1996行）

**修改前**（groups格式）：
```python
groups_raw = parsed.get("groups")
for group in groups_raw:
    members_raw = group.get("members")
    # ... 解析members数组
```

**修改后**（assignments格式，第1940-1996行）：
```python
# Parse assignments (new format)
assignments_raw = parsed.get("assignments")

# Build representative -> members mapping
rep_to_members = {}
for assignment in assignments_raw:
    candidate = int(assignment.get("candidate")) - 1
    representative = int(assignment.get("representative")) - 1
    
    if representative not in rep_to_members:
        rep_to_members[representative] = {
            "members": [],
            "rationales": []
        }
    
    rep_to_members[representative]["members"].append(candidate)
    rationale = assignment.get("rationale")
    if rationale:
        rep_to_members[representative]["rationales"].append(f"[{candidate+1}]: {rationale}")

# Convert to groups format (for internal use)
groups = []
for rep_idx, data in rep_to_members.items():
    normalized_members = sorted(data["members"])
    combined_rationale = " | ".join(data["rationales"])
    
    groups.append({
        "representative": rep_idx,
        "members": normalized_members,
        "rationale": combined_rationale,
    })
```

**关键点**：
- 解析assignments数组
- 根据representative分组，自动重建groups结构
- 合并每个候选项的rationale为组的rationale
- 内部仍使用groups格式（向后兼容）

#### 3.2 _parse_semantic_dedup_results（第4094-4153行）

**完全相同的修改**：
- 从解析groups改为解析assignments
- 重建groups结构
- 保持与_llm_semantic_group的一致性

### 4. 跨Batch上下文传递

#### 4.1 _collect_semantic_dedup_prompts（第4000-4051行）

**新增逻辑**：
```python
for cluster_idx, cluster in enumerate(initial_clusters):
    # Track representatives from previous batches in this cluster
    previous_representatives = {}  # ← 新增
    
    batch_num = 0
    while cluster_indices:
        batch_indices = cluster_indices[:max_batch_size]
        batch_entries = [entries[i] for i in batch_indices]
        
        # Build prompt with previous representatives context
        prompt = self._build_semantic_dedup_prompt(
            head_text, relation, head_context_lines, batch_entries,
            previous_representatives=previous_representatives if batch_num > 0 else None  # ← 传递
        )
        
        prompts.append({
            'type': 'semantic',
            'prompt': prompt,
            'metadata': {
                'cluster_idx': cluster_idx,
                'batch_num': batch_num,
                'batch_indices': batch_indices,
                'previous_representatives': previous_representatives.copy(),  # ← 存储
            }
        })
        
        batch_num += 1
```

**说明**：
- 在同一cluster的不同batch之间传递representatives
- batch 0不需要previous_representatives
- batch 1及以后会收到之前batch的代表信息

**限制**：
- 当前实现是并发处理所有prompts
- previous_representatives在prompt生成时是空的
- 实际的跨batch联系依赖于LLM对相似性的理解
- 完整实现需要sequential处理（会影响性能）

---

## 输出格式对比

### 修改前（Groups格式）

**LLM输出**：
```json
{
  "groups": [
    {
      "members": [1, 3, 5],
      "representative": 1,
      "rationale": "候选项[1]、[3]、[5]都是定义A..."
    },
    {
      "members": [2, 4],
      "representative": 2,
      "rationale": "候选项[2]、[4]都是定义B..."
    }
  ]
}
```

**问题**：容易遗漏members，出现rationale与members不一致

### 修改后（Assignments格式）

**LLM输出**：
```json
{
  "assignments": [
    {"candidate": 1, "representative": 1, "rationale": "权威定义A"},
    {"candidate": 2, "representative": 2, "rationale": "权威定义B"},
    {"candidate": 3, "representative": 1, "rationale": "与[1]相同，都是定义A"},
    {"candidate": 4, "representative": 2, "rationale": "与[2]相同，都是定义B"},
    {"candidate": 5, "representative": 1, "rationale": "与[1]相同，都是定义A"}
  ]
}
```

**内部重建的Groups**：
```python
# 自动从assignments重建
groups = [
    {
        "members": [1, 3, 5],
        "representative": 1,
        "rationale": "[1]: 权威定义A | [3]: 与[1]相同... | [5]: 与[1]相同..."
    },
    {
        "members": [2, 4],
        "representative": 2,
        "rationale": "[2]: 权威定义B | [4]: 与[2]相同..."
    }
]
```

**优势**：
- ✅ LLM只需逐个处理，不需要记住填写members数组
- ✅ 自动保证一致性（同一representative = 同一group）
- ✅ rationale针对每个候选项，更清晰

---

## 向后兼容性

### 内部数据结构

**保持不变**：
- 解析后仍然转换为groups格式
- `{"members": [...], "representative": X, "rationale": "..."}`
- 后续处理逻辑（合并、去重）无需修改

### 配置文件

**无需修改**：
- `base_config.yaml`中的semantic_dedup配置保持不变
- `max_batch_size`, `max_candidates`等参数不变

### 现有代码

**兼容**：
- 所有使用groups的下游代码无需修改
- 只是改变了LLM输出格式和解析方式
- 内部表示仍然是groups

---

## 测试建议

### 1. 基本功能测试

**输入**：6个候选项，其中[1,3,5]相同，[2,4]相同，[6]独立

**期望LLM输出**：
```json
{
  "assignments": [
    {"candidate": 1, "representative": 1, "rationale": "..."},
    {"candidate": 2, "representative": 2, "rationale": "..."},
    {"candidate": 3, "representative": 1, "rationale": "..."},
    {"candidate": 4, "representative": 2, "rationale": "..."},
    {"candidate": 5, "representative": 1, "rationale": "..."},
    {"candidate": 6, "representative": 6, "rationale": "..."}
  ]
}
```

**期望解析结果**：
```python
groups = [
    {"members": [1, 3, 5], "representative": 1, "rationale": "..."},
    {"members": [2, 4], "representative": 2, "rationale": "..."},
    {"members": [6], "representative": 6, "rationale": "..."}
]
```

### 2. 一致性验证

**检查点**：
- ✅ 每个candidate恰好出现在一个assignment中
- ✅ 所有representative都在候选项列表中
- ✅ 相同representative的candidates被正确分组
- ✅ 不再出现"与[X]合并"但X不在同一组的情况

### 3. 跨Batch测试

**场景**：
- batch_size=5，输入[1,2,3,4,5,6,7,8,9,10]
- [1,6,9]应该是同一实体

**批次1**：[1,2,3,4,5]
- 应该输出：1→1, 2→2, ...

**批次2**：[6,7,8,9,10]
- 理想情况：6→6, 9→6（如果能识别相似性）
- 实际情况：可能6→6, 9→9（看不到批次1的代表）

**改进方向**：
- 需要sequential处理才能完全解决跨batch问题
- 或者在prompt中提供所有候选项的概览

---

## 已知限制

### 1. 跨Batch关联

**问题**：
- 当前是并发处理所有batch
- batch 2无法真正"看到"batch 1的结果
- previous_representatives是预留的机制，需要sequential处理才能充分利用

**解决方案**：
- 短期：依赖LLM对相似候选项的理解
- 长期：实现sequential batch processing（牺牲并发性能）

### 2. Rationale合并

**当前做法**：
```python
combined_rationale = " | ".join(rationales)
# 例如："[1]: 权威定义 | [3]: 与[1]相同 | [5]: 与[1]相同"
```

**可能问题**：
- rationale可能很长
- 重复信息（多个"与[1]相同"）

**改进方向**：
- 智能合并：提取共同点，去除重复
- 或：只保留representative的rationale

### 3. 错误恢复

**如果LLM输出格式错误**：
- 现在需要检查"assignments"字段
- 如果LLM仍输出"groups"格式会失败
- 可能需要添加fallback逻辑

---

## 性能影响

### API调用次数

**不变**：
- 仍然是每个batch一次LLM调用
- 并发处理，性能无影响

### Token消耗

**轻微增加**：
- 新prompt略长（增加了CORE CONCEPT, WORKFLOW等）
- 增加约100-200 tokens
- previous_representatives会增加token（如果有跨batch）

### 解析复杂度

**轻微增加**：
- 需要从assignments重建groups
- 增加了rep_to_members的字典操作
- 时间复杂度O(n)，影响很小

---

## 后续改进方向

### 1. Sequential Batch Processing

**目标**：真正实现跨batch的上下文传递

**实现**：
```python
for batch in batches:
    # 处理当前batch
    result = llm_call(batch, previous_reps)
    
    # 更新previous_reps供下一batch使用
    previous_reps.update(extract_representatives(result))
```

**权衡**：失去并发性能，但提高准确性

### 2. 智能Rationale合并

**目标**：生成更简洁的组rationale

**方法**：
- 使用LLM总结多个rationale
- 或：使用模板（"[1], [3], [5]都是定义A，因为..."）

### 3. Fallback机制

**目标**：兼容两种格式

**实现**：
```python
if "assignments" in parsed:
    # 新格式
    parse_assignments(parsed)
elif "groups" in parsed:
    # 旧格式（fallback）
    parse_groups(parsed)
```

---

## 总结

### 核心改进

✅ **输出格式**：从groups改为assignments
- 符合LLM的自然思维
- 避免members数组的一致性问题

✅ **Prompt重构**：更直接、更简洁
- 任务明确：为每个candidate分配representative
- 规则清晰：同一实体 = 同一representative

✅ **解析逻辑**：自动重建groups
- 从assignments自动分组
- 保证一致性（同一rep必然同一组）

✅ **跨Batch支持**：预留机制
- 添加previous_representatives参数
- 为sequential processing做好准备

### 文件修改汇总

| 文件 | 函数/变量 | 行号 | 修改内容 |
|------|----------|------|---------|
| kt_gen.py | DEFAULT_SEMANTIC_DEDUP_PROMPT | 23-137 | 重写prompt为assignment格式 |
| kt_gen.py | DEFAULT_ATTRIBUTE_DEDUP_PROMPT | 140-257 | 重写prompt为assignment格式 |
| kt_gen.py | _build_semantic_dedup_prompt | 1855-1913 | 添加previous_representatives参数 |
| kt_gen.py | _llm_semantic_group | 1940-1996 | 改为解析assignments并重建groups |
| kt_gen.py | _collect_semantic_dedup_prompts | 4013-4051 | 添加跨batch上下文准备 |
| kt_gen.py | _parse_semantic_dedup_results | 4094-4153 | 改为解析assignments并重建groups |

### 预期效果

修改后应该：
- ✅ 消除"rationale说合并但members没包含"的问题
- ✅ 消除representative不在members中的错误
- ✅ 提高LLM输出的一致性
- ✅ 为跨batch关联提供基础

---

**修改完成时间**: 2025-11-05 06:52:31  
**相关文档**: 
- `semantic_dedup_rationale_members_inconsistency_20251105_054617.md`
- `json_field_order_fix_20251105_060712.md`
- `complete_fix_grouping_vs_categorization_20251105_061626.md`
