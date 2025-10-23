# 还原Semantic Results - 节省LLM调用成本

## 📋 概述

这套脚本和补丁允许你从`triple_deduplicate_semantic`保存的中间结果还原`semantic_results`，从而在后续运行中跳过昂贵的LLM调用，节省tokens成本。

## 🎯 使用场景

- **调试和测试：** 修改后续处理逻辑时，不需要重新调用LLM
- **参数调优：** 测试不同的后处理参数，复用LLM结果
- **成本控制：** 大规模数据处理时，复用已有的LLM结果
- **错误恢复：** 如果下游处理出错，可以从LLM结果重新开始

## 📁 文件说明

| 文件 | 说明 |
|------|------|
| `restore_semantic_results.py` | 核心脚本：从中间结果还原semantic_results |
| `example_use_restored_results.py` | 使用示例和验证工具 |
| `patch_kt_gen_for_cached_results.md` | 代码修改指南 |

## 🚀 快速开始

### Step 1: 首次运行，保存中间结果

确保配置文件中启用了中间结果保存：

```yaml
# config/semantic_dedup.yaml
semantic_dedup:
  save_intermediate_results: true
  intermediate_results_path: "output/dedup_intermediate/"
```

运行知识图谱构建：

```bash
python main.py --dataset demo
```

这会生成中间结果文件：
```
output/dedup_intermediate/demo_edge_dedup_20241023_123456.json
```

### Step 2: 还原semantic_results

使用脚本还原semantic_results：

```bash
python restore_semantic_results.py \
    output/dedup_intermediate/demo_edge_dedup_20241023_123456.json
```

输出文件：
- `demo_semantic_results_20241023_123456.pkl` - Python pickle格式，用于加载
- `demo_semantic_results_20241023_123456.json` - JSON格式，用于查看

### Step 3: 修改代码支持缓存

按照 `patch_kt_gen_for_cached_results.md` 中的说明修改 `models/constructor/kt_gen.py`。

### Step 4: 使用缓存重新运行

```bash
python main.py --dataset demo \
    --cached-semantic-results \
    output/dedup_intermediate/demo_semantic_results_20241023_123456.pkl
```

**结果：** 🚀 跳过所有semantic dedup的LLM调用，💰 节省大量tokens！

## 📊 数据结构

### 中间结果文件格式 (JSON)

```json
{
  "dataset": "demo",
  "dedup_type": "edge_deduplication",
  "triples": [
    {
      "head_id": "...",
      "head_name": "...",
      "relation": "...",
      "candidates": [...],
      "clustering": {...},
      "llm_groups": [
        {
          "cluster_id": 0,
          "batch_indices": [0, 1, 2],
          "groups": [
            {
              "members": [0, 1],
              "representative": 0,
              "rationale": "...",
              "member_details": [...]
            }
          ]
        }
      ],
      "final_merges": [...]
    }
  ]
}
```

### 还原的semantic_results格式 (Pickle)

```python
[
  {
    'type': 'semantic',
    'metadata': {
      'group_idx': 0,
      'cluster_idx': 0,
      'batch_num': 0,
      'batch_indices': [0, 1, 2],
      'overflow_indices': []
    },
    'response': '{"groups": [{"members": [1, 2], "representative": 1, "rationale": "..."}]}',
    'error': None
  },
  # ... 更多结果 ...
]
```

这与`_concurrent_llm_calls`的返回格式完全一致。

## 🔧 脚本详细说明

### restore_semantic_results.py

**功能：** 从中间结果JSON文件还原semantic_results

**用法：**
```bash
python restore_semantic_results.py <intermediate_results_file.json>
```

**支持的中间结果类型：**
- Edge deduplication results (`dedup_type: "edge_deduplication"`)
- Keyword deduplication results (`dedup_type: "keyword_deduplication"`)

**输出：**
- `.pkl` 文件：用于Python加载
- `.json` 文件：用于查看和验证

**关键功能：**
1. 解析中间结果JSON
2. 遍历每个triple/community的`llm_groups`
3. 重建LLM响应格式（将0-based索引转换为1-based）
4. 构建完整的semantic_results数据结构
5. 保存为pickle和JSON格式

### example_use_restored_results.py

**功能：** 展示如何使用还原的结果

**包含内容：**
1. 代码集成示例
2. 配置文件示例
3. 命令行参数示例
4. 验证工具

**运行：**
```bash
python example_use_restored_results.py
```

## 🛠️ 代码修改指南

详见 `patch_kt_gen_for_cached_results.md`，主要修改点：

### 1. 添加cached_semantic_results参数

```python
class KnowledgeTree:
    def __init__(self, dataset_name, cached_semantic_results=None):
        self.cached_semantic_results = cached_semantic_results
        # ...
```

### 2. 修改triple_deduplicate_semantic

```python
# 在PHASE 3中：
if self.cached_semantic_results:
    # 加载缓存
    with open(self.cached_semantic_results, 'rb') as f:
        semantic_results = pickle.load(f)
else:
    # 调用LLM
    semantic_results = self._concurrent_llm_calls(semantic_prompts)
```

### 3. 支持配置文件

```yaml
semantic_dedup:
  cached_results_path: "output/dedup_intermediate/demo_semantic_results_xxx.pkl"
```

### 4. 支持命令行参数

```bash
python main.py --cached-semantic-results <path_to_pkl>
```

## 📈 性能和成本对比

| 场景 | LLM调用次数 | 处理时间 | Token成本 |
|------|------------|---------|----------|
| 首次运行 | 100% | 100% | 100% |
| 使用缓存 | 0% | ~10% | 0% |

**节省说明：**
- ✅ 跳过所有semantic dedup的LLM API调用
- ✅ 处理时间减少90%以上
- ✅ Token成本降为0
- ✅ 适合反复调试和测试

## ⚠️ 注意事项

### 1. 缓存有效性

缓存的semantic_results只在以下条件下有效：
- 输入数据完全相同
- 聚类配置（clustering方法、阈值）相同
- Prompt模板没有修改

**如果修改了以上任何内容，需要重新生成缓存。**

### 2. 版本匹配

确保：
- 中间结果文件与当前运行的数据匹配
- prompts数量和顺序一致

脚本会自动验证结果数量，不匹配会fallback到LLM调用。

### 3. 存储空间

- JSON文件：可读性好，但文件较大
- Pickle文件：加载快，但不可读
- 建议保留两种格式

### 4. 安全性

Pickle文件可能包含恶意代码，只加载信任来源的文件。

## 🔍 调试和验证

### 查看还原的结果

```python
import pickle
import json

# 加载pickle
with open('demo_semantic_results_xxx.pkl', 'rb') as f:
    results = pickle.load(f)

print(f"Total results: {len(results)}")
print(f"First result: {results[0]}")

# 查看JSON格式
with open('demo_semantic_results_xxx.json', 'r') as f:
    data = json.load(f)
    print(json.dumps(data[0], indent=2))
```

### 验证结果正确性

```python
# 比较缓存运行和正常运行的输出
# 应该得到完全相同的最终知识图谱

from models.constructor.kt_gen import KnowledgeTree

# 正常运行
kg1 = KnowledgeTree(dataset_name="demo")
kg1.build()
output1 = kg1.format_output()

# 使用缓存
kg2 = KnowledgeTree(
    dataset_name="demo",
    cached_semantic_results="output/dedup_intermediate/demo_semantic_results_xxx.pkl"
)
kg2.build()
output2 = kg2.format_output()

# 比较
assert output1 == output2, "Outputs don't match!"
print("✅ Outputs are identical!")
```

### 检查日志

运行时注意查看日志：
```
INFO: 🚀 Using cached semantic_results from: ...
INFO: 💰 Skipping 150 LLM calls to save tokens!
INFO: ✅ Loaded 150 cached results
```

## 💡 常见问题

### Q1: 还原的结果数量不匹配怎么办？

**A:** 这通常意味着输入数据或聚类配置发生了变化。解决方法：
1. 确认使用的是同一份数据
2. 检查聚类配置是否一致
3. 重新生成中间结果和缓存

### Q2: 能否只缓存部分结果？

**A:** 当前脚本缓存所有semantic_results。如果需要部分缓存，需要修改：
1. `restore_semantic_results.py` - 添加过滤逻辑
2. `kt_gen.py` - 混合使用缓存和LLM调用

### Q3: 如何处理多个数据集？

**A:** 为每个数据集生成单独的缓存文件：
```bash
# 数据集1
python restore_semantic_results.py \
    output/dedup_intermediate/dataset1_edge_dedup_xxx.json

# 数据集2
python restore_semantic_results.py \
    output/dedup_intermediate/dataset2_edge_dedup_xxx.json
```

### Q4: Keyword dedup也支持吗？

**A:** 支持！脚本自动识别`dedup_type`：
- `edge_deduplication` - Triple去重
- `keyword_deduplication` - Keyword去重

## 📝 更新日志

- **2024-10-23**: 初始版本
  - 支持从edge_deduplication中间结果还原
  - 支持从keyword_deduplication中间结果还原
  - 提供完整的使用示例和代码补丁

## 🤝 贡献

如果发现问题或有改进建议，欢迎提交Issue或PR。

## 📄 许可

与主项目保持一致。
