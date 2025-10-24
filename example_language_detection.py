"""
语言检测示例脚本
展示如何使用不同的语言检测库
"""

import logging
from utils.language_detector import (
    LanguageDetector, 
    DetectorType, 
    detect_language,
    get_global_detector
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def example_1_quick_detection():
    """示例1: 快速检测单个文本"""
    print("\n" + "=" * 60)
    print("示例1: 快速语言检测")
    print("=" * 60)
    
    texts = [
        "This is a sample English text.",
        "这是一段中文文本。",
        "これは日本語です。",
        "Ceci est du français.",
    ]
    
    for text in texts:
        lang, confidence = detect_language(text)
        print(f"文本: {text}")
        print(f"  → 语言: {lang}, 置信度: {confidence:.4f}\n")


def example_2_batch_detection():
    """示例2: 批量检测"""
    print("\n" + "=" * 60)
    print("示例2: 批量语言检测")
    print("=" * 60)
    
    texts = [
        "Hello world",
        "你好世界",
        "こんにちは世界",
        "안녕하세요 세계",
        "Bonjour le monde",
        "Hola mundo",
        "Привет мир",
    ]
    
    detector = get_global_detector()
    results = detector.detect_batch(texts)
    
    for text, (lang, conf) in zip(texts, results):
        print(f"{text:25s} -> {lang:5s} (置信度: {conf:.4f})")


def example_3_multiple_languages_prob():
    """示例3: 获取多语言概率分布"""
    print("\n" + "=" * 60)
    print("示例3: 多语言概率分布")
    print("=" * 60)
    
    # 混合语言文本
    text = "Hello 你好 world 世界"
    
    detector = get_global_detector()
    results = detector.detect_with_all_probs(text, top_k=5)
    
    print(f"文本: {text}")
    print("可能的语言:")
    for lang, prob in results:
        print(f"  {lang}: {prob:.4f}")


def example_4_different_detectors():
    """示例4: 对比不同检测器"""
    print("\n" + "=" * 60)
    print("示例4: 对比不同检测器性能")
    print("=" * 60)
    
    text = "这是一段中文文本，用于测试不同语言检测算法的准确性和性能。"
    
    detector_types = [
        DetectorType.FASTTEXT,
        DetectorType.LANGDETECT,
        DetectorType.LANGID,
    ]
    
    print(f"测试文本: {text}\n")
    
    for det_type in detector_types:
        try:
            detector = LanguageDetector(detector_type=det_type, fallback=False)
            lang, conf = detector.detect(text)
            print(f"{det_type.value:12s}: {lang:5s} (置信度: {conf:.4f})")
        except Exception as e:
            print(f"{det_type.value:12s}: 失败 - {e}")


def example_5_short_text_detection():
    """示例5: 短文本检测"""
    print("\n" + "=" * 60)
    print("示例5: 短文本语言检测")
    print("=" * 60)
    
    short_texts = [
        "Hi",
        "你好",
        "こんにちは",
        "안녕",
        "Bonjour",
        "Hola",
        "水",
        "cat",
        "猫",
    ]
    
    detector = get_global_detector()
    
    print("短文本检测结果:")
    for text in short_texts:
        lang, conf = detector.detect(text)
        print(f"  '{text}' -> {lang:5s} (置信度: {conf:.4f})")


def example_6_graphrag_integration():
    """示例6: GraphRAG集成场景"""
    print("\n" + "=" * 60)
    print("示例6: GraphRAG实际应用场景")
    print("=" * 60)
    
    # 模拟实体提取场景
    entities = [
        "Albert Einstein",
        "阿尔伯特·爱因斯坦",
        "アルベルト・アインシュタイン",
        "Machine Learning",
        "机器学习",
        "人工智能",
        "Artificial Intelligence",
    ]
    
    # 模拟关系三元组
    relations = [
        "Einstein developed the theory of relativity",
        "爱因斯坦提出了相对论",
        "Machine learning is a subset of AI",
        "机器学习是人工智能的一个分支",
    ]
    
    detector = get_global_detector()
    
    print("实体语言检测:")
    entity_langs = {}
    for entity in entities:
        lang, conf = detector.detect(entity)
        entity_langs[entity] = lang
        print(f"  {entity:35s} -> {lang:5s}")
    
    print("\n关系三元组语言检测:")
    for relation in relations:
        lang, conf = detector.detect(relation)
        print(f"  {relation[:50]:50s} -> {lang:5s}")
    
    # 语言分组统计
    from collections import Counter
    lang_counter = Counter(entity_langs.values())
    
    print("\n语言分布统计:")
    for lang, count in lang_counter.most_common():
        print(f"  {lang}: {count} 个实体")


def example_7_fallback_mechanism():
    """示例7: Fallback机制演示"""
    print("\n" + "=" * 60)
    print("示例7: Fallback机制")
    print("=" * 60)
    
    # 尝试使用不存在的fastText模型，会自动fallback
    detector = LanguageDetector(
        detector_type=DetectorType.FASTTEXT,
        fallback=True,
        fasttext_model_path="nonexistent_model.bin"  # 故意使用不存在的路径
    )
    
    text = "This will use fallback detector"
    lang, conf = detector.detect(text)
    print(f"文本: {text}")
    print(f"检测结果: {lang} (置信度: {conf:.4f})")
    print("注意: 主检测器失败后，自动使用了备用检测器")


def example_8_multilingual_corpus():
    """示例8: 处理多语言语料库"""
    print("\n" + "=" * 60)
    print("示例8: 多语言语料库处理")
    print("=" * 60)
    
    # 模拟一个多语言文档集合
    documents = [
        {"id": 1, "content": "The theory of relativity revolutionized physics."},
        {"id": 2, "content": "相对论彻底改变了物理学。"},
        {"id": 3, "content": "L'intelligence artificielle transforme notre monde."},
        {"id": 4, "content": "機械学習は人工知能の重要な分野です。"},
        {"id": 5, "content": "Neural networks are inspired by biological neurons."},
        {"id": 6, "content": "深度学习在图像识别领域取得了重大突破。"},
    ]
    
    detector = get_global_detector()
    
    # 按语言分组
    language_groups = {}
    
    print("文档语言分类:")
    for doc in documents:
        lang, conf = detector.detect(doc["content"])
        
        if lang not in language_groups:
            language_groups[lang] = []
        
        language_groups[lang].append(doc)
        
        print(f"文档 {doc['id']}: {lang} (置信度: {conf:.4f})")
        print(f"  内容: {doc['content'][:60]}...")
    
    print("\n语言分组结果:")
    for lang, docs in language_groups.items():
        print(f"  {lang}: {len(docs)} 个文档")


def main():
    """运行所有示例"""
    examples = [
        ("快速检测", example_1_quick_detection),
        ("批量检测", example_2_batch_detection),
        ("多语言概率", example_3_multiple_languages_prob),
        ("对比检测器", example_4_different_detectors),
        ("短文本检测", example_5_short_text_detection),
        ("GraphRAG集成", example_6_graphrag_integration),
        ("Fallback机制", example_7_fallback_mechanism),
        ("多语言语料库", example_8_multilingual_corpus),
    ]
    
    print("\n" + "=" * 60)
    print("语言检测示例程序")
    print("=" * 60)
    print("\n可用示例:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")
    print(f"  0. 运行所有示例")
    
    try:
        choice = input("\n请选择要运行的示例 (0-8): ").strip()
        
        if choice == "0":
            for name, func in examples:
                func()
        elif choice.isdigit() and 1 <= int(choice) <= len(examples):
            examples[int(choice) - 1][1]()
        else:
            print("无效选择，运行所有示例...")
            for name, func in examples:
                func()
    
    except KeyboardInterrupt:
        print("\n\n用户中断")
    except Exception as e:
        logger.error(f"运行示例时出错: {e}", exc_info=True)


if __name__ == "__main__":
    main()
