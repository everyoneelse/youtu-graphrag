# 语言检测集成指南

本文档提供将语言检测功能集成到Youtu-GraphRAG项目的完整方案。

---

## 📋 集成概述

### 集成点

1. **文本分块** (`models/constructor/kt_gen.py`)
   - 检测文本语言
   - 根据语言选择分词策略
   
2. **实体提取** (`models/constructor/kt_gen.py`)
   - 为实体标记语言
   - 支持多语言实体去重
   
3. **关系提取** (`models/constructor/kt_gen.py`)
   - 检测关系描述的语言
   - 跨语言关系链接
   
4. **检索** (`models/retriever/enhanced_kt_retriever.py`)
   - 检测查询语言
   - 语言过滤和匹配
   
5. **社区摘要** (`models/constructor/kt_gen.py`)
   - 检测社区内容的主要语言
   - 支持多语言摘要生成

---

## 🔧 集成步骤

### 步骤1: 安装依赖

```bash
# 更新 requirements.txt
echo "fasttext-wheel>=0.9.2" >> requirements.txt

# 安装
pip install -r requirements.txt

# 下载fastText模型
wget https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin -P models/
# 或使用镜像
export HF_ENDPOINT=https://hf-mirror.com
wget https://hf-mirror.com/facebook/fasttext-language-identification/resolve/main/model.bin -O models/lid.176.bin
```

### 步骤2: 配置文件更新

在 `config/base_config.yaml` 中添加配置：

```yaml
# 语言检测配置
language_detection:
  # 是否启用语言检测
  enabled: true
  
  # 检测器类型: fasttext, lingua, langdetect, langid
  detector_type: fasttext
  
  # fastText模型路径
  model_path: models/lid.176.bin
  
  # 是否启用自动fallback
  fallback: true
  
  # 置信度阈值 (低于此值会尝试fallback)
  confidence_threshold: 0.8
  
  # 支持的语言列表 (用于过滤和验证)
  supported_languages:
    - en  # 英语
    - zh  # 中文
    - ja  # 日语
    - ko  # 韩语
    - fr  # 法语
    - de  # 德语
    - es  # 西班牙语
    - ru  # 俄语
    - ar  # 阿拉伯语
    - pt  # 葡萄牙语
  
  # 是否在实体/关系中保存语言信息
  save_language_info: true
  
  # 是否根据语言分别索引
  language_aware_indexing: true
```

### 步骤3: 更新配置加载器

更新 `config/config_loader.py`：

```python
def get_language_detection_config():
    """获取语言检测配置"""
    config = load_config()
    return config.get('language_detection', {
        'enabled': True,
        'detector_type': 'fasttext',
        'model_path': 'models/lid.176.bin',
        'fallback': True,
        'confidence_threshold': 0.8,
        'supported_languages': ['en', 'zh', 'ja', 'ko'],
        'save_language_info': True,
        'language_aware_indexing': False
    })
```

### 步骤4: 集成到KTBuilder

修改 `models/constructor/kt_gen.py`：

```python
from utils.language_detector import LanguageDetector, DetectorType, get_global_detector
from config.config_loader import get_language_detection_config

class KTBuilder:
    def __init__(self, ...):
        # ... 现有初始化代码 ...
        
        # 初始化语言检测器
        self.lang_config = get_language_detection_config()
        if self.lang_config.get('enabled', False):
            self.lang_detector = self._init_language_detector()
            logger.info("✓ 语言检测器已启用")
        else:
            self.lang_detector = None
            logger.info("语言检测器未启用")
    
    def _init_language_detector(self):
        """初始化语言检测器"""
        try:
            detector_type_str = self.lang_config.get('detector_type', 'fasttext')
            detector_type = DetectorType(detector_type_str)
            
            detector = LanguageDetector(
                detector_type=detector_type,
                fallback=self.lang_config.get('fallback', True),
                fasttext_model_path=self.lang_config.get('model_path')
            )
            return detector
        except Exception as e:
            logger.warning(f"语言检测器初始化失败: {e}, 将禁用语言检测功能")
            return None
    
    def _detect_language(self, text: str) -> tuple:
        """检测文本语言"""
        if not self.lang_detector:
            return ('unknown', 0.0)
        
        try:
            lang, conf = self.lang_detector.detect(text)
            
            # 验证是否在支持的语言列表中
            supported = self.lang_config.get('supported_languages', [])
            if supported and lang not in supported:
                logger.debug(f"检测到不支持的语言: {lang}, 将标记为unknown")
                return ('unknown', conf)
            
            return (lang, conf)
        except Exception as e:
            logger.error(f"语言检测失败: {e}")
            return ('unknown', 0.0)
    
    # 在文本分块时检测语言
    def chunk_text(self, text: str):
        """文本分块 - 集成语言检测"""
        
        # 检测文本语言
        doc_lang, lang_conf = self._detect_language(text)
        logger.info(f"文档语言: {doc_lang} (置信度: {lang_conf:.2f})")
        
        # 根据语言选择分词策略
        if doc_lang in ['zh', 'ja']:
            # 中日文使用字符级或专用分词
            chunks = self._chunk_cjk(text, lang=doc_lang)
        elif doc_lang in ['ko']:
            # 韩文处理
            chunks = self._chunk_korean(text)
        else:
            # 其他语言使用空格分词
            chunks = self._chunk_latin(text, lang=doc_lang)
        
        # 为每个chunk添加语言信息
        for chunk in chunks:
            chunk['language'] = doc_lang
            chunk['language_confidence'] = lang_conf
        
        return chunks
    
    # 在实体提取时标记语言
    def extract_entities(self, text: str):
        """实体提取 - 集成语言检测"""
        
        # 检测文本语言
        text_lang, _ = self._detect_language(text)
        
        # 调用LLM提取实体
        entities = self._extract_entities_llm(text)
        
        # 为每个实体标记语言
        if self.lang_config.get('save_language_info', True):
            for entity in entities:
                # 检测实体本身的语言
                entity_lang, entity_conf = self._detect_language(entity['name'])
                entity['language'] = entity_lang
                entity['language_confidence'] = entity_conf
                entity['context_language'] = text_lang
        
        return entities
    
    # 在关系提取时标记语言
    def extract_relations(self, text: str):
        """关系提取 - 集成语言检测"""
        
        text_lang, _ = self._detect_language(text)
        
        relations = self._extract_relations_llm(text)
        
        if self.lang_config.get('save_language_info', True):
            for relation in relations:
                # 检测关系描述的语言
                rel_lang, rel_conf = self._detect_language(relation.get('description', ''))
                relation['language'] = rel_lang
                relation['context_language'] = text_lang
        
        return relations
    
    # 社区摘要生成时考虑语言
    def generate_community_summary(self, community_nodes, community_edges):
        """社区摘要 - 考虑语言"""
        
        # 统计社区中的语言分布
        lang_counter = {}
        for node in community_nodes:
            lang = node.get('language', 'unknown')
            lang_counter[lang] = lang_counter.get(lang, 0) + 1
        
        # 确定主要语言
        main_lang = max(lang_counter.items(), key=lambda x: x[1])[0] if lang_counter else 'en'
        logger.info(f"社区主要语言: {main_lang}")
        
        # 根据主要语言生成摘要
        if main_lang == 'zh':
            summary = self._generate_summary_chinese(community_nodes, community_edges)
        elif main_lang == 'ja':
            summary = self._generate_summary_japanese(community_nodes, community_edges)
        else:
            summary = self._generate_summary_english(community_nodes, community_edges)
        
        return {
            'summary': summary,
            'language': main_lang,
            'language_distribution': lang_counter
        }
```

### 步骤5: 集成到检索器

修改 `models/retriever/enhanced_kt_retriever.py`：

```python
from utils.language_detector import get_global_detector
from config.config_loader import get_language_detection_config

class KTRetriever:
    def __init__(self, ...):
        # ... 现有初始化代码 ...
        
        # 初始化语言检测器
        self.lang_config = get_language_detection_config()
        if self.lang_config.get('enabled', False):
            self.lang_detector = get_global_detector()
        else:
            self.lang_detector = None
    
    def retrieve(self, query: str, top_k: int = 10):
        """检索 - 考虑查询语言"""
        
        # 检测查询语言
        query_lang = 'unknown'
        if self.lang_detector:
            query_lang, query_conf = self.lang_detector.detect(query)
            logger.info(f"查询语言: {query_lang} (置信度: {query_conf:.2f})")
        
        # 执行检索
        results = self._retrieve_core(query, top_k)
        
        # 如果启用语言感知索引，进行语言过滤
        if self.lang_config.get('language_aware_indexing', False):
            results = self._filter_by_language(results, query_lang)
        
        return results
    
    def _filter_by_language(self, results, query_lang):
        """根据语言过滤结果"""
        if query_lang == 'unknown':
            return results
        
        # 优先返回同语言的结果
        same_lang_results = [r for r in results if r.get('language') == query_lang]
        other_results = [r for r in results if r.get('language') != query_lang]
        
        # 同语言结果排在前面
        return same_lang_results + other_results
```

---

## 📊 使用示例

### 示例1: 构建多语言知识图谱

```python
from models.constructor.kt_gen import KTBuilder

# 初始化构建器
builder = KTBuilder(
    llm_config=llm_config,
    schema_path="schemas/your_schema.yaml"
)

# 构建多语言文档
documents = [
    {"text": "Einstein developed the theory of relativity...", "id": "doc1"},
    {"text": "爱因斯坦提出了相对论...", "id": "doc2"},
    {"text": "アインシュタインは相対性理論を発展させた...", "id": "doc3"},
]

# 自动检测语言并构建图谱
graph = builder.build_graph(documents)

# 查看语言分布
print("语言分布:", graph.language_stats)
```

### 示例2: 多语言检索

```python
from models.retriever.enhanced_kt_retriever import KTRetriever

retriever = KTRetriever(graph_path="output/graphs/my_graph.json")

# 中文查询
results_zh = retriever.retrieve("相对论是什么?")

# 英文查询
results_en = retriever.retrieve("What is relativity?")

# 查看结果语言
for r in results_zh:
    print(f"结果: {r['text'][:50]}, 语言: {r.get('language', 'unknown')}")
```

---

## 🎯 高级功能

### 功能1: 跨语言实体链接

```python
def link_cross_language_entities(self, entities):
    """链接跨语言的相同实体"""
    
    # 按语言分组
    entities_by_lang = {}
    for entity in entities:
        lang = entity.get('language', 'unknown')
        if lang not in entities_by_lang:
            entities_by_lang[lang] = []
        entities_by_lang[lang].append(entity)
    
    # 使用embedding进行跨语言匹配
    cross_lang_links = []
    for lang1, entities1 in entities_by_lang.items():
        for lang2, entities2 in entities_by_lang.items():
            if lang1 >= lang2:
                continue
            
            # 计算相似度
            links = self._find_similar_entities(entities1, entities2)
            cross_lang_links.extend(links)
    
    return cross_lang_links
```

### 功能2: 语言感知的查询扩展

```python
def expand_query_multilingual(self, query: str):
    """多语言查询扩展"""
    
    query_lang, _ = self.lang_detector.detect(query)
    
    expanded_queries = [query]
    
    # 如果是英文查询，考虑添加中文翻译
    if query_lang == 'en':
        # 调用翻译API或使用预定义词典
        zh_query = self.translate(query, target_lang='zh')
        expanded_queries.append(zh_query)
    
    # 如果是中文查询，考虑添加英文翻译
    elif query_lang == 'zh':
        en_query = self.translate(query, target_lang='en')
        expanded_queries.append(en_query)
    
    return expanded_queries
```

### 功能3: 语言统计和分析

```python
def analyze_graph_languages(self, graph):
    """分析图谱的语言统计信息"""
    
    stats = {
        'entities': {},
        'relations': {},
        'communities': {},
        'overall': {}
    }
    
    # 统计实体语言
    for entity in graph.entities:
        lang = entity.get('language', 'unknown')
        stats['entities'][lang] = stats['entities'].get(lang, 0) + 1
    
    # 统计关系语言
    for relation in graph.relations:
        lang = relation.get('language', 'unknown')
        stats['relations'][lang] = stats['relations'].get(lang, 0) + 1
    
    # 统计社区主要语言
    for community in graph.communities:
        lang = community.get('language', 'unknown')
        stats['communities'][lang] = stats['communities'].get(lang, 0) + 1
    
    # 整体统计
    all_langs = list(stats['entities'].keys()) + list(stats['relations'].keys())
    from collections import Counter
    stats['overall'] = dict(Counter(all_langs))
    
    return stats
```

---

## 🔍 调试和监控

### 1. 日志记录

```python
import logging

logger = logging.getLogger(__name__)

# 在关键位置添加日志
def process_text(self, text):
    lang, conf = self._detect_language(text)
    logger.info(f"处理文本 - 语言: {lang}, 置信度: {conf:.2f}, 长度: {len(text)}")
    
    if conf < 0.5:
        logger.warning(f"低置信度语言检测: {lang} ({conf:.2f})")
```

### 2. 性能监控

```python
import time

def monitor_language_detection(func):
    """装饰器: 监控语言检测性能"""
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        
        if elapsed > 0.1:  # 超过100ms
            logger.warning(f"语言检测耗时过长: {elapsed*1000:.2f}ms")
        
        return result
    return wrapper
```

### 3. 准确率监控

```python
def validate_language_detection(self, sample_size=100):
    """验证语言检测准确率"""
    
    # 从图谱中随机抽样
    samples = random.sample(self.graph.entities, sample_size)
    
    correct = 0
    for entity in samples:
        # 重新检测语言
        detected_lang, _ = self._detect_language(entity['name'])
        stored_lang = entity.get('language', 'unknown')
        
        if detected_lang == stored_lang:
            correct += 1
    
    accuracy = correct / sample_size
    logger.info(f"语言检测准确率: {accuracy*100:.2f}%")
    
    return accuracy
```

---

## 📝 最佳实践

### 1. 性能优化

```python
# ✅ 好: 使用全局单例
detector = get_global_detector()

# ❌ 差: 每次都创建新实例
detector = LanguageDetector()  # 会重新加载模型
```

### 2. 批量处理

```python
# ✅ 好: 批量检测
texts = [entity['name'] for entity in entities]
results = detector.detect_batch(texts)

# ❌ 差: 逐个检测
for entity in entities:
    lang, conf = detector.detect(entity['name'])
```

### 3. 错误处理

```python
# ✅ 好: 有容错机制
try:
    lang, conf = detector.detect(text)
    if conf < threshold:
        lang = 'unknown'
except Exception as e:
    logger.error(f"语言检测失败: {e}")
    lang, conf = 'unknown', 0.0

# ❌ 差: 没有错误处理
lang, conf = detector.detect(text)  # 可能抛出异常
```

### 4. 缓存结果

```python
# ✅ 好: 缓存重复检测
from functools import lru_cache

@lru_cache(maxsize=1000)
def detect_language_cached(text):
    return detector.detect(text)
```

---

## 🧪 测试

### 单元测试

创建 `tests/test_language_detection_integration.py`:

```python
import unittest
from models.constructor.kt_gen import KTBuilder

class TestLanguageDetectionIntegration(unittest.TestCase):
    
    def setUp(self):
        self.builder = KTBuilder(...)
    
    def test_detect_chinese(self):
        text = "这是中文文本"
        lang, conf = self.builder._detect_language(text)
        self.assertEqual(lang, 'zh')
        self.assertGreater(conf, 0.8)
    
    def test_detect_english(self):
        text = "This is English text"
        lang, conf = self.builder._detect_language(text)
        self.assertEqual(lang, 'en')
        self.assertGreater(conf, 0.8)
    
    def test_entity_language_tagging(self):
        text = "Einstein was a physicist"
        entities = self.builder.extract_entities(text)
        for entity in entities:
            self.assertIn('language', entity)
            self.assertIn('language_confidence', entity)

if __name__ == '__main__':
    unittest.main()
```

---

## 📦 部署清单

- [ ] 安装fasttext-wheel依赖
- [ ] 下载lid.176.bin模型文件
- [ ] 更新config/base_config.yaml配置
- [ ] 集成language_detector到KTBuilder
- [ ] 集成language_detector到KTRetriever
- [ ] 添加语言检测日志
- [ ] 运行基准测试验证准确率
- [ ] 运行集成测试
- [ ] 更新文档
- [ ] 部署到生产环境

---

## 🎉 预期收益

1. **多语言支持**: 自动识别和处理176种语言
2. **更好的分词**: 根据语言选择最佳分词策略
3. **语言感知检索**: 提高跨语言查询的准确性
4. **实体链接**: 支持跨语言实体对齐
5. **统计分析**: 了解知识图谱的语言分布

---

## 📞 支持

如有问题，请参考：
- [语言检测对比文档](LANGUAGE_DETECTION_COMPARISON.md)
- [快速开始指南](LANGUAGE_DETECTION_QUICKSTART.md)
- [示例代码](example_language_detection.py)
