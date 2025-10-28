# Head节点去重 - 文件索引

**作用**: 快速找到所有相关文件  
**日期**: 2025-10-27

---

## 📂 文件分类

### 🔧 核心代码和配置（必读）

| 文件 | 行数/大小 | 作用 | 优先级 |
|------|----------|------|--------|
| `config/base_config.yaml` | +70行 | 配置参数 + Prompt模板（唯一来源）| ⭐⭐⭐⭐⭐ |
| `models/constructor/kt_gen.py` | +440行 | 核心实现（14个方法） | ⭐⭐⭐⭐⭐ |

### 📖 使用文档

| 文件 | 页数 | 内容 | 适合人群 |
|------|------|------|----------|
| `HEAD_DEDUP_README.md` ⭐ | 5页 | 总览+快速使用 | 所有人 |
| `HEAD_DEDUP_QUICKSTART.md` | 8页 | 5分钟快速开始 | 新手 |
| `HEAD_DEDUP_INTEGRATION_SUMMARY.md` | 12页 | 完整集成说明 | 开发者 |
| `HEAD_DEDUP_PROMPT_CUSTOMIZATION.md` | 10页 | Prompt自定义指南 | 高级用户 |

### 📚 设计文档

| 文件 | 页数 | 内容 | 适合人群 |
|------|------|------|----------|
| `HEAD_DEDUPLICATION_SOLUTION.md` | 30页 | 完整方案设计 | 架构师 |
| `HEAD_DEDUP_LLM_CORE_LOGIC.md` | 20页 | LLM判断逻辑详解 | 算法工程师 |
| `PROMPT_COMPARISON_HEAD_VS_TAIL_DEDUP.md` | 25页 | 与tail去重对比 | 研究人员 |
| `PROFESSIONAL_EVALUATION_PROMPTS.md` | 20页 | 专业度客观评估 | 技术Leader |
| `PROMPT_IN_CONFIG_ONLY.md` ⭐ | 15页 | 为何Prompt只在配置文件 | 所有人 |

### 💻 代码示例

| 文件 | 行数 | 内容 | 适合人群 |
|------|------|------|----------|
| `example_use_head_dedup.py` | 300行 | 7个实际使用场景 | 开发者 |
| `head_deduplication_reference.py` | 600行 | 完整参考实现 | 学习者 |
| `example_head_deduplication.py` | 400行 | 8个理论示例 | 学习者 |

### 🧪 测试文件

| 文件 | 行数 | 内容 | 适合人群 |
|------|------|------|----------|
| `test_head_dedup_integration.py` | 250行 | 集成测试脚本 | QA工程师 |

### 📝 总结文档

| 文件 | 作用 |
|------|------|
| `FINAL_HEAD_DEDUP_SUMMARY.md` | 最终完成总结 |
| `HEAD_DEDUP_FILE_INDEX.md` | 本文档（文件索引） |

---

## 🗂️ 按用途分类

### 1️⃣ 我想快速使用功能

**必读**:
1. `HEAD_DEDUP_README.md` - 总览
2. `HEAD_DEDUP_INTEGRATION_SUMMARY.md` - 使用说明
3. `example_use_head_dedup.py` - 代码示例

**配置**:
- 编辑 `config/base_config.yaml`
- 设置 `head_dedup.enabled: true`

### 2️⃣ 我想自定义Prompt

**必读**:
1. `HEAD_DEDUP_PROMPT_CUSTOMIZATION.md` - 详细指南
2. `config/base_config.yaml` - 编辑prompt模板

**位置**:
- 配置文件中的 `prompts.head_dedup.general`

### 3️⃣ 我想理解设计原理

**必读**:
1. `HEAD_DEDUPLICATION_SOLUTION.md` - 完整设计
2. `HEAD_DEDUP_LLM_CORE_LOGIC.md` - LLM逻辑
3. `PROMPT_COMPARISON_HEAD_VS_TAIL_DEDUP.md` - 对比分析

### 4️⃣ 我想评估方案质量

**必读**:
1. `PROFESSIONAL_EVALUATION_PROMPTS.md` - 专业评估
2. `PROMPT_COMPARISON_HEAD_VS_TAIL_DEDUP.md` - 对比
3. `HEAD_DEDUP_LLM_CORE_LOGIC.md` - 技术细节

### 5️⃣ 我想学习代码实现

**必读**:
1. `models/constructor/kt_gen.py` (第4471-5218行)
2. `head_deduplication_reference.py` - 参考实现
3. `example_use_head_dedup.py` - 实际示例

### 6️⃣ 我想测试功能

**必读**:
1. `test_head_dedup_integration.py` - 运行测试
2. `example_use_head_dedup.py` - 手动测试

---

## 📊 文件统计

### 代码文件
- **修改**: 2个文件（kt_gen.py, base_config.yaml）
- **新增**: 4个文件（3个示例 + 1个测试）
- **总计**: +约1800行代码（移除fallback后更精简）

### 文档文件
- **设计文档**: 5个（~110页，含PROMPT_IN_CONFIG_ONLY.md）
- **使用文档**: 4个（~35页）
- **总结文档**: 2个（~10页）
- **示例说明**: 2个（~15页）
- **总计**: 13个文档（~170页）

### 完整列表（按字母顺序）

```
HEAD节点去重相关文件：

配置和代码:
  config/base_config.yaml                           [修改] 配置+Prompt
  models/constructor/kt_gen.py                      [修改] 核心实现

文档:
  FINAL_HEAD_DEDUP_SUMMARY.md                       [新建] 完成总结
  HEAD_DEDUP_FILE_INDEX.md                          [新建] 本文档
  HEAD_DEDUP_INTEGRATION_SUMMARY.md                 [新建] 集成说明 ⭐
  HEAD_DEDUP_LLM_CORE_LOGIC.md                      [新建] LLM逻辑
  HEAD_DEDUP_PROMPT_CUSTOMIZATION.md                [新建] Prompt自定义
  HEAD_DEDUP_QUICKSTART.md                          [新建] 快速开始
  HEAD_DEDUP_README.md                              [新建] 主README
  HEAD_DEDUPLICATION_SOLUTION.md                    [新建] 方案设计
  PROFESSIONAL_EVALUATION_PROMPTS.md                [新建] 专业评估
  PROMPT_COMPARISON_HEAD_VS_TAIL_DEDUP.md          [新建] Prompt对比
  PROMPT_IN_CONFIG_ONLY.md                          [新建] Prompt设计说明 ⭐

代码示例:
  example_head_deduplication.py                     [新建] 8个示例
  example_use_head_dedup.py                         [新建] 7个实际场景
  head_deduplication_reference.py                   [新建] 完整实现
  test_head_dedup_integration.py                    [新建] 集成测试
```

---

## 🎯 推荐阅读路径

### 路径1: 快速使用者（30分钟）

```
1. HEAD_DEDUP_README.md (5分钟)
   ↓ 了解功能和快速开始
   
2. HEAD_DEDUP_INTEGRATION_SUMMARY.md (15分钟)
   ↓ 学习详细使用方法
   
3. example_use_head_dedup.py (10分钟)
   ↓ 运行实际示例
   
→ 开始使用！
```

### 路径2: 深度学习者（2小时）

```
1. HEAD_DEDUP_QUICKSTART.md (5分钟)
   ↓ 快速了解
   
2. HEAD_DEDUPLICATION_SOLUTION.md (40分钟)
   ↓ 理解设计原理
   
3. HEAD_DEDUP_LLM_CORE_LOGIC.md (30分钟)
   ↓ 掌握LLM逻辑
   
4. PROMPT_COMPARISON_HEAD_VS_TAIL_DEDUP.md (25分钟)
   ↓ 对比现有实现
   
5. models/constructor/kt_gen.py (20分钟)
   ↓ 阅读源码
   
→ 完全掌握！
```

### 路径3: 技术评审者（1小时）

```
1. PROFESSIONAL_EVALUATION_PROMPTS.md (30分钟)
   ↓ 了解专业评估
   
2. PROMPT_COMPARISON_HEAD_VS_TAIL_DEDUP.md (20分钟)
   ↓ 对比现有方案
   
3. HEAD_DEDUPLICATION_SOLUTION.md (10分钟，快速浏览)
   ↓ 验证技术方案
   
→ 做出评审决策！
```

---

## 🔍 快速查找

### 我想找...

**配置参数**: 
- `config/base_config.yaml` → `construction.semantic_dedup.head_dedup`

**Prompt模板**: 
- `config/base_config.yaml` → `prompts.head_dedup.general`

**核心代码**: 
- `models/constructor/kt_gen.py` → 第4471-5218行

**使用示例**: 
- `example_use_head_dedup.py` → 7个场景

**如何启用**: 
- `HEAD_DEDUP_README.md` → 快速使用章节

**如何自定义Prompt**: 
- `HEAD_DEDUP_PROMPT_CUSTOMIZATION.md` - 详细指南
- `PROMPT_IN_CONFIG_ONLY.md` - 设计原理

**为什么这样设计**: 
- `HEAD_DEDUPLICATION_SOLUTION.md` → 方案设计原则

**与tail去重的区别**: 
- `PROMPT_COMPARISON_HEAD_VS_TAIL_DEDUP.md`

**LLM如何判断**: 
- `HEAD_DEDUP_LLM_CORE_LOGIC.md` → 核心逻辑章节

**专业度评价**: 
- `PROFESSIONAL_EVALUATION_PROMPTS.md`

**遇到问题**: 
- `HEAD_DEDUP_INTEGRATION_SUMMARY.md` → 故障排除章节

**运行测试**: 
- `test_head_dedup_integration.py`

---

## 📌 关键点速查

| 关键点 | 位置 |
|--------|------|
| **启用功能** | `config/base_config.yaml` → `head_dedup.enabled: true` |
| **调整阈值** | `config/base_config.yaml` → `similarity_threshold: 0.85` |
| **修改Prompt** | `config/base_config.yaml` → `prompts.head_dedup.general` |
| **调用方法** | `builder.deduplicate_heads()` |
| **查看结果** | 返回的 `stats` 字典 |
| **导出审核** | `builder.export_head_merge_candidates_for_review()` |
| **验证完整性** | `builder.validate_graph_integrity_after_head_dedup()` |

---

**版本**: v1.0  
**最后更新**: 2025-10-27  
**状态**: ✅ 完整且最新
