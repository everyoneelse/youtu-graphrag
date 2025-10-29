# Head Dedup Prompt Update Summary

**Date**: 2025-10-29  
**Task**: 参考semantic_dedup的prompt风格改进head_dedup的prompt

## 📋 修改内容

### 修改文件
- `config/base_config.yaml` - 修改了 `prompts.head_dedup.general` 部分

### 主要改进

#### 1. 开头部分更清晰
**之前**:
```
You are an expert in knowledge graph entity resolution.
TASK: Determine if the following two entities refer to the SAME real-world object.
```

**之后**:
```
You are an expert in knowledge graph entity deduplication.
TASK: Determine if the following two entities are COREFERENT (refer to the exact same real-world object).
```

#### 2. Context说明更明确
**之前**:
```
Related knowledge about Entity 1:
{context_1}
```

**之后**:
```
Related knowledge about Entity 1 (graph relations and source text):
{context_1}
```

说明：明确指出context包含图关系和源文本（当use_hybrid_context=true时）

#### 3. CRITICAL RULES结构改进
参考semantic_dedup的风格，将规则表述更加统一：

- **Rule 1 - REFERENTIAL IDENTITY**: 
  - 使用 `MERGE` / `DO NOT MERGE` 统一标识
  - 添加更清晰的例子

- **Rule 2 - SUBSTITUTION TEST**:
  - 使用统一的 `DO NOT MERGE` / `MERGE` 格式
  
- **Rule 3 - TYPE CONSISTENCY**:
  - 强调"carefully verify with all available context"
  
- **Rule 4 - CONSERVATIVE PRINCIPLE**:
  - 使用 `DO NOT MERGE` 统一格式
  - 强调"When in doubt, keep entities separate"

#### 4. 新增 CRITICAL DISTINCTION 部分
```
CRITICAL DISTINCTION - Related vs Coreferent:
⚠️  Entities can have similar relations or contexts but still be DIFFERENT entities.
Example: 'Apple Inc.' and 'Apple Store' are related (ownership) but DIFFERENT entities.
Only merge if they are the SAME entity with different names/expressions.
```

参考semantic_dedup的"Relation Satisfaction vs Entity Identity"部分

#### 5. PROHIBITED MERGE REASONS 改进
- 添加了新的禁止原因: `✗ Hierarchical relationship: One contains/owns the other → different entities`
- 所有示例改用单引号，保持风格一致

#### 6. DECISION PROCEDURE 改进
新增步骤：
- Step 3: "Compare their source text contexts - do they describe the SAME entity?"
- 明确说明需要同时检查图关系和源文本

#### 7. OUTPUT FORMAT 改进
```
"rationale": "Clear explanation based on referential identity and context analysis"
```
强调要基于referential identity **和** context analysis

## ✅ 验证结果

测试通过：
```
✓ Head dedup prompt formatting successful
✓ Formatted prompt length: 3716 characters
✓ All required sections present
```

## 🔍 与semantic_dedup的对比

### 共同点（已对齐）
1. ✅ 开头都是 "You are an expert in knowledge graph entity deduplication"
2. ✅ 都有明确的 TASK 说明
3. ✅ 都有 CRITICAL RULES 分级结构
4. ✅ 都有 CRITICAL DISTINCTION 部分
5. ✅ 都有 PROHIBITED MERGE REASONS
6. ✅ 都有 DECISION PROCEDURE
7. ✅ 都强调 CONSERVATIVE PRINCIPLE

### 差异点（合理的）
1. semantic_dedup: 多对多判断 (一对relation的多个tail)
2. head_dedup: 两两判断 (两个独立的entity)
3. semantic_dedup: 只使用chunk contexts
4. head_dedup: 使用图关系 + chunk contexts (hybrid模式)

## 📝 Context类型说明

### head_dedup的context
根据 `use_hybrid_context` 配置：
- **false** (默认): 只包含图关系
  - 通过 `_collect_node_context()` 收集出边和入边
- **true**: 同时包含图关系和源文本
  - 图关系: `_collect_node_context()`  
  - 源文本: `_collect_chunk_context()`
  
### semantic_dedup的context
- 只使用chunk文本contexts
- 通过 `_summarize_contexts()` 提供

## 🎯 设计原则

参考semantic_dedup的成功设计：
1. **清晰的结构化**: CRITICAL RULES → DISTINCTION → PROHIBITED → PROCEDURE
2. **统一的术语**: MERGE / DO NOT MERGE 贯穿全文
3. **具体的例子**: 每个规则都有清晰的例子
4. **保守原则**: When in doubt → 明确指示
5. **完整的决策流程**: 从名称检查到最终判断

---

**修改完成时间**: 2025-10-29  
**状态**: ✅ 已测试通过
