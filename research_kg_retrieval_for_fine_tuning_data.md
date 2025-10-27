# 知识图谱检索生成微调数据的框架调研

**调研日期**: 2025-10-27  
**调研主题**: 区分合成微调数据与基于知识图谱检索生成微调数据的方法

---

## 📋 目录

1. [概述](#概述)
2. [合成微调数据方法](#合成微调数据方法)
3. [基于知识图谱检索生成微调数据方法](#基于知识图谱检索生成微调数据方法)
4. [对比分析](#对比分析)
5. [应用场景](#应用场景)
6. [总结与建议](#总结与建议)

---

## 概述

微调数据生成是大语言模型(LLM)训练的关键环节。当前主要有两大类方法:

- **合成微调数据(Synthetic Fine-tuning Data)**: 完全由LLM生成,不依赖外部知识源
- **基于知识图谱检索生成微调数据(KG-Retrieval-based Data Generation)**: 利用知识图谱的结构化知识,通过检索增强生成

---

## 合成微调数据方法

### 1. **Self-Instruct** (Stanford, 2023)

**类型**: ✅ 纯合成数据

**核心思想**:
- 使用少量人工标注的种子指令
- LLM自我生成新的指令和响应
- 迭代扩展训练数据集

**方法流程**:
```
种子指令 → LLM生成新指令 → LLM生成响应 → 质量过滤 → 训练数据
```

**特点**:
- ❌ 不使用外部知识源
- ✅ 完全依赖LLM的内部知识
- ⚠️ 可能存在幻觉和知识偏差

**论文**: [Self-Instruct: Aligning Language Model with Self Generated Instructions](https://arxiv.org/abs/2212.10560)

---

### 2. **Alpaca** (Stanford, 2023)

**类型**: ✅ 纯合成数据

**核心思想**:
- 基于Self-Instruct方法
- 使用GPT-3.5-turbo生成52K指令遵循数据
- 用于微调LLaMA模型

**方法流程**:
```
175个人工种子任务 → GPT-3.5生成52K指令-响应对 → 微调LLaMA
```

**特点**:
- ❌ 不涉及知识图谱或检索
- ✅ 纯LLM生成的合成数据
- 💰 成本低(约$500)

**GitHub**: [tatsu-lab/stanford_alpaca](https://github.com/tatsu-lab/stanford_alpaca)

---

### 3. **Evol-Instruct** (WizardLM, 2023)

**类型**: ✅ 纯合成数据

**核心思想**:
- 通过"进化"方法逐步增加指令复杂度
- 深度进化(增加约束)和广度进化(增加技能)
- 生成更复杂、多样化的训练数据

**方法流程**:
```
简单指令 → 深度进化(添加约束) → 广度进化(扩展场景) → 复杂指令数据
```

**特点**:
- ❌ 不使用外部知识库
- ✅ 通过指令演化增加复杂性
- 📈 提升模型复杂推理能力

**论文**: [WizardLM: Empowering Large Language Models to Follow Complex Instructions](https://arxiv.org/abs/2304.12244)

---

### 4. **UltraChat** (Tsinghua, 2023)

**类型**: ✅ 纯合成数据

**核心思想**:
- 大规模多轮对话合成
- 涵盖问答、写作、推理等多种任务
- 生成1.5M高质量对话数据

**方法流程**:
```
主题种子 → 多轮对话生成(两个LLM角色扮演) → 质量过滤 → 对话数据
```

**特点**:
- ❌ 不依赖知识图谱
- ✅ 大规模对话数据生成
- 🎭 双LLM角色扮演机制

**论文**: [UltraChat: A Large-scale Auto-generated Multi-round Dialogue Data](https://arxiv.org/abs/2305.14233)

---

### 5. **GLAN** (Generalized Instruction Tuning, 2024)

**类型**: ✅ 纯合成数据

**核心思想**:
- 从学科分类系统构建指令分类法
- 系统化生成覆盖各领域的指令
- 提升模型泛化能力

**方法流程**:
```
学科分类体系 → 生成各学科指令模板 → LLM填充具体内容 → 多学科指令数据
```

**特点**:
- ❌ 不使用知识图谱检索
- ✅ 基于分类学的系统化生成
- 🌍 覆盖广泛领域

**论文**: [GLAN: Generalized Instruction Tuning](https://arxiv.org/abs/2402.13064)

---

## 基于知识图谱检索生成微调数据方法

> ⚠️ **重要区分**: 
> - **检索框架** (如GraphRAG, Youtu-GraphRAG): 主要用途是在推理时增强LLM回答
> - **微调数据生成**: 使用检索框架生成训练数据，这是**二次应用**
> 
> 本节重点关注：哪些方法**专门设计用于生成微调数据**，以及哪些检索框架**可以被用来**生成微调数据

---

### 🔍 检索框架 vs 数据生成：概念澄清

#### GraphRAG的实际定位

**GraphRAG (Microsoft, 2024)** 

**❗ 正确理解**: GraphRAG是一个**检索增强生成框架**，不是专门的微调数据生成工具

**主要用途**:
1. ✅ **推理时检索**: 在用户提问时，从知识图谱检索相关信息
2. ✅ **增强回答质量**: 将检索到的结构化知识融入LLM生成
3. ✅ **支持复杂推理**: 通过图结构支持多跳推理

**核心流程**:
```
用户问题 → KG检索(实体/关系/社区) → 组织上下文 → LLM生成答案
```

**能否用于生成微调数据？**
- 🤔 理论上可以: 可以收集(问题, 检索上下文, 答案)三元组作为训练数据
- ⚠️ 但这不是其主要设计目的
- 📊 需要额外的数据采集和标注流程

**论文**: [From Local to Global: A Graph RAG Approach](https://arxiv.org/abs/2404.16130)

---

### 🎯 真正用于生成微调数据的方法

---

### 1. **KGQA数据集生成方法** (多个工作)

**类型**: ⭐ 专门用于生成微调数据

**核心思想**:
- 从知识图谱采样子图
- 基于图结构生成问题模板
- 自动生成大规模结构化推理数据

**方法流程**:
```
KG子图采样 → 路径/模式识别 → 问题模板化 → 自然语言化 → (问题,答案,推理路径)数据对
```

**典型方法和数据集**:

**a) MetaQA (2017)**
- 基于知识图谱的多跳问题生成
- 1跳、2跳、3跳问题自动生成
- 用于训练多跳推理模型

**b) GrailQA (2020)**
- 从Freebase大规模生成复杂KGQA数据
- 包含64K问题
- 涵盖多种推理模式

**c) WebQSP**
- 从Freebase生成Web风格问题
- 自然语言问题 + SPARQL查询对
- 用于训练语义解析模型

**特点**:
- ✅ 专门设计用于生成训练数据
- ✅ 完全基于KG结构
- ✅ 可控的推理链和难度
- ✅ 大规模自动化生成

---

### 2. **KG-to-Text数据生成** (Triple-to-Text)

**类型**: ⭐ 专门用于生成微调数据

**核心思想**:
- 从知识图谱提取三元组
- 将三元组转换为自然语言描述
- 生成(结构化数据 → 文本)的训练对

**方法流程**:
```
KG三元组采样 → 选择模板/生成策略 → 自然语言化 → (三元组, 文本描述)训练对
```

**典型数据集**:

**a) WebNLG (2017)**
- RDF三元组 → 自然语言文本
- 多领域(人物、建筑、天文等)
- 包含47K数据对

**b) DART (2021)**
- 数据表格 + 知识图谱 → 文本
- 开放领域数据到文本生成
- 82K训练样例

**c) GenWiki**
- Wikipedia + Wikidata
- 生成基于事实的文本描述
- 大规模自动化生成

**特点**:
- ✅ 专门用于训练数据生成任务
- ✅ 保证事实一致性
- ✅ 可控生成(基于结构约束)
- 📝 训练KG-to-Text模型

---

### 3. **QA-GNN数据增强方法** (2021)

**类型**: ⭐ 专门用于生成微调数据

**核心思想**:
- 将问题映射到知识图谱
- 提取相关子图作为结构化上下文
- 生成带有推理路径的训练数据

**方法流程**:
```
问题 → 实体识别 → KG子图提取 → GNN编码 → (问题, 子图, 答案, 推理路径)
```

**特点**:
- ✅ 显式推理路径标注
- ✅ 结合GNN和语言模型
- 📊 CommonsenseQA等任务效果好

**论文**: QA-GNN: Reasoning with Language Models and Knowledge Graphs

---

### 📊 可以用于数据生成的检索框架

> 以下框架**主要是检索系统**，但**可以被用于**收集和生成微调数据

---

### A. **Youtu-GraphRAG** (当前项目, 2025)

**主要定位**: ⭐ 检索增强生成框架

**核心能力**:
- Schema引导的四层知识树构建
- Agent化迭代检索(IRCoT)
- 结构-语义双重感知

**如何用于生成微调数据？**

**方案1: 收集推理轨迹**
```python
# 运行agent模式收集数据
问题 → IRCoT迭代检索 → 记录每步推理 → 生成训练数据
训练数据格式: (问题, [推理步骤1, 步骤2, ...], 最终答案)
```

**方案2: 生成多跳QA对**
```python
# 基于知识图谱生成问题
从KG采样路径 → 设计问题 → 用Youtu-GraphRAG检索验证 → QA对
训练数据格式: (问题, 检索到的三元组, 答案)
```

**方案3: 领域知识迁移**
```python
# 新领域文档 → 构建KG → 生成领域QA
领域文档 → 四层知识树 → 基于Schema生成问题 → 答案生成 → 领域微调数据
```

**优势**:
- ✅ 四层架构提供丰富的知识组织
- ✅ IRCoT提供推理过程标注
- ✅ Schema可控性强
- 🚀 适合生成复杂推理训练数据

---

### B. **Think-on-Graph (ToG, 2023)**

**主要定位**: 检索推理框架

**如何用于数据生成**:
- 在KG上beam search探索多条推理路径
- 记录推理树和路径
- 生成(问题, 推理树, 答案)训练数据

**适用场景**: 生成带有推理树标注的训练数据

---

### C. **StructGPT (2023)**

**主要定位**: 结构化数据访问框架

**如何用于数据生成**:
- 收集LLM生成的SPARQL/SQL查询
- 记录查询执行结果
- 生成(自然语言问题, 结构化查询, 结果)三元组

**适用场景**: 生成代码推理和语义解析训练数据

---

### D. **CRAG (Corrective RAG, 2024)**

**主要定位**: 检索增强框架(混合)

**如何用于数据生成**:
- 自我评估检索质量
- 收集(问题, 检索结果, 质量评分, 校正后答案)
- 生成自我校正训练数据

**适用场景**: 训练具有自我校正能力的模型

---

## 🔥 最新趋势: LLM自我反思生成KG增强数据

### 4. **Self-RAG (2023)**

**类型**: ⭐ 结合检索的自我反思数据生成

**核心思想**:
- LLM在生成过程中自我评估是否需要检索
- 从KG/文档检索后再生成
- 收集(问题, 检索决策, 检索内容, 反思token, 答案)

**特点**:
- ✅ 自适应检索决策
- 🔄 生成-检索-反思循环
- 📊 可生成带反思标注的训练数据

**论文**: Self-RAG: Learning to Retrieve, Generate and Critique

---

### 5. **FLARE (2023)**

**类型**: ⭐ 前瞻性检索数据生成

**核心思想**:
- 生成过程中预测未来需要的知识
- 主动从KG检索
- 生成训练数据包含预测性检索标注

**特点**:
- ✅ 前瞻性检索
- 🎯 主动知识获取
- 📈 适合长文本生成任务

---

## 对比分析

### ⭐ 核心区别总结

#### 1. **纯合成 vs KG检索方法的本质区别**

| 维度 | 纯合成数据 | KG检索生成数据 | 检索框架(可用于数据生成) |
|-----|-----------|---------------|---------------------|
| **主要目的** | 生成训练数据 | 生成训练数据 | 推理时检索(可二次用于数据生成) |
| **知识来源** | LLM内部参数 | 外部知识图谱 | 外部知识图谱 |
| **结构化程度** | 无 | 高(三元组/图结构) | 高(三元组/图结构) |
| **事实准确性** | 中低(可能幻觉) | 高 | 高 |
| **生成成本** | 低(仅LLM调用) | 中高(KG构建+生成) | 高(需要额外数据收集) |
| **可控性** | 低 | 高 | 高 |
| **推理能力** | 泛化推理 | 结构化推理 | 结构化推理 |

---

### 方法分类总结

| 方法类型 | 代表方法 | 知识来源 | 主要用途 | 优势 | 局限 |
|---------|---------|---------|---------|------|------|
| **纯合成数据** | Self-Instruct<br>Alpaca<br>Evol-Instruct | LLM内部知识 | 通用指令遵循 | ✅ 成本低<br>✅ 快速生成<br>✅ 灵活多样 | ❌ 可能幻觉<br>❌ 知识过时<br>❌ 缺乏结构约束 |
| **专门数据生成** | KGQA数据集<br>WebNLG<br>QA-GNN | 外部知识图谱 | 专门生成训练数据 | ✅ 事实准确<br>✅ 结构化推理<br>✅ 大规模自动化 | ❌ 需要KG<br>❌ 领域依赖<br>❌ 构建成本 |
| **检索框架** | GraphRAG<br>Youtu-GraphRAG<br>ToG | 外部知识图谱 | 推理时检索 | ✅ 高质量检索<br>✅ 可用于收集数据<br>✅ 推理路径清晰 | ⚠️ 需二次开发<br>⚠️ 数据收集复杂 |
| **混合方法** | Self-RAG<br>CRAG<br>FLARE | KG + 文档 + LLM | 自适应检索生成 | ✅ 互补优势<br>✅ 鲁棒性强<br>✅ 质量高 | ⚠️ 系统复杂<br>⚠️ 计算开销大 |

---

### 2. **关键洞察**

#### 📌 GraphRAG等是检索框架,不是数据生成工具

**重要澄清**:
- **GraphRAG, Youtu-GraphRAG, ToG** 等的主要设计目的是**推理时检索**
- 它们在用户提问时动态检索知识来增强回答
- **可以被用于**生成微调数据,但需要额外的数据收集和标注流程

**对比**:
```
专门的数据生成方法 (如KGQA, WebNLG):
  └─ 设计目的: 生成训练数据
  └─ 使用方式: 直接运行生成数据
  
检索框架 (如GraphRAG, Youtu-GraphRAG):
  └─ 设计目的: 推理时增强
  └─ 使用方式: 运行系统 → 收集(问题,检索,答案) → 后处理成训练数据
```

#### 📊 如何选择合适的方法

**决策流程**:
1. **明确目标**: 是要生成什么类型的训练数据?
2. **评估资源**: 是否有知识图谱?构建成本?
3. **考虑用途**: 通用能力 vs 知识密集任务

---

## 应用场景与方法推荐

### 场景1: 通用对话能力训练
**推荐方法**: ✅ **纯合成数据方法**
- **推荐**: Self-Instruct / Alpaca / UltraChat
- **优势**: 快速生成大规模对话数据,成本可控
- **适用**: 指令遵循、多轮对话、通用助手

---

### 场景2: 复杂多跳推理训练
**推荐方法**: ⭐ **专门KG数据生成** 或 **检索框架**

**选项A**: 使用专门的KGQA数据生成
- **方法**: MetaQA, GrailQA类型
- **优势**: 自动化大规模生成,推理链可控

**选项B**: 使用Youtu-GraphRAG收集数据
- **方法**: 运行IRCoT模式,收集推理轨迹
- **优势**: 真实推理过程,高质量标注
- **步骤**: 
  1. 构建知识图谱
  2. 运行agent模式回答问题
  3. 记录(问题, 推理步骤, 三元组, 答案)
  4. 后处理成训练数据

---

### 场景3: 领域知识问答微调
**推荐方法**: ⭐ **KG数据生成方法**

**方案1**: KGQA数据集生成
- 从领域KG采样子图
- 生成领域特定问题
- 确保事实准确性

**方案2**: 使用Youtu-GraphRAG
- 领域文档 → 构建知识树
- 基于Schema生成问题
- 通过检索验证答案质量

---

### 场景4: 代码推理能力训练
**推荐方法**: ⭐ **StructGPT类型**
- API/数据库结构作为KG
- 生成SPARQL/SQL查询
- 训练程序式推理能力

---

### 场景5: 创意写作能力训练
**推荐方法**: ✅ **纯合成数据方法**
- **推荐**: Evol-Instruct / UltraChat
- **优势**: 多样性和创造性优先
- **适用**: 不严格要求事实性的任务

---

### 场景6: 事实核查能力训练
**推荐方法**: ⭐ **KG数据生成方法**
- 从KG生成正确/错误陈述对
- 标注支持证据
- 训练事实验证模型

---

### 场景7: 长文档理解训练
**推荐方法**: ⭐ **混合方法** (Self-RAG, FLARE)
- 生成需要多次检索的长文本任务
- 标注检索时机和内容
- 训练主动检索能力

---

## 总结与建议

### 🎯 关键发现

#### 1. **GraphRAG是检索框架,不是专门的数据生成工具**

**重要结论**:
- ✅ **GraphRAG, Youtu-GraphRAG** 的主要用途是**推理时检索增强**
- ⚠️ 它们**可以被用于**生成微调数据,但这是**二次应用**
- 📊 需要额外的数据收集、标注和后处理流程

**正确理解**:
```
Youtu-GraphRAG的主要定位:
  🎯 检索增强生成框架 (主要用途)
    └─ 用户提问 → KG检索 → 增强回答
  
  📊 可以用于数据生成 (二次应用)
    └─ 运行系统 → 收集轨迹 → 后处理 → 训练数据
```

---

#### 2. **合成方法 vs KG检索方法是互补关系**

- **合成方法**: 适合通用能力、对话、创意任务
- **KG专门数据生成**: 适合知识密集、多跳推理、事实问答
- **检索框架**: 可用于收集高质量推理轨迹数据

---

#### 3. **混合方法是当前趋势**

- Self-RAG, CRAG, FLARE等结合检索和生成
- 根据任务动态选择知识源
- 生成更加鲁棒和高质量的训练数据

---

### 💡 对于当前项目(Youtu-GraphRAG)的定位建议

#### 明确双重价值

**价值1: 检索增强生成框架** (主要价值)
> Youtu-GraphRAG是一个先进的**推理时检索框架**,通过四层知识树和IRCoT提升LLM回答质量

**价值2: 可用于生成高质量微调数据** (附加价值)
> 通过运行Youtu-GraphRAG系统,可以收集高质量的推理轨迹,用于生成微调数据

---

### 🚀 如何用Youtu-GraphRAG生成微调数据

#### 方案1: 收集IRCoT推理轨迹

**步骤**:
```python
# 1. 运行agent模式
python main.py --datasets yourdomain --override '{"triggers": {"mode": "agent"}}'

# 2. 修改retrieval()函数,在agent_retrieval中保存数据
def agent_retrieval(graphq, kt_retriever, qa_pairs, schema_path):
    training_data = []
    for qa in qa_pairs:
        # ... IRCoT过程 ...
        training_data.append({
            "question": qa["question"],
            "reasoning_steps": thoughts,  # 推理步骤
            "retrieved_triples": dedup_triples,  # 检索的三元组
            "final_answer": answer,
            "gold_answer": qa["answer"]
        })
    
    # 3. 保存为训练数据
    with open("training_data.json", "w") as f:
        json.dump(training_data, f)

# 4. 训练数据格式
{
  "question": "...",
  "reasoning_steps": ["step1", "step2", ...],
  "retrieved_triples": ["triple1", "triple2", ...],
  "final_answer": "..."
}
```

**适用场景**: 训练具有迭代推理能力的模型

---

#### 方案2: 基于KG自动生成QA对

**步骤**:
```python
# 1. 从构建好的KG采样路径
graph = load_graph("output/graphs/yourdomain_new.json")
sampled_paths = sample_multi_hop_paths(graph, num_paths=1000, hop=2-3)

# 2. 将路径转换为问题模板
for path in sampled_paths:
    # path: [Entity1, Relation1, Entity2, Relation2, Entity3]
    question = generate_question_from_path(path)
    
    # 3. 用Youtu-GraphRAG检索验证
    result = kt_retriever.process_retrieval_results(question)
    
    # 4. 生成答案
    answer = generate_answer(question, result)
    
    training_data.append({
        "question": question,
        "answer": answer,
        "supporting_triples": result['triples'],
        "reasoning_path": path
    })
```

**适用场景**: 大规模生成多跳推理QA数据

---

#### 方案3: 领域迁移数据生成

**步骤**:
```python
# 1. 新领域文档构建KG
python main.py --datasets medical_domain --override '{"triggers": {"constructor_trigger": true}}'

# 2. 基于Schema生成领域问题
schema = load_schema("schemas/medical.json")
domain_questions = generate_questions_from_schema(
    schema=schema,
    entities=graph.entities,
    relations=graph.relations
)

# 3. 用Youtu-GraphRAG生成答案
for question in domain_questions:
    answer = kt_retriever.answer_question(question)
    training_data.append({"question": question, "answer": answer})
```

**适用场景**: 领域特定LLM微调

---

### 🔬 推荐研究方向

#### 方向1: 自动化问题生成
- 基于四层知识树自动生成多样化问题
- 控制问题难度和推理跳数
- 确保问题的自然性和合理性

#### 方向2: 数据质量自动评估
- 开发评估生成数据质量的指标
- 包括: 事实准确性、推理连贯性、答案完整性
- 自动过滤低质量数据

#### 方向3: 推理链标注
- 自动标注推理过程中的关键步骤
- 生成(问题, 推理链, 答案)三元组
- 用于训练可解释的推理模型

#### 方向4: 混合数据生成策略
- 结合合成方法和KG检索方法
- 合成方法生成问题多样性
- KG检索保证事实准确性

---

## 参考文献

### 纯合成数据方法
1. **Self-Instruct**: https://arxiv.org/abs/2212.10560
2. **Alpaca**: https://github.com/tatsu-lab/stanford_alpaca
3. **WizardLM (Evol-Instruct)**: https://arxiv.org/abs/2304.12244
4. **UltraChat**: https://arxiv.org/abs/2305.14233
5. **GLAN**: https://arxiv.org/abs/2402.13064

### 专门的KG数据生成方法
1. **MetaQA**: Miller et al. 2016 - https://arxiv.org/abs/1606.03126
2. **GrailQA**: Gu et al. 2020 - https://arxiv.org/abs/2011.07743
3. **WebQSP**: Yih et al. 2016
4. **WebNLG**: Gardent et al. 2017 - https://webnlg-challenge.loria.fr/
5. **DART**: Nan et al. 2021 - https://arxiv.org/abs/2007.02871
6. **QA-GNN**: Yasunaga et al. 2021 - https://arxiv.org/abs/2104.06378

### 检索增强框架(可用于数据生成)
1. **GraphRAG (Microsoft)**: https://arxiv.org/abs/2404.16130
2. **Youtu-GraphRAG**: https://arxiv.org/abs/2508.19855
3. **StructGPT**: https://arxiv.org/abs/2305.09645
4. **Think-on-Graph (ToG)**: https://arxiv.org/abs/2307.07697

### 混合方法
1. **Self-RAG**: https://arxiv.org/abs/2310.11511
2. **CRAG (Corrective RAG)**: https://arxiv.org/abs/2401.15884
3. **FLARE**: https://arxiv.org/abs/2305.06983

### 相关资源
- **KGQA数据集**: GrailQA, MetaQA, WebQSP, ComplexWebQuestions
- **KG资源**: Wikidata, ConceptNet, Freebase, DBpedia
- **评估基准**: GraphRAG-Bench, HotpotQA, MuSiQue, 2WikiMultiHopQA
- **AnonyRAG**: https://huggingface.co/datasets/Youtu-Graph/AnonyRAG

---

## 附录: 快速决策树

### 需要生成微调数据的决策流程

```
❓ 需要生成微调数据?
│
├─ 📋 Step 1: 确定任务类型
│  │
│  ├─ 通用对话/指令遵循?
│  │   └─ ✅ 使用纯合成方法 (Self-Instruct, Alpaca)
│  │
│  ├─ 知识密集型/多跳推理?
│  │   └─ ⭐ 继续 Step 2
│  │
│  └─ 创意写作/开放任务?
│      └─ ✅ 使用纯合成方法 (Evol-Instruct, UltraChat)
│
├─ 📊 Step 2: 评估KG资源
│  │
│  ├─ 已有知识图谱?
│  │   └─ ⭐ 继续 Step 3
│  │
│  └─ 无知识图谱 → 评估构建成本
│      ├─ 成本可接受 → 构建KG → 继续 Step 3
│      └─ 成本太高 → ✅ 使用纯合成方法
│
├─ 🎯 Step 3: 选择KG方法类型
│  │
│  ├─ 需要大规模自动生成?
│  │   └─ ⭐ 专门数据生成方法
│  │       └─ KGQA (MetaQA, GrailQA)
│  │       └─ KG-to-Text (WebNLG, DART)
│  │
│  ├─ 需要高质量推理轨迹?
│  │   └─ ⭐ 使用检索框架收集数据
│  │       └─ Youtu-GraphRAG (IRCoT轨迹)
│  │       └─ Think-on-Graph (推理树)
│  │
│  └─ 需要代码推理能力?
│      └─ ⭐ StructGPT类型
│          └─ 生成SPARQL/SQL查询数据
│
└─ 🔄 Step 4: 考虑混合策略
   │
   ├─ 需要自适应检索?
   │   └─ ⭐ Self-RAG, CRAG
   │
   └─ 需要长文本生成?
       └─ ⭐ FLARE
```

---

### ⚡ 快速参考表

| 你的需求 | 推荐方法 | 类型 |
|---------|---------|------|
| 通用对话助手 | Alpaca, UltraChat | ✅ 纯合成 |
| 多跳推理 | KGQA数据集 或 Youtu-GraphRAG | ⭐ KG方法 |
| 领域问答 | 构建领域KG + KGQA生成 | ⭐ KG方法 |
| 事实核查 | KG + 正负样本生成 | ⭐ KG方法 |
| 代码推理 | StructGPT类型 | ⭐ KG方法 |
| 创意写作 | Evol-Instruct | ✅ 纯合成 |
| 推理轨迹标注 | Youtu-GraphRAG (IRCoT) | ⭐ 检索框架 |

---

## 🎓 关键术语解释

### GraphRAG
**定义**: 一种检索增强生成框架,在推理时从知识图谱检索相关信息来增强LLM回答  
**主要用途**: 推理时检索增强  
**能否生成数据**: 可以,但需要二次开发

### Youtu-GraphRAG  
**定义**: 基于Schema引导的四层知识树和IRCoT的检索增强框架  
**主要用途**: 推理时检索增强,支持复杂推理  
**能否生成数据**: 可以收集高质量推理轨迹作为训练数据

### KGQA数据集生成
**定义**: 专门从知识图谱自动生成问答数据集的方法  
**主要用途**: 生成训练数据  
**代表**: MetaQA, GrailQA, WebQSP

### 合成数据
**定义**: 完全由LLM生成,不依赖外部知识源的训练数据  
**优势**: 成本低,规模大  
**劣势**: 可能有幻觉,事实准确性无保证

---

**文档创建时间**: 2025-10-27  
**最后更新**: 2025-10-27  
**建议更新频率**: 季度更新(跟踪最新研究进展)  
**维护者**: 基于Youtu-GraphRAG项目的调研

