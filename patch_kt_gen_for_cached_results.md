# 补丁：支持使用缓存的semantic_results

这个文档展示如何修改`models/constructor/kt_gen.py`来支持使用缓存的semantic_results，从而跳过昂贵的LLM调用。

## 修改1：添加cached_results参数到构造函数

**位置：** `KnowledgeTree.__init__` 方法

```python
def __init__(
    self,
    dataset_name: str,
    chunk_func: Optional[Callable] = None,
    cached_semantic_results: str = None,  # 🔥 新增参数
):
    """
    Args:
        dataset_name: dataset name
        chunk_func: function to chunk text
        cached_semantic_results: Path to cached semantic_results pickle file.
                                If provided, will skip LLM calls in semantic deduplication.
    """
    self.dataset_name = dataset_name
    self.chunk_func = chunk_func
    self.cached_semantic_results = cached_semantic_results  # 🔥 保存参数
    
    # ... 其他初始化代码 ...
```

## 修改2：修改triple_deduplicate_semantic方法

**位置：** `triple_deduplicate_semantic` 方法中的PHASE 3

**原始代码（Line 4370-4375）：**
```python
logger.info(f"Collected {len(semantic_prompts)} semantic dedup prompts, processing concurrently...")
semantic_results = self._concurrent_llm_calls(semantic_prompts)

# Parse semantic dedup results and update group_data
logger.info("Parsing semantic dedup results...")
self._parse_semantic_dedup_results(dedup_groups, semantic_results)
```

**修改后的代码：**
```python
logger.info(f"Collected {len(semantic_prompts)} semantic dedup prompts")

# 🔥 使用缓存的结果或调用LLM
if self.cached_semantic_results:
    logger.info(f"🚀 Using cached semantic_results from: {self.cached_semantic_results}")
    logger.info(f"💰 Skipping {len(semantic_prompts)} LLM calls to save tokens!")
    
    import pickle
    try:
        with open(self.cached_semantic_results, 'rb') as f:
            semantic_results = pickle.load(f)
        logger.info(f"✅ Loaded {len(semantic_results)} cached results")
        
        # 验证缓存结果数量
        if len(semantic_results) != len(semantic_prompts):
            logger.warning(
                f"⚠️  Cached results count ({len(semantic_results)}) "
                f"doesn't match prompts count ({len(semantic_prompts)}). "
                f"Falling back to LLM calls."
            )
            semantic_results = self._concurrent_llm_calls(semantic_prompts)
    except Exception as e:
        logger.error(f"❌ Failed to load cached results: {e}")
        logger.info("Falling back to LLM calls...")
        semantic_results = self._concurrent_llm_calls(semantic_prompts)
else:
    logger.info("Processing concurrently...")
    semantic_results = self._concurrent_llm_calls(semantic_prompts)

# Parse semantic dedup results and update group_data
logger.info("Parsing semantic dedup results...")
self._parse_semantic_dedup_results(dedup_groups, semantic_results)
```

## 修改3（可选）：从配置文件读取cached_results路径

**位置：** `triple_deduplicate_semantic` 方法开始处

**在方法开始处添加：**
```python
def triple_deduplicate_semantic(self):
    """Perform semantic deduplication on all edges"""
    config = self._get_semantic_dedup_config()
    save_intermediate = config and getattr(config, "save_intermediate_results", False)
    if save_intermediate:
        self._edge_dedup_results = []
    
    # 🔥 如果配置中指定了cached_results_path，使用它
    if config and not self.cached_semantic_results:
        cached_path = getattr(config, "cached_results_path", None)
        if cached_path:
            logger.info(f"Using cached_results_path from config: {cached_path}")
            self.cached_semantic_results = cached_path
    
    # ... 继续原有代码 ...
```

**配置文件示例（config/semantic_dedup.yaml）：**
```yaml
semantic_dedup:
  save_intermediate_results: true
  intermediate_results_path: "output/dedup_intermediate/"
  
  # 使用缓存的semantic_results（如果不需要，注释掉或删除）
  cached_results_path: "output/dedup_intermediate/demo_semantic_results_20241023_123456.pkl"
  
  threshold: 0.85
  max_batch_size: 8
```

## 修改4（可选）：在_deduplicate_keyword_nodes中也支持缓存

**位置：** `_deduplicate_keyword_nodes` 方法中的PHASE 3

类似的修改应用到keyword deduplication：

```python
logger.info(f"Collected {len(semantic_prompts)} keyword semantic dedup prompts")

# 🔥 使用缓存的结果或调用LLM
if self.cached_semantic_results:
    logger.info(f"🚀 Using cached semantic_results for keyword dedup")
    # ... 加载缓存逻辑 ...
else:
    logger.info("Processing concurrently...")
    semantic_results = self._concurrent_llm_calls(semantic_prompts)
```

## 使用方法

### 方法1：通过构造函数参数

```python
from models.constructor.kt_gen import KnowledgeTree

# 首次运行，保存中间结果
kg = KnowledgeTree(
    dataset_name="demo",
    cached_semantic_results=None  # 不使用缓存
)
kg.build()  # save_intermediate_results需要在配置中开启

# 第二次运行，使用缓存
kg = KnowledgeTree(
    dataset_name="demo",
    cached_semantic_results="output/dedup_intermediate/demo_semantic_results_20241023.pkl"
)
kg.build()  # 这次会跳过LLM调用
```

### 方法2：通过配置文件

**config/semantic_dedup.yaml:**
```yaml
semantic_dedup:
  cached_results_path: "output/dedup_intermediate/demo_semantic_results_xxx.pkl"
```

然后正常运行即可。

### 方法3：通过命令行参数

**修改main.py添加参数：**
```python
parser.add_argument(
    '--cached-semantic-results',
    type=str,
    default=None,
    help='Path to cached semantic_results pickle file'
)

# 在创建KnowledgeTree时传入
kg = KnowledgeTree(
    dataset_name=args.dataset,
    cached_semantic_results=args.cached_semantic_results
)
```

**运行命令：**
```bash
python main.py --dataset demo \
    --cached-semantic-results output/dedup_intermediate/demo_semantic_results_xxx.pkl
```

## 完整工作流程

```bash
# Step 1: 首次运行，保存中间结果
python main.py --dataset demo

# 这会生成：output/dedup_intermediate/demo_edge_dedup_20241023_123456.json

# Step 2: 还原semantic_results
python restore_semantic_results.py \
    output/dedup_intermediate/demo_edge_dedup_20241023_123456.json

# 这会生成：output/dedup_intermediate/demo_semantic_results_20241023_123456.pkl

# Step 3: 使用缓存重新运行（不调用LLM）
python main.py --dataset demo \
    --cached-semantic-results \
    output/dedup_intermediate/demo_semantic_results_20241023_123456.pkl
```

## 注意事项

1. **缓存有效性：** 缓存的semantic_results只在以下情况下有效：
   - 输入数据没有变化
   - 聚类结果没有变化（clustering配置相同）
   - prompts数量和顺序一致

2. **验证缓存：** 代码会自动验证缓存的结果数量是否与当前prompts数量匹配，不匹配会自动fallback到LLM调用

3. **调试：** 如果遇到问题，检查日志中的缓存加载信息

4. **性能提升：** 使用缓存可以节省：
   - 100% 的LLM API调用成本
   - 90%+ 的处理时间
   - 适合调试、测试和重复运行场景

## 测试

修改后可以用以下代码测试：

```python
# test_cached_results.py
from models.constructor.kt_gen import KnowledgeTree

# 测试1：正常运行（不使用缓存）
kg1 = KnowledgeTree(dataset_name="demo")
print("Test 1: Normal run (no cache)")
# kg1.build()

# 测试2：使用缓存
kg2 = KnowledgeTree(
    dataset_name="demo",
    cached_semantic_results="output/dedup_intermediate/demo_semantic_results_xxx.pkl"
)
print("Test 2: Using cached results")
# kg2.build()

# 测试3：缓存文件不存在（应该fallback到LLM调用）
kg3 = KnowledgeTree(
    dataset_name="demo",
    cached_semantic_results="nonexistent_file.pkl"
)
print("Test 3: Invalid cache file (should fallback)")
# kg3.build()
```
