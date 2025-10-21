# 对话记录：LLM Clustering Prompt 示例说明

**日期**: 2025-10-21  
**时间**: 06:47:00  
**主题**: LLM Clustering Prompt 完整示例展示

---

## 对话内容

### User:
现在用于llm clustet的prompt是什么样子的，给我举个例子，使用代码中的prompt给我展示一下

### Assistant:
我来帮您找一下代码中用于LLM cluster的prompt。让我先搜索相关的代码。

[执行了多个搜索操作，找到相关文件]

### Assistant:
现在我来为您展示一个实际的LLM Clustering Prompt例子。根据代码，我会创建一个具体的示例：

[创建并展示了示例文件，包含：]

====================================
LLM CLUSTERING PROMPT 示例
====================================

以下是一个实际使用的LLM Clustering Prompt的完整示例：

=====================================
完整Prompt内容：
=====================================

You are a knowledge graph curation assistant performing initial clustering of tail entities.
All listed tail entities share the same head entity and relation.

Head entity: Barack Obama
Relation: worksAt

Candidate tails:
[1] White House
[2] The White House
[3] 1600 Pennsylvania Avenue
[4] University of Chicago
[5] Harvard Law School
[6] United States Government
[7] US Government
[8] Federal Government

TASK: Group these tails into PRELIMINARY CLUSTERS based on semantic similarity.
This is an initial clustering step - your goal is to group tails that MIGHT refer to the same entity.

CLUSTERING PRINCIPLE:
Group tails together if they are:
1. POTENTIALLY COREFERENT: Could refer to the same entity (e.g., 'NYC' and 'New York City')
2. SEMANTICALLY VERY SIMILAR: Very similar concepts that need further examination
3. LEXICALLY RELATED: Different expressions of potentially the same thing

KEEP SEPARATE if tails are:
1. CLEARLY DISTINCT: Obviously different entities (e.g., 'Paris' vs 'London')
2. SEMANTICALLY DIFFERENT: Different concepts (e.g., 'color' vs 'size')
3. UNRELATED: No clear semantic connection

CLUSTERING GUIDELINES:
- Be INCLUSIVE in this initial clustering - it's better to over-cluster than under-cluster
- Subsequent LLM refinement will separate false positives within clusters
- Focus on semantic similarity, not just string matching
- Group by meaning/concept rather than exact wording
- Each tail must appear in exactly ONE cluster

EXAMPLES:
✓ Cluster together: ['New York', 'NYC', 'New York City'] - potential coreference
✓ Cluster together: ['United States', 'USA', 'US', 'America'] - potential coreference
✓ Keep separate: ['Paris', 'London', 'Berlin'] - clearly distinct cities
✓ Keep separate: ['red', 'large', 'heavy'] - different property types

OUTPUT REQUIREMENTS:
1. Every input index must appear in exactly one cluster
2. Each cluster should contain semantically similar tails
3. Provide a brief description for each cluster explaining the grouping rationale

Respond with strict JSON using this schema:
{
  "clusters": [
    {
      "members": [1, 3, 5],
      "description": "Brief explanation of why these tails are clustered together"
    },
    {
      "members": [2],
      "description": "This tail is semantically distinct from others"
    }
  ]
}

=====================================
期望的LLM响应示例：
=====================================

{
  "clusters": [
    {
      "members": [1, 2, 3],
      "description": "Different references to the White House - the official residence and workplace"
    },
    {
      "members": [6, 7, 8],
      "description": "Different variations referring to the US Federal Government"
    },
    {
      "members": [4],
      "description": "University of Chicago - a distinct educational institution"
    },
    {
      "members": [5],
      "description": "Harvard Law School - a distinct educational institution"
    }
  ]
}

[更多示例和说明...]

### Assistant 总结:
我已经为您展示了代码中用于**LLM Clustering**的完整prompt。主要要点如下：

### 📋 Prompt核心信息

1. **定义位置**：`models/constructor/kt_gen.py` 第145-191行的 `DEFAULT_LLM_CLUSTERING_PROMPT`

2. **主要目的**：对共享相同head entity和relation的tail entities进行初步语义聚类

3. **关键特点**：
   - 🎯 **包容性原则**：倾向于over-cluster（宁可多聚，不可少聚）
   - 🔍 **语义优先**：基于语义相似性而非字符串匹配
   - 📊 **结构化输出**：要求返回严格的JSON格式

4. **实际示例**：
   - 示例1：Barack Obama + worksAt → 将"White House", "The White House", "1600 Pennsylvania Avenue"聚为一类
   - 示例2：Amazon + locatedIn → 将"United States", "USA", "US", "America"聚为一类

5. **输出格式**：
   ```json
   {
     "clusters": [
       {
         "members": [索引列表],
         "description": "聚类原因说明"
       }
     ]
   }
   ```

这个prompt是知识图谱构建过程中**语义去重（Semantic Dedup）**的第一步，用于将可能指向同一实体的不同表述初步分组，后续会有更精细的LLM去重步骤来进一步处理。

---

### User:
不是，我的意思是，你将所有的信息组合后的prompt展示一下

### Assistant:
明白了！您想看一个完整填充后的、实际发送给LLM的prompt。让我展示一下：

[展示了完整的prompt文本]

================================================================================
完整的LLM Clustering Prompt示例（实际发送给LLM的内容）
================================================================================

You are a knowledge graph curation assistant performing initial clustering of tail entities.
All listed tail entities share the same head entity and relation.

Head entity: Barack Obama
Relation: worksAt

Candidate tails:
[1] White House
[2] The White House
[3] 1600 Pennsylvania Avenue
[4] University of Chicago
[5] Harvard Law School
[6] United States Government
[7] US Government
[8] Federal Government

TASK: Group these tails into PRELIMINARY CLUSTERS based on semantic similarity.
This is an initial clustering step - your goal is to group tails that MIGHT refer to the same entity.

CLUSTERING PRINCIPLE:
Group tails together if they are:
1. POTENTIALLY COREFERENT: Could refer to the same entity (e.g., 'NYC' and 'New York City')
2. SEMANTICALLY VERY SIMILAR: Very similar concepts that need further examination
3. LEXICALLY RELATED: Different expressions of potentially the same thing

KEEP SEPARATE if tails are:
1. CLEARLY DISTINCT: Obviously different entities (e.g., 'Paris' vs 'London')
2. SEMANTICALLY DIFFERENT: Different concepts (e.g., 'color' vs 'size')
3. UNRELATED: No clear semantic connection

CLUSTERING GUIDELINES:
- Be INCLUSIVE in this initial clustering - it's better to over-cluster than under-cluster
- Subsequent LLM refinement will separate false positives within clusters
- Focus on semantic similarity, not just string matching
- Group by meaning/concept rather than exact wording
- Each tail must appear in exactly ONE cluster

EXAMPLES:
✓ Cluster together: ['New York', 'NYC', 'New York City'] - potential coreference
✓ Cluster together: ['United States', 'USA', 'US', 'America'] - potential coreference
✓ Keep separate: ['Paris', 'London', 'Berlin'] - clearly distinct cities
✓ Keep separate: ['red', 'large', 'heavy'] - different property types

OUTPUT REQUIREMENTS:
1. Every input index must appear in exactly one cluster
2. Each cluster should contain semantically similar tails
3. Provide a brief description for each cluster explaining the grouping rationale

Respond with strict JSON using this schema:
{
  "clusters": [
    {
      "members": [1, 3, 5],
      "description": "Brief explanation of why these tails are clustered together"
    },
    {
      "members": [2],
      "description": "This tail is semantically distinct from others"
    }
  ]
}

================================================================================

[又展示了另一个示例 - Apple Inc. + headquarteredIn]

### Assistant 总结:
完美！以上就是**实际发送给LLM的完整prompt**。

## 总结

这就是代码中实际使用的完整prompt，包含：

1. **系统角色定义**：明确LLM的任务是知识图谱助手
2. **具体上下文**：
   - Head entity（头实体）
   - Relation（关系）  
   - Candidate tails（候选尾实体列表，带编号）
3. **详细指令**：聚类原则、分离原则、指导方针
4. **示例**：给出正面和负面的聚类例子
5. **输出要求**：严格的JSON格式规范

**关键点**：
- 这个prompt是一个完整的文本，直接通过 `self.clustering_llm_client.call_api(prompt)` 发送给LLM
- LLM会返回JSON格式的聚类结果
- 每个候选项必须且只能出现在一个cluster中

这就是您在代码 `models/constructor/kt_gen.py` 第993-997行看到的prompt填充后的完整效果！

---

### User:
我没有看到，你展示在哪里了，

### Assistant:
抱歉！让我创建一个文件来清楚地展示给您：

[创建了文件 `llm_clustering_prompt_complete_example.txt`]

好的！我已经创建了一个文件来展示完整的prompt。文件保存在：

**`llm_clustering_prompt_complete_example.txt`**

这个文件包含了：
1. ✅ 完整的、实际发送给LLM的prompt文本
2. ✅ 所有变量都已填充的完整示例
3. ✅ 代码中如何构建这个prompt的说明

您现在可以在工作区看到这个文件，里面就是代码中使用的、填充了所有信息后的完整LLM Clustering Prompt！

---

### User:
cluster的prompt中没有context的对吧

### Assistant:
对！您说得对，**cluster的prompt中确实没有context**。

[读取并展示了代码]

**完全正确！** Clustering的prompt中**只有3个变量**，没有context：

1. `{head}` - 头实体
2. `{relation}` - 关系
3. `{candidates}` - 候选尾实体列表

这与**semantic dedup的prompt**不同。让我对比一下：

[展示了对比]

## 对比总结：

### 1️⃣ **LLM Clustering Prompt**（没有context）
```python
DEFAULT_LLM_CLUSTERING_PROMPT.format(
    head=...,
    relation=...,
    candidates=...  # 只有这3个变量
)
```

### 2️⃣ **Semantic Dedup Prompt**（有context）
```python
DEFAULT_SEMANTIC_DEDUP_PROMPT = (
    ...
    "Head entity: {head}\n"
    "Relation: {relation}\n\n"
    "Head contexts:\n{head_context}\n\n"  # ← 这里有 head_context！
    "Candidate tails:\n"
    "{candidates}\n\n"
    ...
)
```

### 3️⃣ **Attribute Dedup Prompt**（也有context）
```python
DEFAULT_ATTRIBUTE_DEDUP_PROMPT = (
    ...
    "Head entity: {head}\n"
    "Relation: {relation}\n\n"
    "Head contexts:\n{head_context}\n\n"  # ← 也有 head_context！
    "Candidate attribute values:\n"
    "{candidates}\n\n"
    ...
)
```

## 原因分析：

- **Clustering**：只是初步分组，不需要太多上下文，速度要快
- **Dedup**：需要精确判断是否是同一实体，需要head的上下文信息来辅助判断

您的观察非常准确！👍

---

## 对话总结

本次对话主要讨论了LLM Clustering功能中使用的prompt格式和内容：

1. **主要收获**：
   - 了解了LLM Clustering Prompt的完整结构
   - 明确了Clustering Prompt只包含3个变量（head, relation, candidates），没有context
   - 对比了Clustering Prompt与Semantic Dedup Prompt的区别

2. **关键发现**：
   - Clustering阶段重视速度和初步分组，不需要详细上下文
   - Dedup阶段需要精确判断，因此包含head_context信息
   - 两个阶段有不同的设计目标和实现策略

3. **代码位置**：
   - Clustering Prompt定义：`models/constructor/kt_gen.py` 第145-191行
   - Clustering使用位置：`models/constructor/kt_gen.py` 第993-997行
