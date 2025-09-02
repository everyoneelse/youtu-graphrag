<div align="center">
<img src="assets/logo.png" alt="Youtu-GraphRAG Logo" width="170"/>

# 🌟 Youtu-GraphRAG: Vertically Unified Agents for Graph Retrieval-Augmented Complex Reasoning

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Documentation](https://img.shields.io/badge/paper-latest-blue.svg)](Youtu-GraphRAG.pdf)
[![Tencent Youtu Lab GraphRAG Comunity](https://img.shields.io/badge/Youtu--_-GraphRAG_Community-8A2BE2)](assets/wechat.png)

*🚀 Revolutionary framework moving Pareto Frontier with 90.71% lower token cost and 16.62% higher accuracy over SOTA baselines*

[🔖 中文版](README-CN.md) • [⭐ Contributions](#contributions) • [📊 Benchmarks](https://huggingface.co/datasets/Youtu-Graph/AnonyRAG) • [🚀 Getting Started](#quickstart)


</div>

## 🏗️ Framework Architecture

<div align="center">
<img src="assets/framework.png" alt="Youtu-GraphRAG Framework Architecture" width="70%"/><br>
A skeched overview of our proposed framework Youtu-GraphRAG.
</div>


## 🎯 Brief Introduction

<table>
<tr>
<td width="30%">
<img src="assets/pareto.png" alt="Moving Pareto Frontier" width="100%"/>
</td>
<td width="70%">

**Youtu-GraphRAG** is a vertically unified agentic paradigm that jointly connects the entire framework as an intricate integration based on graph schema. We allow seamless domain transfer with minimal intervention on the graph schema, providing insights of the next evolutionary GraphRAG paradigm for real-world applications with remarkable adaptability.

📊 **Results**: Extensive experiments across six challenging benchmarks demonstrate the robustness of Youtu-GraphRAG, remarkably moving the Pareto frontier with up to **90.71% saving of token costs** and **16.62% higher accuracy** over state-of-the-art baselines. The results indicate our adaptability, allowing seamless domain transfer with minimal intervention on schema.

</td>
</tr>
</table>

<img src="assets/performance.png" alt="Cost/acc performance" width="51.6%"/>
<img src="assets/radar.png" alt="radar comparison" width="25%"/>

### 🎨 When to use Youtu-GraphRAG: Main Application Scenarios

🔗 Multi-hop Reasoning/Summarization/Conclusion: Complex questions requiring multi-step reasoning<br>
📚 Knowledge-Intensive Tasks: Questions dependent on large amounts of structured/private/domain knowledge<br>
🌐 Domain Scalability: Easily support novels, encyclopedias, academic papers, personal knowledge base, private/commercial knowledge base and other domains with minimal intervention on the shcema<br>

<a id="contributions"></a>
## 🚀 Contributions and Novely

Based on our unified agentic paradigm for Graph Retrieval-Augmented Generation (GraphRAG), Youtu-GraphRAG introduces several key innovations that jointly connect the entire framework as an intricate integration:


<summary><strong>🏗️ 1. Schema-Guided Hierarchical Knowledge Tree Construction</strong></summary>

- 🌱 **Seed Graph Schema**: Introduces targeted entity types, relations, and attribute types to bound automatic extraction agents
- 📈 **Scalable Schema Expansion**: Continuously expands schemas for adaptability over unseen domains
- 🏢 **Four-Level Architecture**: 
  - **Level 1 (Attributes)**: Entity property information
  - **Level 2 (Relations)**: Entity relationship triples
  - **Level 3 (Keywords)**: Keyword indexing
  - **Level 4 (Communities)**: Hierarchical community structure
- ⚡ **Quick Adaptation to industrial applications**: We allow seamless domain transfer with minimal intervention on the schema


<summary><strong>🌳 2. Dually-Perceived Community Detection</strong></summary>

- 🔬 **Novel Community Detection Algorithm**: Fuses structural topology with subgraph semantics for comprehensive knowledge organization
- 📊 **Hierarchical Knowledge Tree**: Naturally yields a structure supporting both top-down filtering and bottom-up reasoning that performs better than traditional Leiden and Louvain algorithms
- 📝 **Community Summaries**: LLM-enhanced community summarization for higher-level knowledge abstraction

<img src="assets/comm.png" alt="Youtu-GraphRAG Community Detection" width="30%"/>


<summary><strong>🤖 3. Agentic Retrieval</strong></summary>

- 🎯 **Schema-Aware Decomposition**: Interprets the same graph schema to transform complex queries into tractable and parallel sub-queries
- 🔄 **Iterative Reflection**: Performs reflection for more advanced reasoning through IRCoT (Iterative Retrieval Chain of Thought)

<img src="assets/agent.png" alt="Youtu-GraphRAG Agentic Decomposer" width="30%"/>


<!-- <details> -->
<summary><strong>🧠 4. Advanced Construction and Reasoning Capabilities for real-world deployment</strong></summary>

- 🎯 **Performance Enhancement**: Less token costs and higher accuracy with optimized prompting, indexing and retrieval strategies
- 🤹‍♀️ **User friendly visualization**: In ```output/graphs/```, the four-level knowledge tree supports visualization with neo4j import，making reasoning paths and knowledge organization vividly visable to users
- ⚡ **Parallel Sub-question Processing**: Concurrent handling of decomposed questions for efficiency and complex scenarios
- 🤔 **Iterative Reasoning**: Step-by-step answer construction with reasoning traces
- 📊 **Domain Scalability**: Designed for enterprise-scale deployment with minimal manual intervention for new domains
<!-- </details> -->


<summary><strong>📈 5. Fair Anonymous Dataset 'AnonyRAG'</strong></summary>

- Link: [Hugging Face AnonyRAG](https://huggingface.co/datasets/Youtu-Graph/AnonyRAG)
- **Against knowledeg leakage in LLM/embedding model pretraining**
- **In-depth test on real retrieval performance of GraphRAG**
- **Multi-lingual with Chinese and English versions**


</details>


<summary><strong>⚙️ 6. Unified Configuration Management</strong></summary>

- 🎛️ **Centralized Parameter Management**: All components configured through a single YAML file
- 🔧 **Runtime Parameter Override**: Dynamic configuration adjustment during execution
- 🌍 **Multi-Environment Support**: Seamless domain transfer with minimal intervention on schema
- 🔄 **Backward Compatibility**: Ensures existing code continues to function



## 📁 Project Structure

```
youtu-graphrag/
├── 📁 config/                     # Configuration System
│   ├── base_config.yaml           # Main configuration file
│   ├── config_loader.py           # Configuration loader
│   └── __init__.py                # Configuration module interface
│
├── 📁 data/                       # Data Directory
│
├── 📁 models/                     # Core Models
│   ├── 📁 constructor/            # Knowledge Graph Construction
│   │   └── kt_gen.py              # KTBuilder - Hierarchical graph builder
│   ├── 📁 retriever/              # Retrieval Module
│   │   ├── enhanced_kt_retriever.py  # KTRetriever - Main retriever
│   │   ├── agentic_decomposer.py     # Query decomposer
│   └── └── faiss_filter.py           # DualFAISSRetriever - FAISS retrieval
│
├── 📁 utils/                      # Utility Modules
│   ├── tree_comm_fast.py         # community detection algorithm
│   ├── call_llm_api.py           # LLM API calling
│   ├── eval.py                   # Evaluation tools
│   └── graph_processor.py        # Graph processing tools
│
├── 📁 schemas/                   # Dataset Schemas
├── 📁 assets/                    # Assets (images, figures)
│
├── 📁 output/                    # Output Directory
│   ├── graphs/                   # Constructed knowledge graphs
│   ├── chunks/                   # Text chunk information
│   └── logs/                     # Runtime logs
│
├── 📁 retriever/                 # Retrieval Cache
│
├── kt_rag.py                     # 🎯 Main program entry
├── requirements.txt              # Dependencies list
└── README.md                     # Project documentation
```

### 🔧 Key Configuration Points

| Configuration Category | Key Parameters | Description |
|------------------------|----------------|-------------|
| **🔑 API** | `llm_api_key`, `model`, `temperature` | LLM service configuration |
| **🤖 Mode** | `triggers.mode` | agent(intelligent)/noagent(basic) |
| **🏗️ Construction** | `construction.max_workers` | Graph construction concurrency |
| **🔍 Retrieval** | `retrieval.top_k_filter`, `recall_paths` | Retrieval parameters |
| **🧠 Agentic CoT** | `retrieval.agent.max_steps` | Iterative retrieval steps |
| **🌳 Community Detection** | `tree_comm.struct_weight` | Weight to control impacts from topology |
| **⚡ Performance** | `embeddings.batch_size` | Batch processing size |

<a id="quickstart"></a>
## 🚀 Quick Start

### 🛠️ Installation & Environment

```bash
# 1. Clone project
git clone <repository-url>
cd youtu-graphrag

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure API key
# Edit config/base_config.yaml and set your API key
```


### 🎯 Basic Usage

```bash
# 1. Run with default configuration
python kt_rag.py --datasets demo

# 2. Specify multiple datasets
python kt_rag.py --datasets hotpot 2wiki musique

# 3. Use custom configuration file
python kt_rag.py --config my_config.yaml --datasets demo

# 4. Runtime parameter override
python kt_rag.py --override '{"retrieval": {"top_k_filter": 50}, "triggers": {"mode": "noagent"}}' --datasets demo
```

### 🔧 Advanced Usage

```bash
# 1. Build knowledge graph only
python kt_rag.py --override '{"triggers": {"constructor_trigger": true, "retrieve_trigger": false}}' --datasets demo

# 2. Execute retrieval only (skip construction)
python kt_rag.py --override '{"triggers": {"constructor_trigger": false, "retrieve_trigger": true}}' --datasets demo

# 3. Performance optimization configuration
python kt_rag.py --override '{"construction": {"max_workers": 64}, "embeddings": {"batch_size": 64}}' --datasets demo
```

<details>
<summary><strong>🎛️ Configuration Parameter Override Examples</strong></summary>

```bash
# Adjust retrieval parameters
python kt_rag.py --override '{
  "retrieval": {
    "top_k_filter": 30,
    "recall_paths": 3,
    "agent": {"max_steps": 8}
  }
}' --datasets hotpot

# Adjust API parameters
python kt_rag.py --override '{
  "api": {
    "temperature": 0.1,
    "max_retries": 10
  }
}' --datasets novel_eng

# Adjust Community Detection parameters
python kt_rag.py --override '{
  "tree_comm": {
    "struct_weight": 0.5,
    "embedding_model": "all-mpnet-base-v2"
  }
}' --datasets 2wiki
```

</details>

## 🧪 Complete Workflow Examples

### 📊 End-to-End Workflow

```bash
# Construction only: Build knowledge graph
python kt_rag.py --override '{"triggers": {"constructor_trigger": true, "retrieve_trigger": false}}' --datasets hotpot 2wiki novel

# Retrieval only: Execute retrieval QA
python kt_rag.py --override '{"triggers": {"constructor_trigger": false, "retrieve_trigger": true}}' --datasets hotpot 2wiki novel

# End-to-end: One-click run (construction + retrieval)
python kt_rag.py --override '{"triggers": {"constructor_trigger": true, "retrieve_trigger": true}}' --datasets hotpot 2wiki novel
```

## 🤝 Contributing

We welcome contributions from the community! Here's how you can help:

### 💻 Code Contribution
1. 🍴 Fork the project
2. 🌿 Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. 💾 Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. 📤 Push to the branch (`git push origin feature/AmazingFeature`)
5. 🔄 Create a Pull Request

### 🔧 Extension Guide
- **🌱 New Seed Schemas**: Add high-quality seed schema and data processing
- **📊 Custom Datasets**: Integrate new datasets with minimal schema intervention
- **🎯 Domain-Specific Applications**: Extend framework for specialized use cases with 'Best Practice'

## 📄 License

This project is licensed under the [MIT License](LICENSE) - see the LICENSE file for details.

## 📞 Contact

**Hanson Dong** - hansonjdong@tencent.com  **Siyu An** - siyuan@tencent.com

---

## 🎉 Citation

```bibtex
@misc{dong2025youtugraphrag,
      title={Youtu-GraphRAG: Vertically Unified Agents for Graph Retrieval-Augmented Complex Reasoning}, 
      author={Junnan Dong and Siyu An and Yifei Yu and Qian-Wen Zhang and Linhao Luo and Xiao Huang and Yunsheng Wu and Di Yin and Xing Sun},
      year={2025},
      eprint={2508.19855},
      archivePrefix={arXiv},
      url={https://arxiv.org/abs/2508.19855}, 
}
```

### ⭐ **Start using Youtu-GraphRAG now and experience the intelligent question answering!** 🚀

<!-- [![GitHub stars](https://img.shields.io/github/stars/youtu-graphrag/youtu-graphrag?style=social)](https://github.com/youtu-graphrag/youtu-graphrag) -->
