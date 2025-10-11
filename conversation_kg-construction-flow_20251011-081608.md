# 对话记录：知识图谱构建流程分析

**时间**: 2025-10-11 08:16:08  
**主题**: Youtu-GraphRAG 知识图谱构建流程解析  
**分支**: cursor/build-knowledge-graph-with-llm-extraction-585a

---

## 用户问题

所以这个repo构建知识图谱的流程就是，先分chunk？然后通过llm抽取实体和关系？抽取完成之后做什么？

---

## 回答概要

根据代码分析，这个 repo 构建知识图谱的完整流程如下：

## 📋 完整流程

### 1️⃣ **文本分块（Chunking）**

首先对输入文档进行分块处理：

```python
# models/constructor/kt_gen.py: 43-61
def chunk_text(self, text) -> Tuple[List[str], Dict[str, str]]:
    if self.dataset_name in self.datasets_no_chunk:
        chunks = [f"{text.get('title', '')} {text.get('text', '')}".strip() 
                 if isinstance(text, dict) else str(text)]
    else:
        chunks = [str(text)]

    chunk2id = {}
    for chunk in chunks:
        try:
            chunk_id = nanoid.generate(size=8)
            chunk2id[chunk_id] = chunk
```

每个 chunk 会被分配一个唯一的 8 位 ID，用于后续追踪。

---

### 2️⃣ **LLM 抽取实体和关系**

通过 LLM API 从每个 chunk 中抽取三类信息：

- **属性 (attributes)**: 实体的属性信息
- **三元组 (triples)**: `[主体, 关系, 客体]` 格式的关系
- **实体类型 (entity_types)**: 每个实体对应的 schema 类型

```python
# models/constructor/kt_gen.py: 245-271
def process_level1_level2(self, chunk: str, id: int):
    """Process attributes (level 1) and triples (level 2) with optimized structure."""
    prompt = self._get_construction_prompt(chunk)
    llm_response = self.extract_with_llm(prompt)
    
    # Validate and parse response
    parsed_response = self._validate_and_parse_llm_response(prompt, llm_response)
    if not parsed_response:
        return
    
    extracted_attr = parsed_response.get("attributes", {})
    extracted_triples = parsed_response.get("triples", [])
    entity_types = parsed_response.get("entity_types", {})
```

**支持两种模式：**
- **NoAgent 模式**: 标准抽取流程
- **Agent 模式**: 支持动态 Schema 演化，LLM 可以建议新的实体类型、关系类型和属性类型

---

### 3️⃣ **抽取完成后：构建四层知识树**

这是该框架的核心创新！抽取完成后会构建一个**四层层次化知识树结构**：

#### **Level 1 - 属性层 (Attribute Layer)**
- 存储实体的属性节点
- 通过 `has_attribute` 关系连接到对应实体
- 例如: 人物 → 年龄、职业等属性

#### **Level 2 - 关系层 (Entity & Relation Layer)**
- 构建实体间的三元组关系网络
- 形成知识图谱的核心结构
- 例如: `[张三, 工作于, 腾讯]`

#### **Level 3 & 4 - 关键词层和社区层 (Community Layer)**
使用 **Tree-Comm 算法**进行社区检测和层次化组织：

```python
# models/constructor/kt_gen.py: 423-440
def process_level4(self):
    """Process communities using Tree-Comm algorithm"""
    level2_nodes = [n for n, d in self.graph.nodes(data=True) if d['level'] == 2]
    start_comm = time.time()
    _tree_comm = tree_comm.FastTreeComm(
        self.graph, 
        embedding_model=self.config.tree_comm.embedding_model,
        struct_weight=self.config.tree_comm.struct_weight,
    )
    comm_to_nodes = _tree_comm.detect_communities(level2_nodes)

    # create super nodes (level 4 communities)
    _tree_comm.create_super_nodes_with_keywords(comm_to_nodes, level=4)
```

**Tree-Comm 算法特点**：
- 结合**结构拓扑特征**和**子图语义信息**
- 比传统 Leiden 和 Louvain 算法效果更好
- 生成层次化社区摘要，支持多粒度检索

---

### 4️⃣ **三元组去重**

对 Level 1 和 Level 2 的三元组进行去重处理：

```python
# models/constructor/kt_gen.py: 537-550
def triple_deduplicate(self):
    """deduplicate triples in lv1 and lv2"""
    new_graph = nx.MultiDiGraph()

    for node, node_data in self.graph.nodes(data=True):
        new_graph.add_node(node, **node_data)

    seen_triples = set()
    for u, v, key, data in self.graph.edges(keys=True, data=True):
        relation = data.get('relation') 
        if (u, v, relation) not in seen_triples:
            seen_triples.add((u, v, relation))
            new_graph.add_edge(u, v, **data)
```

确保图中不会有重复的关系三元组。

---

### 5️⃣ **保存输出**

构建完成后保存两类文件：

- **Chunks 文件**: `output/chunks/{dataset}.txt`
  - 格式: `id: {chunk_id}\tChunk: {chunk_text}`
  - 用于后续检索时关联原始文本

- **Graph 文件**: `output/graphs/{dataset}_new.json`
  - JSON 格式存储四层知识树结构
  - 可直接导入 Neo4j 进行可视化

```python
# models/constructor/kt_gen.py: 578-599
def build_knowledge_graph(self, corpus):
    logger.info(f"========{'Start Building':^20}========")
    
    with open(corpus, 'r', encoding='utf-8') as f:
        documents = json_repair.load(f)
    
    self.process_all_documents(documents)
    
    self.save_chunks_to_file()
    
    output = self.format_output()
    
    json_output_path = f"output/graphs/{self.dataset_name}_new.json"
    os.makedirs("output/graphs", exist_ok=True)
    with open(json_output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
```

---

### 6️⃣ **构建 FAISS 索引**（检索阶段）

图谱构建完成后，进入检索阶段，首先构建向量索引：

```python
# main.py: 185-189
logger.info("🚀 Building FAISS index 🚀")
logger.info("-"*30)
start_time = time.time()
kt_retriever.build_indices()
logger.info(f"Time taken to build FAISS index: {time.time() - start_time} seconds")
```

**索引内容包括**：
- **节点（实体）**向量
- **关系（三元组）**向量
- **Chunks** 向量
- **社区摘要**向量

这些索引被缓存到 `retriever/faiss_cache_new/{dataset}/` 目录。

---

### 7️⃣ **检索和推理**

框架支持两种检索推理模式：

#### **NoAgent 模式**
基础检索模式，流程如下：
1. 问题分解 → 将复杂问题分解为多个子问题
2. 并行检索 → 同时处理所有子问题的检索
3. 聚合结果 → 合并所有检索到的三元组和 chunks
4. 生成答案 → 基于检索上下文生成最终答案

#### **Agent 模式 (IRCoT - Iterative Retrieval Chain of Thought)**
迭代推理模式，更加智能：

```python
# main.py: 406-469
logger.info(f"🚀 Starting IRCoT for question: {current_query}")

while step <= max_steps:
    logger.info(f"📝 IRCoT Step {step}/{max_steps}")
    
    # 构建当前上下文
    context = "=== Triples ===\n" + "\n".join(dedup_triples)
    context += "\n=== Chunks ===\n" + "\n".join(dedup_chunk_contents)
    
    # 生成推理和新查询
    response = kt_retriever.generate_answer(ircot_prompt)
    thoughts.append(response)
    
    # 判断是否已找到答案
    if "So the answer is:" in response:
        logger.info("✅ Final answer found, stopping IRCoT")
        break

    # 提取新的查询并继续检索
    if "The new query is:" in response:
        new_query = response.split("The new query is:")[1].strip()
        current_query = new_query
        
        # 执行新一轮检索
        retrieval_results, time_taken = kt_retriever.process_retrieval_results(
            current_query, top_k=config.retrieval.top_k_filter
        )
        
        # 更新知识库
        all_triples.update(new_triples)
        all_chunk_ids.update(new_chunk_ids)
    
    step += 1
```

**Agent 模式特点**：
- 先运行 NoAgent 模式获得初始分析
- 基于初始结果进行迭代推理
- 每步可以生成新的查询进行补充检索
- 提供完整的推理链路（思维过程可见）

---

## 🎯 核心创新点总结

1. **四层知识树**: 属性→实体关系→关键词→社区，支持多粒度检索
   - Level 1: 属性层
   - Level 2: 实体关系层
   - Level 3: 关键词层
   - Level 4: 社区层

2. **Tree-Comm 算法**: 结构+语义双重感知的社区检测，优于传统算法

3. **Schema 演化**: Agent 模式支持动态扩展 schema，无需人工干预即可适应新领域

4. **迭代检索 (IRCoT)**: 通过迭代反思机制实现深度推理，显著提升复杂问题的回答精度

5. **并行处理**: 支持多线程并行处理文档和子问题，提高效率

6. **向量索引**: 对所有层级的内容建立 FAISS 索引，实现高效检索

---

## 📂 关键文件说明

- **`models/constructor/kt_gen.py`**: KTBuilder - 知识图谱构建核心类
- **`models/retriever/enhanced_kt_retriever.py`**: KTRetriever - 检索核心类
- **`models/retriever/agentic_decomposer.py`**: GraphQ - 问题分解模块
- **`models/retriever/faiss_filter.py`**: DualFAISSRetriever - FAISS 检索器
- **`utils/tree_comm.py`**: FastTreeComm - 社区检测算法实现
- **`utils/graph_processor.py`**: 图的加载、保存和处理工具
- **`main.py`**: 主程序入口，包含完整的构建和检索流程

---

## 🔄 完整流程图

```
原始文档
   ↓
[1] 文本分块 (Chunking)
   ↓
[2] LLM 抽取 (属性 + 三元组 + 实体类型)
   ↓
[3] 构建四层知识树
   ├── Level 1: 属性层
   ├── Level 2: 实体关系层
   ├── Level 3: 关键词层
   └── Level 4: 社区层 (Tree-Comm)
   ↓
[4] 三元组去重
   ↓
[5] 保存输出
   ├── output/chunks/{dataset}.txt
   └── output/graphs/{dataset}_new.json
   ↓
[6] 构建 FAISS 索引
   ├── 节点向量索引
   ├── 关系向量索引
   ├── Chunk 向量索引
   └── 社区向量索引
   ↓
[7] 检索推理
   ├── NoAgent: 问题分解 → 并行检索 → 生成答案
   └── Agent: NoAgent + IRCoT 迭代推理
```

---

## 💡 性能优势

根据论文实验结果：
- **Token 成本节约**: 最高达 90.71%
- **精度提升**: 最高达 16.62%
- **帕累托前沿**: 在成本和精度之间实现最优平衡
- **跨域迁移**: 在 Schema 最小人为干预下实现跨领域应用

---

**对话结束**
