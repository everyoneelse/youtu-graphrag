# Prompt管理设计说明

**日期**: 2025-10-27  
**主题**: 为什么Head去重的Prompt只在配置文件中，没有代码fallback

---

## 🎯 设计决策

Head节点去重的prompt **只存储在配置文件**中，代码**不包含fallback**。

### 位置

**唯一位置**: `config/base_config.yaml` → `prompts.head_dedup.general`

```yaml
prompts:
  head_dedup:
    general: |-
      You are an expert in knowledge graph entity resolution.
      
      TASK: Determine if the following two entities refer to the SAME real-world object.
      
      Entity 1: {entity_1}
      Related knowledge about Entity 1:
      {context_1}
      
      Entity 2: {entity_2}
      Related knowledge about Entity 2:
      {context_2}
      
      # ... 完整规则
```

### 代码实现

```python
def _build_head_dedup_prompt(self, node_id_1: str, node_id_2: str) -> str:
    """Build LLM prompt for head deduplication.
    
    Loads prompt from config file (prompts.head_dedup.general).
    If prompt is missing or malformed, raises an error.
    """
    # ... 准备变量 ...
    
    # Load prompt from config (no fallback)
    try:
        prompt_template = self.config.get_prompt_formatted(
            "head_dedup", "general",
            entity_1=desc_1, context_1=context_1,
            entity_2=desc_2, context_2=context_2
        )
        return prompt_template
    except Exception as e:
        # 直接报错，不使用fallback
        error_msg = (
            f"Failed to load head_dedup prompt from config: {e}\n"
            f"Please ensure 'prompts.head_dedup.general' is defined in your config file.\n"
            f"See HEAD_DEDUP_PROMPT_CUSTOMIZATION.md for details."
        )
        logger.error(error_msg)
        raise ValueError(error_msg)
```

---

## ✅ 为什么这样设计？

### 1. 单一数据源原则 (Single Source of Truth)

**问题**: 如果同时在配置文件和代码中保存prompt
```
❌ 配置文件: prompts.head_dedup.general
❌ 代码fallback: _get_default_head_dedup_prompt()
```

**后果**:
- 🔴 维护两份prompt
- 🔴 容易不一致：改了配置忘改代码
- 🔴 不知道实际使用的是哪个

**解决**: 只在配置文件中保存
```
✅ 配置文件: prompts.head_dedup.general  ← 唯一来源
✅ 代码: 仅从配置读取，失败则报错
```

### 2. 明确错误，快速反馈 (Fail Fast)

**如果有fallback**:
```python
try:
    prompt = load_from_config()
except:
    prompt = default_prompt()  # 静默使用fallback
    # ❌ 用户不知道配置有问题
    # ❌ 可能使用了旧版本的prompt
    # ❌ 排查困难
```

**不用fallback**:
```python
try:
    prompt = load_from_config()
except Exception as e:
    raise ValueError(f"Config error: {e}")  # 立即报错
    # ✅ 用户立即知道问题
    # ✅ 必须修复配置才能继续
    # ✅ 避免静默失败
```

### 3. 强制最佳实践 (Enforce Best Practice)

**有fallback的情况**:
```
用户A: 不知道有配置文件，一直用fallback
用户B: 修改了配置文件
用户C: 修改了代码里的fallback

结果: 三个环境使用不同的prompt
```

**无fallback的情况**:
```
所有用户: 必须使用配置文件
结果: 所有环境的prompt管理方式统一
```

### 4. 与现有架构一致

查看现有的tail去重prompt管理：

```python
# 现有的semantic_dedup也是从配置读取
def _build_semantic_dedup_prompt(self, ...):
    # 从config读取，没有硬编码fallback
    prompt = self.config.get_prompt_formatted("semantic_dedup", "general", ...)
    return prompt
```

**Head去重遵循同样的模式**:
```python
# 新的head_dedup也从配置读取，保持一致
def _build_head_dedup_prompt(self, ...):
    # 从config读取，没有硬编码fallback
    prompt = self.config.get_prompt_formatted("head_dedup", "general", ...)
    return prompt
```

---

## 🔍 对比分析

### 方案A: 有Fallback（已弃用）

```python
def _build_head_dedup_prompt(self, ...):
    try:
        return self.config.get_prompt_formatted(...)
    except:
        return self._get_default_head_dedup_prompt(...)  # 50行硬编码

def _get_default_head_dedup_prompt(self, ...):
    return f"""You are an expert...
    # 50行硬编码的prompt
    """
```

**优点**:
- ✓ 即使配置文件损坏也能工作

**缺点**:
- ✗ 维护两份prompt（配置+代码）
- ✗ 不知道实际使用哪个
- ✗ 配置错误时静默失败
- ✗ 用户可能一直用fallback而不自知
- ✗ 代码多50行
- ✗ 与现有tail去重方式不一致

### 方案B: 无Fallback（当前）✅

```python
def _build_head_dedup_prompt(self, ...):
    try:
        return self.config.get_prompt_formatted(...)
    except Exception as e:
        raise ValueError(f"Config missing: {e}")  # 明确报错
```

**优点**:
- ✓ 只维护一份prompt（配置文件）
- ✓ 配置错误立即发现
- ✓ 强制使用配置文件
- ✓ 代码更简洁（少50行）
- ✓ 与现有tail去重方式一致
- ✓ 符合单一数据源原则

**缺点**:
- ✗ 必须确保配置文件正确

**应对措施**:
- ✓ 集成测试检查配置
- ✓ 清晰的错误提示
- ✓ 详细的文档说明

---

## 📝 用户体验

### 配置正确时

```python
# 一切正常
stats = builder.deduplicate_heads()
# ✓ 使用配置文件中的prompt
```

### 配置缺失时

**有fallback（不好）**:
```python
stats = builder.deduplicate_heads()
# ⚠ 静默使用fallback
# ⚠ 用户不知道配置有问题
# ⚠ 可能使用旧版prompt
```

**无fallback（好）**✅:
```python
stats = builder.deduplicate_heads()
# ❌ ValueError: Failed to load head_dedup prompt from config
#    Please ensure 'prompts.head_dedup.general' is defined in your config file.
#    See HEAD_DEDUP_PROMPT_CUSTOMIZATION.md for details.

# ✓ 用户立即知道问题
# ✓ 得到明确的修复指引
# ✓ 不会默默使用错误的prompt
```

---

## 🎨 实际案例

### 场景1: 用户想调整prompt

**有fallback**:
```bash
# 用户修改配置文件
vim config/base_config.yaml
# 修改 prompts.head_dedup.general

# 运行
python main.py
# 结果: 可能用配置，也可能用fallback
# 不确定是否生效
```

**无fallback**✅:
```bash
# 用户修改配置文件
vim config/base_config.yaml
# 修改 prompts.head_dedup.general

# 运行
python main.py
# 结果: 一定使用配置文件的prompt
# 如果配置错误，立即报错
```

### 场景2: 多环境部署

**有fallback**:
```
开发环境: 修改了配置文件 → 使用配置
测试环境: 忘记同步配置 → 使用fallback
生产环境: 配置文件损坏 → 使用fallback

结果: 三个环境的prompt不一致！
```

**无fallback**✅:
```
开发环境: 修改了配置文件 → 使用配置
测试环境: 忘记同步配置 → 报错，强制修复
生产环境: 配置文件损坏 → 报错，立即发现

结果: 所有环境的prompt一致！
```

### 场景3: 团队协作

**有fallback**:
```
成员A: 修改配置文件，提交PR
成员B: 审查配置，批准
成员C: 部署到服务器，但配置没生效（用了fallback）
→ 7天后才发现使用的是旧prompt
```

**无fallback**✅:
```
成员A: 修改配置文件，提交PR
成员B: 审查配置，批准
成员C: 部署到服务器
  - 配置正确 → 成功运行
  - 配置错误 → 立即报错，立即修复
→ 不会静默使用错误配置
```

---

## 🛡️ 保障措施

虽然没有fallback，但有完善的保障：

### 1. 集成测试

```python
# test_head_dedup_integration.py
def test_prompt_loading():
    """Test that head_dedup prompt can be loaded."""
    config = get_config()
    
    # 尝试加载prompt
    prompt = config.get_prompt_formatted(
        "head_dedup", "general",
        entity_1="Test", context_1="Test",
        entity_2="Test", context_2="Test"
    )
    
    assert "Test" in prompt
    assert len(prompt) > 100
```

### 2. 清晰的错误提示

```python
ValueError: Failed to load head_dedup prompt from config: 'head_dedup'
Please ensure 'prompts.head_dedup.general' is defined in your config file.
See HEAD_DEDUP_PROMPT_CUSTOMIZATION.md for details.
```

### 3. 详细的文档

- `HEAD_DEDUP_PROMPT_CUSTOMIZATION.md` - Prompt自定义指南
- `HEAD_DEDUP_README.md` - 快速使用
- `config/base_config.yaml` - 包含完整的prompt模板

### 4. 示例配置

配置文件已包含完整的prompt模板，用户只需：
```bash
cp config/base_config.yaml config/my_config.yaml
# 直接使用，或根据需要修改
```

---

## 📊 业界最佳实践

### 配置管理原则

大多数成熟项目都遵循：

**好的做法** ✅:
- Django: 所有配置在 `settings.py`，没有硬编码fallback
- Kubernetes: 所有配置在YAML，配置错误直接报错
- Terraform: 所有基础设施配置在文件，不支持fallback

**不好的做法** ❌:
- 配置和代码都有默认值
- 配置失败时静默使用代码默认值
- 不知道实际使用哪个配置

### 我们的选择

Head去重遵循业界最佳实践：
- ✅ 配置即代码 (Configuration as Code)
- ✅ 明确失败 (Fail Fast)
- ✅ 单一数据源 (Single Source of Truth)

---

## 🎯 总结

| 维度 | 有Fallback | 无Fallback（当前）|
|------|-----------|------------------|
| 维护性 | ❌ 两处维护 | ✅ 一处维护 |
| 一致性 | ❌ 可能不一致 | ✅ 强制一致 |
| 可调试性 | ❌ 不知道用哪个 | ✅ 只有一个来源 |
| 错误反馈 | ❌ 静默失败 | ✅ 立即报错 |
| 代码复杂度 | ❌ 多50行 | ✅ 更简洁 |
| 架构一致性 | ❌ 与tail不同 | ✅ 与tail一致 |
| 用户体验 | ❌ 不知道问题 | ✅ 明确提示 |
| 最佳实践 | ❌ 违背原则 | ✅ 符合原则 |

**结论**: 无fallback方案在所有维度都更优 ✅

---

## 💡 如何使用

### 正常使用

```python
# 1. 确保配置文件包含prompt
# config/base_config.yaml 已包含完整prompt模板

# 2. 直接使用
from models.constructor.kt_gen import KnowledgeTreeGen
builder = KnowledgeTreeGen(...)
stats = builder.deduplicate_heads()  # 自动使用配置文件的prompt
```

### 自定义prompt

```bash
# 编辑配置文件
vim config/base_config.yaml

# 修改 prompts.head_dedup.general
# 添加你的规则、示例等

# 重启程序即可生效
```

### 错误处理

如果看到错误：
```
ValueError: Failed to load head_dedup prompt from config
```

解决方法：
1. 检查 `config/base_config.yaml` 是否存在
2. 检查 `prompts.head_dedup.general` 是否定义
3. 检查YAML格式是否正确
4. 参考 `HEAD_DEDUP_PROMPT_CUSTOMIZATION.md`

---

**设计原则**: Configuration as Code, Fail Fast, Single Source of Truth  
**实现方式**: 仅从配置文件读取，失败立即报错  
**用户利益**: 配置统一、错误明确、维护简单

---

**版本**: v1.1  
**日期**: 2025-10-27  
**状态**: ✅ 最终版本
