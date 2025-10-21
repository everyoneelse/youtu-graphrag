# tqdm进度条添加说明

## 修改内容

已在 `_concurrent_llm_calls` 方法中添加 **tqdm 进度条**，实时显示LLM并发调用的进度。

## 修改文件

### 1. `models/constructor/kt_gen.py`

#### 添加导入
```python
from tqdm import tqdm
```

#### 修改并发调用逻辑
**之前**（简单的 executor.map）：
```python
with futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
    results = list(executor.map(_call_single_llm, prompts_with_metadata))
```

**现在**（使用 as_completed + tqdm）：
```python
with futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
    # Submit all tasks
    future_to_item = {
        executor.submit(_call_single_llm, item): item 
        for item in prompts_with_metadata
    }
    
    # Collect results with progress bar
    results = []
    with tqdm(total=len(prompts_with_metadata), desc="Processing LLM calls", unit="call") as pbar:
        for future in futures.as_completed(future_to_item):
            result = future.result()
            results.append(result)
            pbar.update(1)
```

### 2. `requirements.txt`

添加依赖：
```
tqdm==4.66.1
```

## 优势

### 1. **实时进度显示**
- 使用 `as_completed` 而非 `map`，每个任务完成就立即更新
- 不需要等待所有任务完成

### 2. **详细信息**
进度条显示：
```
Processing LLM calls:  45%|████▌     | 45/100 [00:23<00:28, 1.95call/s]
```
- 当前完成数 / 总数
- 百分比
- 进度条可视化
- 已用时间
- 预计剩余时间 (ETA)
- 处理速度 (calls/s)

### 3. **更好的用户体验**
- 用户知道还有多久完成
- 避免"卡住"的错觉
- 在处理大量prompts时尤其有用

## 使用示例

当执行 `triple_deduplicate_semantic()` 时，会看到两个进度条：

```bash
INFO: Prepared 15 groups for semantic deduplication
INFO: Collecting all clustering prompts...
INFO: Collected 18 clustering prompts, processing concurrently...

Processing LLM calls:  100%|██████████| 18/18 [00:36<00:00, 2.00call/s]

INFO: Parsing clustering results...
INFO: Collecting all semantic dedup prompts...
INFO: Collected 85 semantic dedup prompts, processing concurrently...

Processing LLM calls:  100%|██████████| 85/85 [02:50<00:00, 2.00call/s]

INFO: Parsing semantic dedup results...
INFO: Building final deduplicated graph...
INFO: Semantic deduplication completed
```

## 技术细节

### 为什么使用 `as_completed` 而非 `map`？

**executor.map 的问题**：
```python
results = list(executor.map(func, items))
# 问题：map 返回结果的顺序与输入顺序相同
# 必须等待前面的任务完成才能返回后面的结果
# 进度条更新不均匀
```

**as_completed 的优势**：
```python
for future in futures.as_completed(future_to_item):
    result = future.result()
    # 优势：哪个任务先完成就先处理哪个
    # 进度条实时更新
    # 更准确的速度显示
```

### 结果顺序

⚠️ **注意**：使用 `as_completed` 后，结果的顺序**不再与输入顺序相同**。

但这**不是问题**，因为：
1. 每个 result 都包含 `metadata`，可以追溯到原始的 group
2. 在 `_parse_clustering_results` 和 `_parse_semantic_dedup_results` 中，我们通过 `group_idx` 来分组结果
3. 最终结果不依赖于处理顺序

### 错误处理

```python
try:
    result = future.result()
    results.append(result)
except Exception as e:
    # 兜底错误处理（正常情况下不会触发）
    logger.error(f"Unexpected error in concurrent call: {e}")
    results.append({
        'type': 'unknown',
        'metadata': {},
        'response': None,
        'error': str(e)
    })
pbar.update(1)  # 无论成功失败都更新进度
```

## 性能影响

- ✅ **几乎无性能影响**：tqdm 开销极小（<1ms per update）
- ✅ **不影响并发**：进度条更新在主线程，不阻塞工作线程
- ✅ **可选禁用**：如果不想看进度条，可以设置环境变量 `TQDM_DISABLE=1`

## 自定义选项

如果需要自定义进度条样式，可以修改 tqdm 参数：

```python
with tqdm(
    total=len(prompts_with_metadata),
    desc="Processing LLM calls",
    unit="call",
    # 可选参数：
    # ncols=80,              # 进度条宽度
    # bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt}",  # 自定义格式
    # disable=False,         # 是否禁用
    # leave=True,            # 完成后是否保留
    # position=0,            # 多进度条时的位置
) as pbar:
    ...
```

## 兼容性

- ✅ 支持所有终端（Windows/Linux/Mac）
- ✅ 支持 Jupyter Notebook（自动检测）
- ✅ 支持日志重定向
- ✅ 可以与 logger 共存

## 依赖版本

- `tqdm==4.66.1`
  - 稳定版本
  - 支持 Python 3.7+
  - 轻量级（无额外依赖）

## 测试建议

安装tqdm后测试：
```bash
pip install tqdm==4.66.1
python main.py --config config/your_config.yaml
```

观察两个进度条：
1. Clustering阶段的进度条
2. Semantic dedup阶段的进度条

## 总结

✅ 添加了实时进度条显示  
✅ 使用 `as_completed` 实现真正的实时更新  
✅ 完善的错误处理  
✅ 几乎零性能影响  
✅ 显著提升用户体验

**安装命令**：
```bash
pip install tqdm==4.66.1
```
