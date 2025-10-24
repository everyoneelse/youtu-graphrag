"""
语言检测算法基准测试
对比 fastText, lingua, langdetect, langid 等算法的准确率和性能
"""

import time
import logging
from typing import List, Dict, Tuple
from collections import defaultdict
from utils.language_detector import LanguageDetector, DetectorType

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# 测试数据集 - 包含真实标签
TEST_DATASET = [
    # 英语 (en)
    ("The quick brown fox jumps over the lazy dog.", "en"),
    ("Machine learning is transforming our world.", "en"),
    ("Natural language processing is a subfield of AI.", "en"),
    ("Hello", "en"),
    ("cat", "en"),
    
    # 中文 (zh)
    ("这是一段中文文本，用于测试语言检测算法。", "zh"),
    ("人工智能正在改变我们的世界。", "zh"),
    ("机器学习是人工智能的重要分支。", "zh"),
    ("你好", "zh"),
    ("猫", "zh"),
    
    # 日语 (ja)
    ("これは日本語のテキストです。", "ja"),
    ("機械学習は人工知能の重要な分野です。", "ja"),
    ("自然言語処理は素晴らしい技術です。", "ja"),
    ("こんにちは", "ja"),
    ("猫", "ja"),
    
    # 韩语 (ko)
    ("이것은 한국어 텍스트입니다.", "ko"),
    ("기계 학습은 인공 지능의 중요한 분야입니다.", "ko"),
    ("자연어 처리는 멋진 기술입니다.", "ko"),
    ("안녕하세요", "ko"),
    
    # 法语 (fr)
    ("Ceci est un texte français.", "fr"),
    ("L'intelligence artificielle transforme notre monde.", "fr"),
    ("Le traitement du langage naturel est fascinant.", "fr"),
    ("Bonjour", "fr"),
    
    # 德语 (de)
    ("Dies ist ein deutscher Text.", "de"),
    ("Künstliche Intelligenz verändert unsere Welt.", "de"),
    ("Maschinelles Lernen ist ein wichtiges Feld.", "de"),
    ("Guten Tag", "de"),
    
    # 西班牙语 (es)
    ("Este es un texto en español.", "es"),
    ("La inteligencia artificial está cambiando nuestro mundo.", "es"),
    ("El aprendizaje automático es fascinante.", "es"),
    ("Hola", "es"),
    
    # 俄语 (ru)
    ("Это русский текст.", "ru"),
    ("Искусственный интеллект меняет наш мир.", "ru"),
    ("Машинное обучение - важная область.", "ru"),
    ("Привет", "ru"),
    
    # 阿拉伯语 (ar)
    ("هذا نص عربي.", "ar"),
    ("الذكاء الاصطناعي يغير عالمنا.", "ar"),
    
    # 葡萄牙语 (pt)
    ("Este é um texto em português.", "pt"),
    ("A inteligência artificial está transformando nosso mundo.", "pt"),
]


def evaluate_detector(
    detector_type: DetectorType,
    test_data: List[Tuple[str, str]],
    verbose: bool = False
) -> Dict:
    """
    评估单个检测器的性能
    
    Args:
        detector_type: 检测器类型
        test_data: 测试数据 [(text, true_label), ...]
        verbose: 是否打印详细信息
        
    Returns:
        评估结果字典
    """
    logger.info(f"\n评估检测器: {detector_type.value}")
    logger.info("=" * 60)
    
    try:
        detector = LanguageDetector(detector_type=detector_type, fallback=False)
    except Exception as e:
        logger.error(f"无法初始化检测器 {detector_type.value}: {e}")
        return {
            "detector": detector_type.value,
            "total": len(test_data),
            "correct": 0,
            "accuracy": 0.0,
            "avg_time": 0.0,
            "error": str(e)
        }
    
    correct = 0
    total = len(test_data)
    errors = []
    total_time = 0
    
    # 按文本长度分类统计
    short_text_correct = 0
    short_text_total = 0
    long_text_correct = 0
    long_text_total = 0
    
    for text, true_lang in test_data:
        try:
            start_time = time.time()
            predicted_lang, confidence = detector.detect(text)
            elapsed_time = time.time() - start_time
            total_time += elapsed_time
            
            # 语言码归一化 (有些库返回 zh-cn, 需要转换为 zh)
            predicted_lang = predicted_lang.split('-')[0]
            true_lang = true_lang.split('-')[0]
            
            is_correct = predicted_lang == true_lang
            
            if is_correct:
                correct += 1
            else:
                errors.append({
                    "text": text,
                    "true": true_lang,
                    "predicted": predicted_lang,
                    "confidence": confidence
                })
            
            # 按文本长度分类
            if len(text) <= 20:
                short_text_total += 1
                if is_correct:
                    short_text_correct += 1
            else:
                long_text_total += 1
                if is_correct:
                    long_text_correct += 1
            
            if verbose:
                status = "✓" if is_correct else "✗"
                logger.info(
                    f"{status} 文本: {text[:40]:40s} | "
                    f"真实: {true_lang:5s} | 预测: {predicted_lang:5s} | "
                    f"置信度: {confidence:.4f} | 耗时: {elapsed_time*1000:.2f}ms"
                )
        
        except Exception as e:
            logger.error(f"检测失败: {text[:30]}... | 错误: {e}")
            errors.append({
                "text": text,
                "true": true_lang,
                "predicted": "ERROR",
                "error": str(e)
            })
    
    accuracy = correct / total if total > 0 else 0
    avg_time = total_time / total if total > 0 else 0
    
    short_accuracy = short_text_correct / short_text_total if short_text_total > 0 else 0
    long_accuracy = long_text_correct / long_text_total if long_text_total > 0 else 0
    
    results = {
        "detector": detector_type.value,
        "total": total,
        "correct": correct,
        "accuracy": accuracy,
        "avg_time": avg_time,
        "short_text_accuracy": short_accuracy,
        "long_text_accuracy": long_accuracy,
        "short_text_count": short_text_total,
        "long_text_count": long_text_total,
        "errors": errors
    }
    
    logger.info(f"\n总体准确率: {accuracy*100:.2f}% ({correct}/{total})")
    logger.info(f"短文本准确率: {short_accuracy*100:.2f}% ({short_text_correct}/{short_text_total})")
    logger.info(f"长文本准确率: {long_accuracy*100:.2f}% ({long_text_correct}/{long_text_total})")
    logger.info(f"平均检测时间: {avg_time*1000:.2f}ms")
    logger.info(f"吞吐量: {1/avg_time:.0f} 文本/秒\n")
    
    if errors and verbose:
        logger.info("错误示例:")
        for i, error in enumerate(errors[:5], 1):
            logger.info(f"  {i}. {error}")
    
    return results


def compare_all_detectors(test_data: List[Tuple[str, str]], verbose: bool = False):
    """对比所有检测器"""
    
    detectors = [
        DetectorType.FASTTEXT,
        DetectorType.LANGDETECT,
        DetectorType.LANGID,
        DetectorType.LINGUA,
    ]
    
    results = []
    
    print("\n" + "=" * 80)
    print("语言检测算法基准测试")
    print("=" * 80)
    print(f"测试样本数: {len(test_data)}")
    print(f"覆盖语言: en, zh, ja, ko, fr, de, es, ru, ar, pt")
    print("=" * 80)
    
    for detector_type in detectors:
        try:
            result = evaluate_detector(detector_type, test_data, verbose)
            results.append(result)
        except Exception as e:
            logger.error(f"评估 {detector_type.value} 时出错: {e}")
    
    # 打印对比结果
    print("\n" + "=" * 80)
    print("综合对比结果")
    print("=" * 80)
    
    # 排序 - 按准确率
    results_sorted = sorted(results, key=lambda x: x["accuracy"], reverse=True)
    
    print(f"\n{'检测器':<15} {'总体准确率':>12} {'短文本':>12} {'长文本':>12} {'平均耗时':>12} {'吞吐量':>12}")
    print("-" * 80)
    
    for result in results_sorted:
        detector = result["detector"]
        accuracy = result["accuracy"] * 100
        short_acc = result.get("short_text_accuracy", 0) * 100
        long_acc = result.get("long_text_accuracy", 0) * 100
        avg_time = result["avg_time"] * 1000
        throughput = 1 / result["avg_time"] if result["avg_time"] > 0 else 0
        
        print(
            f"{detector:<15} "
            f"{accuracy:>11.2f}% "
            f"{short_acc:>11.2f}% "
            f"{long_acc:>11.2f}% "
            f"{avg_time:>10.2f}ms "
            f"{throughput:>9.0f}/s"
        )
    
    # 推荐
    print("\n" + "=" * 80)
    print("推荐选择")
    print("=" * 80)
    
    best_accuracy = max(results_sorted, key=lambda x: x["accuracy"])
    best_speed = min(results_sorted, key=lambda x: x["avg_time"])
    
    print(f"\n✓ 准确率最高: {best_accuracy['detector']} ({best_accuracy['accuracy']*100:.2f}%)")
    print(f"✓ 速度最快: {best_speed['detector']} ({1/best_speed['avg_time']:.0f} 文本/秒)")
    
    # 综合推荐
    print("\n综合推荐:")
    print("  1. 🏆 实时应用: fastText (速度快+准确率高)")
    print("  2. 🥈 离线处理: lingua (准确率最高)")
    print("  3. 🥉 通用场景: langdetect (稳定可靠)")
    
    return results


def test_edge_cases():
    """测试边界情况"""
    print("\n" + "=" * 80)
    print("边界情况测试")
    print("=" * 80)
    
    edge_cases = [
        ("", "empty"),  # 空文本
        ("   ", "whitespace"),  # 纯空白
        ("123456", "numbers"),  # 纯数字
        ("!@#$%^&*()", "symbols"),  # 纯符号
        ("a", "single_char"),  # 单字符
        ("Hello 你好 world 世界", "mixed"),  # 混合语言
        ("😀😃😄😁", "emoji"),  # 表情符号
    ]
    
    detector = LanguageDetector(detector_type=DetectorType.FASTTEXT, fallback=True)
    
    print(f"\n{'测试用例':<25} {'检测结果':>10} {'置信度':>10}")
    print("-" * 50)
    
    for text, case_type in edge_cases:
        try:
            lang, conf = detector.detect(text)
            print(f"{repr(text):<25} {lang:>10} {conf:>10.4f}")
        except Exception as e:
            print(f"{repr(text):<25} {'ERROR':>10} {str(e)[:10]:>10}")


def performance_test():
    """性能压力测试"""
    print("\n" + "=" * 80)
    print("性能压力测试")
    print("=" * 80)
    
    # 生成大量测试数据
    test_texts = [
        "This is a test sentence in English.",
        "这是一个中文测试句子。",
        "これは日本語のテスト文です。",
    ] * 1000  # 3000个样本
    
    detectors = [
        DetectorType.FASTTEXT,
        DetectorType.LANGDETECT,
        DetectorType.LANGID,
    ]
    
    print(f"\n测试样本数: {len(test_texts)}")
    print(f"\n{'检测器':<15} {'总耗时':>12} {'平均耗时':>12} {'吞吐量':>12}")
    print("-" * 55)
    
    for detector_type in detectors:
        try:
            detector = LanguageDetector(detector_type=detector_type, fallback=False)
            
            start_time = time.time()
            for text in test_texts:
                detector.detect(text)
            total_time = time.time() - start_time
            
            avg_time = total_time / len(test_texts) * 1000
            throughput = len(test_texts) / total_time
            
            print(
                f"{detector_type.value:<15} "
                f"{total_time:>10.2f}s "
                f"{avg_time:>10.2f}ms "
                f"{throughput:>9.0f}/s"
            )
        
        except Exception as e:
            print(f"{detector_type.value:<15} ERROR: {e}")


def main():
    """运行所有测试"""
    
    tests = [
        ("基准测试", lambda: compare_all_detectors(TEST_DATASET, verbose=False)),
        ("详细测试", lambda: compare_all_detectors(TEST_DATASET, verbose=True)),
        ("边界情况", test_edge_cases),
        ("性能测试", performance_test),
    ]
    
    print("\n" + "=" * 80)
    print("语言检测基准测试程序")
    print("=" * 80)
    print("\n可用测试:")
    for i, (name, _) in enumerate(tests, 1):
        print(f"  {i}. {name}")
    print(f"  0. 运行所有测试")
    
    try:
        choice = input("\n请选择要运行的测试 (0-4): ").strip()
        
        if choice == "0":
            for name, func in tests:
                func()
        elif choice.isdigit() and 1 <= int(choice) <= len(tests):
            tests[int(choice) - 1][1]()
        else:
            print("无效选择，运行基准测试...")
            tests[0][1]()
    
    except KeyboardInterrupt:
        print("\n\n用户中断")
    except Exception as e:
        logger.error(f"运行测试时出错: {e}", exc_info=True)


if __name__ == "__main__":
    main()
