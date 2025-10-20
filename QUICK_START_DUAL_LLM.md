# 双 LLM 快速入门 (5 分钟上手)

## 🎯 这是什么？

一个功能，让你为语义去重的不同阶段使用不同的 LLM 模型：
- **聚类阶段** → 用便宜的模型 (如 GPT-3.5)
- **去重阶段** → 用强大的模型 (如 GPT-4)

**结果**: 节省 15-30% 成本，保持高准确性！

## ⚡ 3 步配置

### 第 1 步: 设置 API Key

```bash
# 编辑 .env 文件
export CLUSTERING_LLM_API_KEY="your-clustering-key"
export DEDUP_LLM_API_KEY="your-dedup-key"
```

### 第 2 步: 修改配置

在你的 `config.yaml` 中添加：

```yaml
construction:
  semantic_dedup:
    enabled: true
    clustering_method: llm
    
    clustering_llm:
      model: "gpt-3.5-turbo"
      base_url: "https://api.openai.com/v1"
      api_key: "${CLUSTERING_LLM_API_KEY}"
      temperature: 0.3
    
    dedup_llm:
      model: "gpt-4"
      base_url: "https://api.openai.com/v1"
      api_key: "${DEDUP_LLM_API_KEY}"
      temperature: 0.0
```

### 第 3 步: 运行

```bash
python main.py --config config/your_config.yaml --dataset your_dataset
```

## 📋 推荐配置

### 🏆 最佳性价比（推荐）
```yaml
clustering_llm:
  model: "gpt-3.5-turbo"
dedup_llm:
  model: "gpt-4"
```
**成本**: ⭐⭐ | **准确性**: ⭐⭐⭐⭐

### 💰 最省钱
```yaml
clustering_llm:
  model: "gpt-3.5-turbo"
dedup_llm:
  model: "gpt-3.5-turbo"
```
**成本**: ⭐ | **准确性**: ⭐⭐⭐

### 🇨🇳 国内推荐 (DeepSeek)
```yaml
clustering_llm:
  model: "deepseek-chat"
  base_url: "https://api.deepseek.com"
dedup_llm:
  model: "deepseek-chat"
  base_url: "https://api.deepseek.com"
```
**成本**: ⭐ | **准确性**: ⭐⭐⭐⭐

## 🔍 验证

### 查看日志
```bash
# 运行后，日志会显示：
INFO: Initialized custom clustering LLM: gpt-3.5-turbo
INFO: Initialized custom deduplication LLM: gpt-4
```

### 测试配置
```bash
python test_dual_llm.py
```

## 💡 什么时候用？

✅ **建议使用双 LLM:**
- 对成本敏感
- 数据量适中（< 1000 triples per (head, relation)）
- 想平衡成本和准确性

❌ **可以不用:**
- 数据量很小（直接用强大模型）
- 预算充足（直接用 GPT-4）
- 使用 embedding 聚类就够了

## 📊 成本对比 (1000 tails)

| 配置 | 成本 | 节省 |
|------|------|------|
| GPT-4 单一 | $4.74 | - |
| GPT-3.5 + GPT-4 | $3.82 | **19%** |
| DeepSeek 双模型 | $1.28 | **73%** |

## 🆘 问题？

### Q: 必须配置两个模型吗？
**A**: 不必须。不配置的话会使用默认 LLM（向后兼容）。

### Q: 可以用相同模型吗？
**A**: 可以！可以用相同模型但不同 temperature。

### Q: 如何确认生效？
**A**: 查看日志，会显示使用的模型名称。

## 📚 更多信息

- **完整指南**: [DUAL_LLM_GUIDE.md](./DUAL_LLM_GUIDE.md)
- **详细总结**: [DUAL_LLM_SUMMARY.md](./DUAL_LLM_SUMMARY.md)
- **配置示例**: [config/example_with_dual_llm.yaml](./config/example_with_dual_llm.yaml)
- **更新日志**: [DUAL_LLM_CHANGELOG.md](./DUAL_LLM_CHANGELOG.md)

## 🚀 立即开始

```bash
# 1. 复制示例配置
cp config/example_with_dual_llm.yaml config/my_config.yaml

# 2. 编辑你的 API keys
vim config/my_config.yaml

# 3. 运行测试
python test_dual_llm.py

# 4. 运行完整流程
python main.py --config config/my_config.yaml --dataset demo
```

就这么简单！🎉

---

**更新时间**: 2025-10-20
