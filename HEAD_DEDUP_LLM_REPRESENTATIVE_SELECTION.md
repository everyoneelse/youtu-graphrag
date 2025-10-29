You are an expert in knowledge graph entity resolution.

TASK: Determine if the following two entities refer to the SAME real-world object, and if so, which one should be the PRIMARY REPRESENTATIVE.

Entity 1 (ID: {entity_1_id}): {entity_1_desc}
Graph relationships:
{graph_context_1}
Source text:
{chunk_context_1}

Entity 2 (ID: {entity_2_id}): {entity_2_desc}
Graph relationships:
{graph_context_2}
Source text:
{chunk_context_2}

CRITICAL RULES:

1. REFERENTIAL IDENTITY: Do they refer to the exact same object/person/concept?
   - Same entity with different names → YES (e.g., "NYC" = "New York City")
   - Different but related entities → NO (e.g., "Apple Inc." ≠ "Apple Store")

2. SUBSTITUTION TEST: Can you replace one with the other in all contexts without changing meaning?
   - If substitution changes information → NO
   - If substitution preserves meaning → YES

3. CONSERVATIVE PRINCIPLE:
   - When in doubt, keep them separate
   - Better to have duplicates than to lose information
   - When uncertain about representative → choose the one with more graph connections

4. CRITICAL: ONLY merge if truly identical (not just similar or related):
   - True identity: Different names/forms for the SAME object
   - Do NOT merge if:
     * Entities describe different concepts (even if related)
     * Entities convey different information or specificity
     * One entity is a type/part/aspect of the other
     * Entities have hierarchical or categorical relationships

## CONTEXT USAGE GUIDANCE (MANDATORY)

The provided context (relationships and source text) is additional information to help you determine coreference. Use it wisely:

1. **Identify contradictions**: If the contexts reveal contradictory information about the two entities, they are DIFFERENT entities → answer NO

2. **Find supporting evidence**: If the contexts show consistent and complementary information, it supports the coreference hypothesis

3. **Assess information sufficiency**: If context is too limited to make a confident decision, apply CONSERVATIVE PRINCIPLE → answer NO

4. **Recognize hierarchical relationships**: If context shows one entity owns/contains/manages the other (e.g., company vs subsidiary, organization vs department), they are DIFFERENT entities → answer NO

**IMPORTANT**: Do NOT verify the context itself - trust it and USE it to make better coreference decisions.

## DECISION PROCEDURE

Follow these steps IN ORDER:

### PHASE 1: USE CONTEXT TO INFORM COREFERENCE DECISION
- Use the provided context (relationships and source text) to identify contradictions or supporting evidence
- If context reveals contradictions or hierarchical relationships → they are DIFFERENT
- If context is insufficient → apply conservative principle

### PHASE 2: COREFERENCE DETERMINATION
- Step 1: Check if names are variations of the same entity (e.g., abbreviations, translations)
- Step 2: Use context to verify relation patterns are consistent (not just similar, but CONSISTENT)
- Step 3: Look for contradictions in context - if ANY key information conflicts → they are DIFFERENT
- Step 4: Apply substitution test - can they be swapped in ALL contexts?
- Step 5: If uncertain → answer NO (conservative principle)

### PHASE 3: REPRESENTATIVE SELECTION (only if coreferent)
Choose PRIMARY REPRESENTATIVE based on:
- a) **Formality and Completeness**: Full name > Abbreviation, BUT domain conventions matter
- b) **Domain Convention**: Medical/Academic prefer standard terms, Popular prefers common forms
- c) **Information Richness**: Entity with MORE relationships (visible in context above)
- d) **Naming Quality**: Official name > Colloquial, Standard spelling > Variant
- e) **Cultural Context**: Consider primary language and widely recognized forms

OUTPUT FORMAT (strict JSON):
{
  "is_coreferent": true/false,
  "preferred_representative": "{entity_1_id}" or "{entity_2_id}" or null,
  "rationale": "MUST include: (1) How you used the context to inform your decision, (2) Coreference decision reasoning, (3) If coreferent, representative selection reasoning"
}

IMPORTANT NOTES:
- "preferred_representative" should ONLY be set if "is_coreferent" is true
- If "is_coreferent" is false, set "preferred_representative" to null
- The "preferred_representative" must be one of the two entity IDs provided
- Always explain how you used the context to inform your decision
- Context helps avoid false merges and improves decision quality

## Examples Demonstrating Context Usage

### Example 1: SHOULD MERGE (context supports with consistent information)
Entity 1 (entity_100): "UN", relations: [founded→1945, member→United States]
Entity 2 (entity_150): "United Nations", relations: [established→1945, member→USA]

Output:
```json
{
  "is_coreferent": true,
  "preferred_representative": "entity_100",
  "rationale": "(Context Usage) Contexts show consistent information: founding year 1945 matches, members align (United States/USA refer to same country). No contradictions found. Contexts support that these are the same entity with different name forms. (Coreference) 'UN' is standard abbreviation of 'United Nations'. (Representative) Choose entity_100 (UN) - widely recognized standard form with more relationships."
}
```

### Example 2: SHOULD NOT MERGE (context reveals contradictions)
Entity 1 (entity_300): "张三", relations: [works_at→清华大学, age→45, position→教授]
Entity 2 (entity_350): "张三", relations: [studies_at→北京大学, age→22, status→学生]

Output:
```json
{
  "is_coreferent": false,
  "preferred_representative": null,
  "rationale": "(Context Usage) Contexts reveal critical contradictions: age differs (45 vs 22), one is professor at Tsinghua while other is student at Peking University. These contradictions indicate different persons with the same name. (Decision) Same name but contradictory context information. Conservative principle applied."
}
```

### Example 3: INSUFFICIENT CONTEXT (conservative principle)
Entity 1 (entity_500): "李明", relations: [age→30]
Entity 2 (entity_550): "李明", relations: [gender→male]

Output:
```json
{
  "is_coreferent": false,
  "preferred_representative": null,
  "rationale": "(Context Usage) Contexts provide very limited information: only generic attributes that many people share. No distinctive information to confidently determine if they are the same person. (Decision) Insufficient context for reliable decision. Conservative principle: answer NO to avoid false merge."
}
```
