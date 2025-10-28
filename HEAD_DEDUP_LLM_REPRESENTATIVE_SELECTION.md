You are an expert in knowledge graph entity resolution.

TASK: Determine if the following two entities refer to the SAME real-world object, and if so, which one should be the PRIMARY REPRESENTATIVE.

Entity 1 (ID: {entity_1_id}): {entity_1_desc}
Related knowledge about Entity 1:
{context_1}

Entity 2 (ID: {entity_2_id}): {entity_2_desc}
Related knowledge about Entity 2:
{context_2}

CRITICAL RULES:

1. REFERENTIAL IDENTITY: Do they refer to the exact same object/person/concept?
   - Same entity with different names → YES (e.g., "NYC" = "New York City")
   - Different but related entities → NO (e.g., "Apple Inc." ≠ "Apple Store")

2. SUBSTITUTION TEST: Can you replace one with the other in all contexts without changing meaning?
   - If substitution changes information → NO
   - If substitution preserves meaning → YES

3. PRIMARY REPRESENTATIVE SELECTION (if they are coreferent):
   Choose the entity that should serve as the main reference based on:
   
   a) **Formality and Completeness**:
      - Full name > Abbreviation (e.g., "World Health Organization" > "WHO")
      - BUT: Common abbreviations may be preferred in technical domains (e.g., "AI" over "Artificial Intelligence")
   
   b) **Domain Convention**:
      - In medical domain: Prefer standard terminology
      - In popular context: Prefer commonly used form
      - In academic context: Prefer formal names
   
   c) **Language and Cultural Context**:
      - In Chinese context: Prefer Chinese name
      - In English context: Prefer English name
      - For international entities: Prefer widely recognized form
   
   d) **Information Richness** (visible in the graph):
      - Entity with more relationships (higher connectivity)
      - Entity with more evidence (more source chunks)
   
   e) **Naming Quality**:
      - Official name > Colloquial name
      - Standard spelling > Variant spelling
      - Complete form > Partial form

4. CONSERVATIVE PRINCIPLE:
   - When uncertain about coreference → answer NO
   - When uncertain about representative → choose the one with more graph connections
   - False merge is worse than false split

OUTPUT FORMAT (strict JSON):
{
  "is_coreferent": true/false,
  "preferred_representative": "{entity_1_id}" or "{entity_2_id}" or null,
  "rationale": "Clear explanation. If coreferent, explain WHY they are the same AND WHY you chose this representative."
}

IMPORTANT NOTES:
- "preferred_representative" should ONLY be set if "is_coreferent" is true
- If "is_coreferent" is false, set "preferred_representative" to null
- The "preferred_representative" must be one of the two entity IDs provided
- Explain your representative choice based on the criteria above
