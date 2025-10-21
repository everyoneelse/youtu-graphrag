"""
示例：LLM Clustering Prompt 实际样子

展示在实际使用中，clustering prompt 是什么样子的。
"""

DEFAULT_LLM_CLUSTERING_PROMPT = (
    "You are a knowledge graph curation assistant performing initial clustering of tail entities.\n"
    "All listed tail entities share the same head entity and relation.\n\n"
    "Head entity: {head}\n"
    "Relation: {relation}\n\n"
    "Candidate tails:\n"
    "{candidates}\n\n"
    "TASK: Group these tails into PRELIMINARY CLUSTERS based on semantic similarity.\n"
    "This is an initial clustering step - your goal is to group tails that MIGHT refer to the same entity.\n\n"
    "CLUSTERING PRINCIPLE:\n"
    "Group tails together if they are:\n"
    "1. POTENTIALLY COREFERENT: Could refer to the same entity (e.g., 'NYC' and 'New York City')\n"
    "2. SEMANTICALLY VERY SIMILAR: Very similar concepts that need further examination\n"
    "3. LEXICALLY RELATED: Different expressions of potentially the same thing\n\n"
    "KEEP SEPARATE if tails are:\n"
    "1. CLEARLY DISTINCT: Obviously different entities (e.g., 'Paris' vs 'London')\n"
    "2. SEMANTICALLY DIFFERENT: Different concepts (e.g., 'color' vs 'size')\n"
    "3. UNRELATED: No clear semantic connection\n\n"
    "CLUSTERING GUIDELINES:\n"
    "- Be INCLUSIVE in this initial clustering - it's better to over-cluster than under-cluster\n"
    "- Subsequent LLM refinement will separate false positives within clusters\n"
    "- Focus on semantic similarity, not just string matching\n"
    "- Group by meaning/concept rather than exact wording\n"
    "- Each tail must appear in exactly ONE cluster\n\n"
    "EXAMPLES:\n"
    "✓ Cluster together: ['New York', 'NYC', 'New York City'] - potential coreference\n"
    "✓ Cluster together: ['United States', 'USA', 'US', 'America'] - potential coreference\n"
    "✓ Keep separate: ['Paris', 'London', 'Berlin'] - clearly distinct cities\n"
    "✓ Keep separate: ['red', 'large', 'heavy'] - different property types\n\n"
    "OUTPUT REQUIREMENTS:\n"
    "1. Every input index must appear in exactly one cluster\n"
    "2. Each cluster should contain semantically similar tails\n"
    "3. Provide a brief description for each cluster explaining the grouping rationale\n\n"
    "Respond with strict JSON using this schema:\n"
    "{{\n"
    "  \"clusters\": [\n"
    "    {{\n"
    "      \"members\": [1, 3, 5],\n"
    "      \"description\": \"Brief explanation of why these tails are clustered together\"\n"
    "    }},\n"
    "    {{\n"
    "      \"members\": [2],\n"
    "      \"description\": \"This tail is semantically distinct from others\"\n"
    "    }}\n"
    "  ]\n"
    "}}\n"
)

# ============================================================================
# 示例 1: 公司产品去重
# ============================================================================
print("=" * 80)
print("示例 1: 公司产品去重")
print("=" * 80)

head_1 = "Apple Inc."
relation_1 = "has_product"
candidates_1 = """[1] iPhone 15
[2] iPhone 15 Pro
[3] iPhone fifteen
[4] MacBook Pro
[5] MacBook Pro 16-inch
[6] iPad
[7] iPad Pro
[8] Apple Watch
[9] Apple Watch Series 9"""

prompt_1 = DEFAULT_LLM_CLUSTERING_PROMPT.format(
    head=head_1,
    relation=relation_1,
    candidates=candidates_1
)

print("\n【实际发送给LLM的Prompt】:\n")
print(prompt_1)

print("\n" + "=" * 80)
print("【期望的LLM响应】:")
print("=" * 80)
expected_response_1 = """{
  "clusters": [
    {
      "members": [1, 2, 3],
      "description": "iPhone 15 系列产品的不同表述，可能指代相同或相关产品"
    },
    {
      "members": [4, 5],
      "description": "MacBook Pro 系列，可能是不同尺寸的同一产品线"
    },
    {
      "members": [6, 7],
      "description": "iPad 系列产品"
    },
    {
      "members": [8, 9],
      "description": "Apple Watch 系列"
    }
  ]
}"""
print(expected_response_1)


# ============================================================================
# 示例 2: 人物属性去重
# ============================================================================
print("\n\n" + "=" * 80)
print("示例 2: 人物属性去重")
print("=" * 80)

head_2 = "Albert Einstein"
relation_2 = "has_attribute"
candidates_2 = """[1] physicist
[2] theoretical physicist
[3] scientist
[4] German-born
[5] German
[6] Jewish
[7] Nobel Prize winner
[8] Nobel laureate
[9] mathematician
[10] philosopher"""

prompt_2 = DEFAULT_LLM_CLUSTERING_PROMPT.format(
    head=head_2,
    relation=relation_2,
    candidates=candidates_2
)

print("\n【实际发送给LLM的Prompt】:\n")
print(prompt_2)

print("\n" + "=" * 80)
print("【期望的LLM响应】:")
print("=" * 80)
expected_response_2 = """{
  "clusters": [
    {
      "members": [1, 2, 3],
      "description": "职业相关，都是科学家/物理学家的不同表述"
    },
    {
      "members": [4, 5],
      "description": "德国出身的不同表述"
    },
    {
      "members": [6],
      "description": "宗教/种族身份"
    },
    {
      "members": [7, 8],
      "description": "诺贝尔奖获得者的不同表述"
    },
    {
      "members": [9],
      "description": "数学家"
    },
    {
      "members": [10],
      "description": "哲学家"
    }
  ]
}"""
print(expected_response_2)


# ============================================================================
# 示例 3: 地点关系去重
# ============================================================================
print("\n\n" + "=" * 80)
print("示例 3: 地点关系去重")
print("=" * 80)

head_3 = "China"
relation_3 = "has_city"
candidates_3 = """[1] Beijing
[2] Peking
[3] 北京
[4] Shanghai
[5] 上海
[6] Guangzhou
[7] Shenzhen
[8] Hong Kong
[9] Hongkong
[10] HK"""

prompt_3 = DEFAULT_LLM_CLUSTERING_PROMPT.format(
    head=head_3,
    relation=relation_3,
    candidates=candidates_3
)

print("\n【实际发送给LLM的Prompt】:\n")
print(prompt_3)

print("\n" + "=" * 80)
print("【期望的LLM响应】:")
print("=" * 80)
expected_response_3 = """{
  "clusters": [
    {
      "members": [1, 2, 3],
      "description": "北京的不同表述（英文、拼音、中文）"
    },
    {
      "members": [4, 5],
      "description": "上海的中英文表述"
    },
    {
      "members": [6],
      "description": "广州，独立城市"
    },
    {
      "members": [7],
      "description": "深圳，独立城市"
    },
    {
      "members": [8, 9, 10],
      "description": "香港的不同表述（全称和缩写）"
    }
  ]
}"""
print(expected_response_3)


# ============================================================================
# 总结
# ============================================================================
print("\n\n" + "=" * 80)
print("Clustering Prompt 特点总结")
print("=" * 80)
print("""
1. 【目标】: 初步聚类，将可能指代相同实体的tail分组
   - 策略：宁可over-cluster，后续semantic dedup阶段会精细区分

2. 【输入】:
   - Head entity: 头实体
   - Relation: 关系类型
   - Candidate tails: 编号的候选tail列表 [1] ... [2] ...

3. 【输出】:
   - JSON格式的clusters
   - 每个cluster包含：members（索引列表）和 description（聚类理由）

4. 【聚类原则】:
   - ✓ 可能是同一实体的不同表述 → 聚到一起
   - ✓ 语义非常相似 → 聚到一起
   - ✗ 明显不同的实体 → 分开
   - ✗ 语义差异大 → 分开

5. 【后续处理】:
   - 聚类结果会传递给 semantic dedup 阶段
   - Semantic dedup 会在每个cluster内部进行更精细的去重判断
""")

print("\n" + "=" * 80)
print("Prompt长度估算")
print("=" * 80)
print(f"模板基础长度: ~{len(DEFAULT_LLM_CLUSTERING_PROMPT)} 字符")
print(f"示例1总长度: ~{len(prompt_1)} 字符 (~{len(prompt_1)//4} tokens)")
print(f"示例2总长度: ~{len(prompt_2)} 字符 (~{len(prompt_2)//4} tokens)")
print(f"示例3总长度: ~{len(prompt_3)} 字符 (~{len(prompt_3)//4} tokens)")
print("\n注意: 实际token数取决于具体的tokenizer，这里用字符数/4作为粗略估算")
