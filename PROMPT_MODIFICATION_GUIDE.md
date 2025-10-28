# Head去重Prompt修改指南

## 📍 Prompt位置

**文件**: `/workspace/config/base_config.yaml`  
**当前prompt**: 第339-410行

```yaml
prompts:
  head_dedup:
    general: |-
      # 这是当前的prompt（只判断是否等价）
```

---

## 🔧 修改方法

### 方法1：添加新的Prompt模板（推荐）⭐

**在第410行后添加**：

```yaml
prompts:
  head_dedup:
    # 保留原有的prompt（向后兼容）
    general: |-
      You are an expert in knowledge graph entity resolution.
      TASK: Determine if the following two entities refer to the SAME real-world object.
      ...
      OUTPUT FORMAT (strict JSON):
      {
        "is_coreferent": true/false,
        "confidence": 0.0-1.0,
        "rationale": "..."
      }
    
    # 新增：带representative选择的prompt
    with_representative_selection: |-
      You are an expert in knowledge graph entity resolution.

      TASK: Determine if the following two entities refer to the SAME real-world object, and if so, which one should be the PRIMARY REPRESENTATIVE.

      Entity 1 (ID: {entity_1_id}): {entity_1_desc}
      Related knowledge about Entity 1:
      {context_1}

      Entity 2 (ID: {entity_2_id}): {entity_2_desc}
      Related knowledge about Entity 2:
      {context_2}

      CRITICAL RULES:

      1. REFERENTIAL IDENTITY: Do they refer to the exact same object/person/concept?
         - Same entity with different names → YES (e.g., "NYC" = "New York City")
         - Different but related entities → NO (e.g., "Apple Inc." ≠ "Apple Store")

      2. SUBSTITUTION TEST: Can you replace one with the other in all contexts?

      3. PRIMARY REPRESENTATIVE SELECTION (if they are coreferent):
         Choose the entity that should serve as the main reference based on:
         
         a) **Formality and Completeness**:
            - Full name > Abbreviation (e.g., "World Health Organization" > "WHO")
            - BUT: In technical domains, common abbreviations may be preferred (e.g., "AI")
         
         b) **Domain Convention**:
            - Medical domain: Prefer standard medical terminology
            - Popular context: Prefer commonly used form
            - Academic context: Prefer formal academic names
         
         c) **Language and Cultural Context**:
            - Consider the primary language of the knowledge graph
            - For international entities, prefer widely recognized forms
         
         d) **Information Richness** (visible in the graph):
            - Entity with MORE relationships (higher connectivity) is usually better
            - Entity with MORE context/evidence is usually better
         
         e) **Naming Quality**:
            - Official name > Colloquial name
            - Standard spelling > Variant spelling
            - Complete form > Partial form

      4. CONSERVATIVE PRINCIPLE:
         - When uncertain about coreference → answer NO
         - When uncertain about representative → choose the one with MORE relationships
         - False merge is worse than false split

      OUTPUT FORMAT (strict JSON):
      {{
        "is_coreferent": true/false,
        "preferred_representative": "{entity_1_id}" or "{entity_2_id}" or null,
        "rationale": "Explain: (1) WHY they are the same/different, (2) If same, WHY you chose this representative based on the criteria above"
      }}

      IMPORTANT NOTES:
      - Set "preferred_representative" ONLY if "is_coreferent" is true
      - If "is_coreferent" is false, set "preferred_representative" to null
      - The "preferred_representative" must be exactly one of: "{entity_1_id}" or "{entity_2_id}"
      - Provide clear reasoning for your representative choice
      
      EXAMPLES:
      
      Example 1 - Technical Abbreviation:
      Entity 1 (entity_100): "AI", relations: [applies_to→Machine Learning, used_in→ChatGPT, ...]
      Entity 2 (entity_150): "Artificial Intelligence", relations: [subfield_of→Computer Science]
      → is_coreferent: true
      → preferred_representative: "entity_100"
      → Rationale: "Both refer to the same concept. 'AI' is the standard term in technical contexts with significantly more graph connections (5 vs 1), making it the better representative despite being an abbreviation."
      
      Example 2 - Formal Name Preferred:
      Entity 1 (entity_200): "北京", relations: [population→21M]
      Entity 2 (entity_250): "北京市", relations: [capital_of→中国, area→16410km², founded→...]
      → is_coreferent: true
      → preferred_representative: "entity_250"
      → Rationale: "Both refer to Beijing. '北京市' is the official administrative name with more comprehensive graph connections (3 vs 1), making it the proper representative."
      
      Example 3 - Context Matters:
      Entity 1 (entity_300): "WHO", relations: [established→1948, member_countries→194, headquarters→Geneva, ...]
      Entity 2 (entity_350): "World Health Organization", relations: [type→UN Agency]
      → is_coreferent: true
      → preferred_representative: "entity_300"
      → Rationale: "Both refer to the same organization. Although 'World Health Organization' is the full name, 'WHO' is the widely recognized standard abbreviation in medical and public health contexts, with significantly more relationships (4 vs 1)."
```

---

## 💻 修改步骤（实际操作）

### 步骤1: 备份原文件

```bash
cd /workspace
cp config/base_config.yaml config/base_config.yaml.backup
```

### 步骤2: 编辑文件

```bash
# 使用vim或其他编辑器
vim config/base_config.yaml

# 或者使用sed直接插入
```

### 步骤3: 在第410行后添加新prompt

**找到这一行**（第410行附近）：
```yaml
      → Rationale: Same name but different age and occupation suggest different persons (conservative principle applied)

  decomposition:
    general: "You are a professional..."
```

**在 `decomposition:` 之前插入**：
```yaml
    # 新增：带representative选择的prompt
    with_representative_selection: |-
      You are an expert in knowledge graph entity resolution.
      
      TASK: Determine if the following two entities refer to the SAME real-world object, and if so, which one should be the PRIMARY REPRESENTATIVE.
      
      ... (完整的新prompt内容)
```

---

## 🔍 验证修改

### 验证1: 检查语法

```bash
cd /workspace
python -c "
from config import get_config
config = get_config()
print('✓ Config loads successfully')

# 检查新prompt是否存在
try:
    prompt = config.get_prompt_formatted(
        'head_dedup',
        'with_representative_selection',
        entity_1_id='test1',
        entity_1_desc='Test Entity 1',
        context_1='Context 1',
        entity_2_id='test2',
        entity_2_desc='Test Entity 2',
        context_2='Context 2'
    )
    print('✓ New prompt template loaded successfully')
    print(f'Prompt length: {len(prompt)} characters')
except Exception as e:
    print(f'✗ Error loading prompt: {e}')
"
```

### 验证2: 测试使用

```python
from models.constructor.kt_gen import KnowledgeTreeGen
from config import get_config

config = get_config()
builder = KnowledgeTreeGen('test', config)

# 测试prompt加载
prompt = builder._build_head_dedup_prompt_v2('entity_1', 'entity_2')
print(f"Prompt loaded, length: {len(prompt)}")
```

---

## 📋 完整的修改内容

我已经为你准备了完整的新prompt内容，你可以：

### 选项1: 直接复制（最简单）

从 `/workspace/config_llm_driven_representative_example.yaml` 复制：

```bash
# 查看完整的新prompt
cat /workspace/config_llm_driven_representative_example.yaml

# 提取prompt部分
sed -n '/with_representative_selection:/,/^[^ ]/p' /workspace/config_llm_driven_representative_example.yaml
```

### 选项2: 使用准备好的完整文件

```bash
# 备份原配置
cp config/base_config.yaml config/base_config.yaml.backup

# 手动编辑，参考示例配置
# vim config/base_config.yaml
# 参考：/workspace/config_llm_driven_representative_example.yaml
```

---

## 🎯 关键改动点

### 原Prompt（只判断等价）

```yaml
OUTPUT FORMAT:
{
  "is_coreferent": true/false,
  "confidence": 0.0-1.0,
  "rationale": "..."
}
```

### 新Prompt（判断等价 + 选择representative）

```yaml
OUTPUT FORMAT:
{
  "is_coreferent": true/false,
  "preferred_representative": "entity_XXX" or null,  # ← 新增
  "rationale": "Explain both decisions"  # ← 更详细
}
```

**关键增加**：
1. 明确要求选择primary representative
2. 提供5个选择标准（formality, domain, richness, quality, context）
3. 输出包含 `preferred_representative` 字段
4. Rationale需要解释选择理由

---

## 🔄 代码适配

修改prompt后，确保代码能正确使用：

### 在 kt_gen.py 中

**当前**：
```python
def _build_head_dedup_prompt(self, node_id_1, node_id_2):
    # 使用 "general" prompt
    prompt = self.config.get_prompt_formatted(
        "head_dedup", 
        "general",  # ← 旧版本
        entity_1=desc_1,
        context_1=context_1,
        entity_2=desc_2,
        context_2=context_2
    )
```

**改进**：
```python
def _build_head_dedup_prompt_v2(self, node_id_1, node_id_2):
    # 使用 "with_representative_selection" prompt
    prompt = self.config.get_prompt_formatted(
        "head_dedup", 
        "with_representative_selection",  # ← 新版本
        entity_1_id=node_id_1,  # ← 新增ID参数
        entity_1_desc=desc_1,
        context_1=context_1,
        entity_2_id=node_id_2,  # ← 新增ID参数
        entity_2_desc=desc_2,
        context_2=context_2
    )
```

---

## ⚠️ 注意事项

1. **保留原有prompt**: 不要删除 `general`，用于向后兼容
2. **缩进对齐**: YAML对缩进敏感，确保对齐
3. **变量名称**: 新prompt需要 `{entity_1_id}` 和 `{entity_2_id}` 参数
4. **测试验证**: 修改后运行测试确保没有语法错误

---

## 📞 快速帮助

**如果不想手动编辑**，我可以直接帮你生成修改后的完整配置文件！

**需要我帮你**：
1. 生成完整的修改后的 `base_config.yaml`？
2. 还是给你一个可以直接运行的修改脚本？

告诉我你更喜欢哪种方式！
