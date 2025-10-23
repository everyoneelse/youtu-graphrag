# 快速开始：还原Semantic Results节省LLM成本

## 🎯 目标

从`triple_deduplicate_semantic`保存的中间结果还原`semantic_results`，跳过昂贵的LLM调用，节省tokens成本。

## ⚡ 三步使用

### 步骤1：首次运行保存中间结果

```bash
# 确保配置开启save_intermediate_results
python main.py --dataset demo
```

输出：`output/dedup_intermediate/demo_edge_dedup_20241023_123456.json`

### 步骤2：还原semantic_results

```bash
python restore_semantic_results.py \
    output/dedup_intermediate/demo_edge_dedup_20241023_123456.json
```

输出：
- `demo_semantic_results_20241023_123456.pkl` (用于加载)
- `demo_semantic_results_20241023_123456.json` (用于查看)

### 步骤3：使用缓存重新运行

修改代码后使用缓存（详见`patch_kt_gen_for_cached_results.md`）：

```bash
python main.py --dataset demo \
    --cached-semantic-results \
    output/dedup_intermediate/demo_semantic_results_20241023_123456.pkl
```

**结果：🚀 跳过所有LLM调用，💰 节省100% tokens！**

## 🧪 测试脚本

```bash
# 运行完整测试
python test_restore_semantic_results.py

# 测试输出
✅ 所有测试通过！
```

## 📊 效果对比

| 运行方式 | LLM调用 | 处理时间 | Token成本 |
|---------|---------|---------|----------|
| 正常运行 | 100% | 100% | 100% |
| 使用缓存 | 0% | ~10% | 0% |

## 📁 相关文件

| 文件 | 说明 |
|------|------|
| `restore_semantic_results.py` | 核心脚本：还原semantic_results |
| `test_restore_semantic_results.py` | 测试脚本：验证功能 |
| `example_use_restored_results.py` | 使用示例 |
| `patch_kt_gen_for_cached_results.md` | 代码修改指南 |
| `RESTORE_SEMANTIC_RESULTS_README.md` | 完整文档 |

## 💡 使用场景

- ✅ **调试**：修改后续处理逻辑，不重新调用LLM
- ✅ **测试**：测试不同参数，复用LLM结果
- ✅ **成本控制**：大规模处理，复用已有结果
- ✅ **错误恢复**：下游出错，从LLM结果重新开始

## ⚠️ 注意事项

**缓存仅在以下情况有效：**
- ✅ 输入数据相同
- ✅ 聚类配置相同
- ✅ Prompt模板未修改

**如修改了以上任何内容，需重新生成缓存。**

## 🔍 验证结果

```python
import pickle
import json

# 加载并查看
with open('demo_semantic_results_xxx.pkl', 'rb') as f:
    results = pickle.load(f)

print(f"Total results: {len(results)}")
print(f"First result: {json.dumps(results[0], indent=2)}")
```

## 📞 问题？

查看完整文档：`RESTORE_SEMANTIC_RESULTS_README.md`
