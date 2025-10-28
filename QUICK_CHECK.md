# ✅ 快速检查清单

运行以下命令验证一切正常：

## 1. 检查代码文件

```bash
# 检查行数（应该是6040）
wc -l models/constructor/kt_gen.py

# 检查没有embedded prompt（应该找不到）
grep "_get_embedded_prompt_template_v2" models/constructor/kt_gen.py

# 检查新函数存在（应该找到）
grep "def deduplicate_heads_with_llm_v2" models/constructor/kt_gen.py
```

## 2. 检查配置文件

```bash
# 检查新prompt存在（应该找到）
grep "with_representative_selection" config/base_config.yaml

# 检查关键规则都在（应该都找到）
grep "PROHIBITED MERGE REASONS" config/base_config.yaml
grep "DECISION PROCEDURE" config/base_config.yaml
grep "TYPE CONSISTENCY" config/base_config.yaml
grep "PRIMARY REPRESENTATIVE" config/base_config.yaml
```

## 3. 运行测试

```bash
# 运行测试（应该全部通过）
python test_head_dedup_llm_driven.py

# 预期输出最后一行：
# 🎉 All tests passed! System is ready to use.
```

## 4. 验证导入

```bash
python3 << 'PYTHON'
from models.constructor.kt_gen import KnowledgeTreeGen
from config import get_config

config = get_config()
builder = KnowledgeTreeGen("test", config)

# 检查所有新方法都存在
assert hasattr(builder, 'deduplicate_heads_with_llm_v2')
assert hasattr(builder, '_merge_head_nodes_with_alias')
assert hasattr(builder, 'is_alias_node')
assert hasattr(builder, 'resolve_alias')

print("✅ All methods exist and can be imported!")
PYTHON
```

---

## ✅ 如果所有检查都通过

系统已准备好使用！

```python
# 立即开始使用
stats = builder.deduplicate_heads_with_llm_v2()
print(f"✅ Done!")
```

---

## ❌ 如果有检查失败

1. 检查备份文件是否存在
2. 查看错误信息
3. 参考文档:
   - STAGE2_IMPLEMENTATION_COMPLETE.md
   - PROMPT_FIX_CONFIRMED.md
   - PROMPT_IN_CODE_FIX.md
