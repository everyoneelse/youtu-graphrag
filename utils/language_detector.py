"""
语种检测工具模块
提供多种语言检测算法的统一接口
支持 fastText, lingua, langdetect 等主流库
"""

import logging
from typing import Dict, List, Tuple, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class DetectorType(Enum):
    """语言检测器类型"""
    FASTTEXT = "fasttext"
    LINGUA = "lingua"
    LANGDETECT = "langdetect"
    LANGID = "langid"
    PYCLD3 = "pycld3"


class LanguageDetector:
    """
    统一的语言检测接口
    支持多种检测引擎，自动fallback机制
    
    推荐优先级:
    1. fastText (速度快，准确率高)
    2. lingua (准确率最高，速度较慢)
    3. langdetect (稳定可靠)
    """
    
    def __init__(
        self, 
        detector_type: DetectorType = DetectorType.FASTTEXT,
        fallback: bool = True,
        fasttext_model_path: Optional[str] = None
    ):
        """
        初始化语言检测器
        
        Args:
            detector_type: 主检测器类型
            fallback: 是否启用自动fallback到其他检测器
            fasttext_model_path: fastText模型路径
        """
        self.detector_type = detector_type
        self.fallback = fallback
        self.fasttext_model_path = fasttext_model_path or "lid.176.bin"
        
        self.detector = None
        self.fallback_detectors = []
        
        self._initialize_detector()
    
    def _initialize_detector(self):
        """初始化检测器"""
        try:
            if self.detector_type == DetectorType.FASTTEXT:
                self.detector = self._init_fasttext()
                if self.fallback:
                    self._init_fallback_detectors()
            
            elif self.detector_type == DetectorType.LINGUA:
                self.detector = self._init_lingua()
                if self.fallback:
                    self._init_fallback_detectors()
            
            elif self.detector_type == DetectorType.LANGDETECT:
                self.detector = self._init_langdetect()
                if self.fallback:
                    self._init_fallback_detectors()
            
            elif self.detector_type == DetectorType.LANGID:
                self.detector = self._init_langid()
                if self.fallback:
                    self._init_fallback_detectors()
            
            elif self.detector_type == DetectorType.PYCLD3:
                self.detector = self._init_pycld3()
                if self.fallback:
                    self._init_fallback_detectors()
            
            else:
                raise ValueError(f"不支持的检测器类型: {self.detector_type}")
        
        except Exception as e:
            logger.error(f"初始化主检测器失败: {e}")
            if self.fallback:
                logger.info("尝试初始化fallback检测器...")
                self._init_fallback_detectors()
    
    def _init_fasttext(self):
        """初始化fastText检测器"""
        try:
            import fasttext
            import os
            import urllib.request
            
            # 如果模型不存在，尝试下载
            if not os.path.exists(self.fasttext_model_path):
                logger.info(f"fastText模型不存在，正在下载到 {self.fasttext_model_path}...")
                url = "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin"
                
                # 尝试使用镜像
                mirror_url = "https://hf-mirror.com/facebook/fasttext-language-identification/resolve/main/model.bin"
                
                try:
                    urllib.request.urlretrieve(mirror_url, self.fasttext_model_path)
                    logger.info("从HuggingFace镜像下载成功")
                except:
                    logger.info("从HuggingFace镜像下载失败，尝试官方源...")
                    urllib.request.urlretrieve(url, self.fasttext_model_path)
                    logger.info("从官方源下载成功")
            
            # 加载模型，禁用警告
            model = fasttext.load_model(self.fasttext_model_path)
            logger.info("✓ fastText检测器初始化成功")
            return {"type": "fasttext", "model": model}
        
        except Exception as e:
            logger.warning(f"fastText初始化失败: {e}")
            logger.info("请手动下载模型: wget https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin")
            return None
    
    def _init_lingua(self):
        """初始化lingua检测器"""
        try:
            from lingua import Language, LanguageDetectorBuilder
            
            # 为了速度，只检测常见语言
            detector = LanguageDetectorBuilder.from_languages(
                Language.ENGLISH,
                Language.CHINESE,
                Language.JAPANESE,
                Language.KOREAN,
                Language.FRENCH,
                Language.GERMAN,
                Language.SPANISH,
                Language.RUSSIAN,
                Language.ARABIC,
                Language.PORTUGUESE
            ).build()
            
            logger.info("✓ lingua检测器初始化成功")
            return {"type": "lingua", "model": detector}
        
        except Exception as e:
            logger.warning(f"lingua初始化失败: {e}")
            return None
    
    def _init_langdetect(self):
        """初始化langdetect检测器"""
        try:
            from langdetect import detect, detect_langs, DetectorFactory
            
            # 设置种子确保结果可复现
            DetectorFactory.seed = 0
            
            logger.info("✓ langdetect检测器初始化成功")
            return {"type": "langdetect", "module": detect_langs}
        
        except Exception as e:
            logger.warning(f"langdetect初始化失败: {e}")
            return None
    
    def _init_langid(self):
        """初始化langid检测器"""
        try:
            import langid
            
            logger.info("✓ langid检测器初始化成功")
            return {"type": "langid", "model": langid}
        
        except Exception as e:
            logger.warning(f"langid初始化失败: {e}")
            return None
    
    def _init_pycld3(self):
        """初始化pycld3检测器"""
        try:
            import cld3
            
            logger.info("✓ pycld3检测器初始化成功")
            return {"type": "pycld3", "model": cld3}
        
        except Exception as e:
            logger.warning(f"pycld3初始化失败: {e}")
            return None
    
    def _init_fallback_detectors(self):
        """初始化备用检测器"""
        fallback_order = [
            DetectorType.FASTTEXT,
            DetectorType.LANGDETECT,
            DetectorType.LANGID,
            DetectorType.LINGUA
        ]
        
        for fallback_type in fallback_order:
            if fallback_type == self.detector_type:
                continue
            
            try:
                if fallback_type == DetectorType.FASTTEXT:
                    detector = self._init_fasttext()
                elif fallback_type == DetectorType.LINGUA:
                    detector = self._init_lingua()
                elif fallback_type == DetectorType.LANGDETECT:
                    detector = self._init_langdetect()
                elif fallback_type == DetectorType.LANGID:
                    detector = self._init_langid()
                else:
                    continue
                
                if detector:
                    self.fallback_detectors.append(detector)
                    logger.info(f"✓ 已添加fallback检测器: {fallback_type.value}")
            
            except Exception as e:
                logger.debug(f"Fallback检测器 {fallback_type.value} 初始化失败: {e}")
    
    def detect(self, text: str, threshold: float = 0.8) -> Tuple[str, float]:
        """
        检测文本的语言
        
        Args:
            text: 待检测文本
            threshold: 置信度阈值，低于此值会尝试fallback检测器
            
        Returns:
            (language_code, confidence) 例如 ('zh', 0.99)
        """
        if not text or not text.strip():
            return ("unknown", 0.0)
        
        text = text.strip()
        
        # 尝试主检测器
        if self.detector:
            try:
                result = self._detect_with_detector(self.detector, text)
                if result and result[1] >= threshold:
                    return result
                
                # 如果置信度低，尝试fallback
                if self.fallback and self.fallback_detectors:
                    logger.debug(f"主检测器置信度较低 ({result[1]:.2f})，尝试fallback...")
                    for fallback_detector in self.fallback_detectors:
                        fallback_result = self._detect_with_detector(fallback_detector, text)
                        if fallback_result and fallback_result[1] >= threshold:
                            return fallback_result
                
                return result
            
            except Exception as e:
                logger.error(f"检测失败: {e}")
        
        # 如果主检测器不可用，尝试fallback
        if self.fallback_detectors:
            for fallback_detector in self.fallback_detectors:
                try:
                    result = self._detect_with_detector(fallback_detector, text)
                    if result:
                        return result
                except Exception as e:
                    logger.debug(f"Fallback检测器失败: {e}")
        
        return ("unknown", 0.0)
    
    def _detect_with_detector(self, detector: Dict, text: str) -> Tuple[str, float]:
        """使用指定检测器进行检测"""
        if not detector:
            return ("unknown", 0.0)
        
        detector_type = detector["type"]
        
        if detector_type == "fasttext":
            model = detector["model"]
            # fastText需要去除换行符
            text_cleaned = text.replace('\n', ' ')
            predictions = model.predict(text_cleaned, k=1)
            language = predictions[0][0].replace('__label__', '')
            confidence = float(predictions[1][0])
            return (language, confidence)
        
        elif detector_type == "lingua":
            model = detector["model"]
            language_obj = model.detect_language_of(text)
            if language_obj:
                # lingua返回的是Language枚举，转换为ISO 639-1代码
                lang_map = {
                    "CHINESE": "zh",
                    "ENGLISH": "en",
                    "JAPANESE": "ja",
                    "KOREAN": "ko",
                    "FRENCH": "fr",
                    "GERMAN": "de",
                    "SPANISH": "es",
                    "RUSSIAN": "ru",
                    "ARABIC": "ar",
                    "PORTUGUESE": "pt"
                }
                lang_code = lang_map.get(language_obj.name, language_obj.name.lower()[:2])
                # lingua没有置信度，返回固定高值
                return (lang_code, 0.95)
            return ("unknown", 0.0)
        
        elif detector_type == "langdetect":
            detect_langs = detector["module"]
            results = detect_langs(text)
            if results:
                # langdetect返回列表，取第一个
                lang = results[0].lang
                prob = results[0].prob
                # langdetect返回的可能是 zh-cn，转换为 zh
                lang_code = lang.split('-')[0]
                return (lang_code, prob)
            return ("unknown", 0.0)
        
        elif detector_type == "langid":
            model = detector["model"]
            language, confidence = model.classify(text)
            return (language, confidence)
        
        elif detector_type == "pycld3":
            model = detector["model"]
            result = model.get_language(text)
            if result:
                return (result.language, result.probability)
            return ("unknown", 0.0)
        
        return ("unknown", 0.0)
    
    def detect_batch(self, texts: List[str], threshold: float = 0.8) -> List[Tuple[str, float]]:
        """
        批量检测文本语言
        
        Args:
            texts: 待检测文本列表
            threshold: 置信度阈值
            
        Returns:
            [(language_code, confidence), ...] 列表
        """
        return [self.detect(text, threshold) for text in texts]
    
    def detect_with_all_probs(self, text: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """
        检测文本语言并返回多个可能结果
        
        Args:
            text: 待检测文本
            top_k: 返回前k个结果
            
        Returns:
            [(language_code, confidence), ...] 按置信度排序
        """
        if not text or not text.strip():
            return [("unknown", 0.0)]
        
        text = text.strip()
        
        if not self.detector:
            return [("unknown", 0.0)]
        
        detector_type = self.detector["type"]
        
        if detector_type == "fasttext":
            model = self.detector["model"]
            text_cleaned = text.replace('\n', ' ')
            predictions = model.predict(text_cleaned, k=top_k)
            results = []
            for label, score in zip(predictions[0], predictions[1]):
                lang = label.replace('__label__', '')
                results.append((lang, float(score)))
            return results
        
        elif detector_type == "lingua":
            model = self.detector["model"]
            confidences = model.compute_language_confidence_values(text)
            lang_map = {
                "CHINESE": "zh", "ENGLISH": "en", "JAPANESE": "ja",
                "KOREAN": "ko", "FRENCH": "fr", "GERMAN": "de",
                "SPANISH": "es", "RUSSIAN": "ru", "ARABIC": "ar",
                "PORTUGUESE": "pt"
            }
            results = []
            for conf in confidences[:top_k]:
                lang_code = lang_map.get(conf.language.name, conf.language.name.lower()[:2])
                results.append((lang_code, conf.value))
            return results
        
        elif detector_type == "langdetect":
            detect_langs = self.detector["module"]
            results = detect_langs(text)
            output = []
            for i, result in enumerate(results[:top_k]):
                lang_code = result.lang.split('-')[0]
                output.append((lang_code, result.prob))
            return output
        
        else:
            # 其他检测器不支持多结果，返回单一结果
            result = self.detect(text)
            return [result]


# 便捷函数
def detect_language(text: str, detector_type: str = "fasttext") -> Tuple[str, float]:
    """
    快速检测文本语言的便捷函数
    
    Args:
        text: 待检测文本
        detector_type: 检测器类型 ("fasttext", "lingua", "langdetect")
        
    Returns:
        (language_code, confidence)
        
    Example:
        >>> lang, conf = detect_language("这是中文")
        >>> print(f"语言: {lang}, 置信度: {conf:.2f}")
        语言: zh, 置信度: 0.99
    """
    detector_enum = DetectorType(detector_type)
    detector = LanguageDetector(detector_type=detector_enum, fallback=True)
    return detector.detect(text)


# 全局单例检测器（推荐用于生产环境）
_global_detector = None

def get_global_detector() -> LanguageDetector:
    """获取全局单例检测器"""
    global _global_detector
    if _global_detector is None:
        _global_detector = LanguageDetector(
            detector_type=DetectorType.FASTTEXT,
            fallback=True
        )
    return _global_detector


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    test_texts = [
        "This is English text.",
        "这是中文文本。",
        "これは日本語のテキストです。",
        "이것은 한국어 텍스트입니다.",
        "Ceci est un texte français.",
        "Dies ist ein deutscher Text.",
        "Este es un texto en español.",
        "Это русский текст.",
    ]
    
    print("=" * 60)
    print("语言检测测试")
    print("=" * 60)
    
    # 测试便捷函数
    print("\n使用便捷函数测试:")
    for text in test_texts:
        lang, conf = detect_language(text)
        print(f"{text[:30]:30s} -> {lang:5s} (置信度: {conf:.4f})")
    
    # 测试全局检测器
    print("\n使用全局检测器测试:")
    detector = get_global_detector()
    for text in test_texts:
        lang, conf = detector.detect(text)
        print(f"{text[:30]:30s} -> {lang:5s} (置信度: {conf:.4f})")
    
    # 测试多概率检测
    print("\n测试多语言概率检测 (中文文本):")
    text = "这是一段中文文本，用来测试语言检测的准确性。"
    results = detector.detect_with_all_probs(text, top_k=5)
    for lang, prob in results:
        print(f"  {lang}: {prob:.4f}")
