from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, Union
from enum import Enum

from pydantic import BaseModel, Field, validator


class RiskLevel(str, Enum):
    """Уровни риска токена"""
    LOW = "low"
    MEDIUM = "medium" 
    HIGH = "high"
    CRITICAL = "critical"


class RecommendationType(str, Enum):
    """Типы рекомендаций"""
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    AVOID = "AVOID"


class SocialPlatform(str, Enum):
    """Социальные платформы"""
    TWITTER = "twitter"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    REDDIT = "reddit"


class AnalysisPattern(str, Enum):
    """Паттерны анализа"""
    BREAKOUT = "breakout"
    VOLUME_SPIKE = "volume_spike"
    WHALE_MOVEMENT = "whale_movement"
    SOCIAL_BUZZ = "social_buzz"
    LIQUIDITY_INCREASE = "liquidity_increase"
    DEV_ACTIVITY = "dev_activity"


# ==============================================
# БАЗОВЫЕ МОДЕЛИ ДАННЫХ
# ==============================================

class TokenMetadata(BaseModel):
    """Метаданные токена"""
    mint: str = Field(..., description="Mint адрес токена")
    name: Optional[str] = Field(None, description="Название токена")
    symbol: Optional[str] = Field(None, description="Символ токена")
    decimals: int = Field(default=9, description="Количество десятичных знаков")
    supply: Optional[Decimal] = Field(None, description="Общий объем токенов")
    description: Optional[str] = Field(None, description="Описание токена")
    image_uri: Optional[str] = Field(None, description="URL изображения")
    website: Optional[str] = Field(None, description="Официальный сайт")
    twitter: Optional[str] = Field(None, description="Twitter аккаунт")
    telegram: Optional[str] = Field(None, description="Telegram канал")
    
    @validator('mint')
    def validate_mint(cls, v):
        """Валидация mint адреса"""
        if not v or len(v) < 32:
            raise ValueError('Некорректный mint адрес')
        return v


class PriceData(BaseModel):
    """Ценовые данные токена"""
    current_price: Decimal = Field(..., description="Текущая цена в USD")
    price_change_1h: Optional[Decimal] = Field(None, description="Изменение за 1 час (%)")
    price_change_24h: Optional[Decimal] = Field(None, description="Изменение за 24 часа (%)")
    price_change_7d: Optional[Decimal] = Field(None, description="Изменение за 7 дней (%)")
    volume_24h: Optional[Decimal] = Field(None, description="Объем торгов за 24 часа")
    market_cap: Optional[Decimal] = Field(None, description="Рыночная капитализация")
    liquidity: Optional[Decimal] = Field(None, description="Ликвидность")
    holders_count: Optional[int] = Field(None, description="Количество держателей")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SocialData(BaseModel):
    """Данные из социальных сетей"""
    platform: SocialPlatform = Field(..., description="Платформа")
    content: str = Field(..., description="Контент поста/сообщения")
    author: Optional[str] = Field(None, description="Автор")
    timestamp: datetime = Field(..., description="Время публикации")
    metrics: Dict[str, Union[int, float]] = Field(default_factory=dict, description="Метрики (лайки, репосты и т.д.)")
    sentiment_score: Optional[float] = Field(None, ge=-1, le=1, description="Оценка тональности от -1 до 1")
    keywords: List[str] = Field(default_factory=list, description="Ключевые слова")


class OnChainMetrics(BaseModel):
    """On-chain метрики токена"""
    token_address: str = Field(..., description="Адрес токена")
    
    # Транзакции
    tx_count_24h: Optional[int] = Field(None, description="Количество транзакций за 24ч")
    unique_traders_24h: Optional[int] = Field(None, description="Уникальные трейдеры за 24ч")
    
    # Ликвидность
    liquidity_pools: List[Dict[str, Any]] = Field(default_factory=list, description="Пулы ликвидности")
    total_liquidity: Optional[Decimal] = Field(None, description="Общая ликвидность")
    
    # Держатели
    top_holders: List[Dict[str, Any]] = Field(default_factory=list, description="Крупнейшие держатели")
    holder_distribution: Dict[str, int] = Field(default_factory=dict, description="Распределение держателей")
    
    # Безопасность
    is_verified: Optional[bool] = Field(None, description="Верифицирован ли токен")
    security_score: Optional[float] = Field(None, ge=0, le=1, description="Оценка безопасности")
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ==============================================
# МОДЕЛИ АНАЛИЗА
# ==============================================

class MistralAnalysis(BaseModel):
    """Результат быстрого анализа Mistral 7B"""
    score: float = Field(..., ge=0, le=1, description="Общая оценка токена")
    risk_level: RiskLevel = Field(..., description="Уровень риска")
    is_scam_likely: bool = Field(default=False, description="Вероятность скама")
    key_points: List[str] = Field(default_factory=list, description="Ключевые моменты")
    notes: Optional[str] = Field(None, description="Дополнительные заметки")
    processing_time: float = Field(..., description="Время обработки в секундах")
    confidence: float = Field(..., ge=0, le=1, description="Уверенность в анализе")


class LlamaAnalysis(BaseModel):
    """Результат глубокого анализа LLaMA 3 70B"""
    pump_probability_1h: float = Field(..., ge=0, le=1, description="Вероятность роста за 1 час")
    pump_probability_24h: float = Field(..., ge=0, le=1, description="Вероятность роста за 24 часа")
    patterns: List[AnalysisPattern] = Field(default_factory=list, description="Обнаруженные паттерны")
    price_targets: Dict[str, Decimal] = Field(default_factory=dict, description="Ценовые цели")
    reasoning: str = Field(..., description="Подробное обоснование")
    risk_factors: List[str] = Field(default_factory=list, description="Факторы риска")
    opportunities: List[str] = Field(default_factory=list, description="Возможности")
    processing_time: float = Field(..., description="Время обработки в секундах")
    confidence: float = Field(..., ge=0, le=1, description="Уверенность в анализе")


class AggregatedAnalysis(BaseModel):
    """Агрегированный результат анализа"""
    final_score: float = Field(..., ge=0, le=1, description="Итоговая оценка")
    recommendation: RecommendationType = Field(..., description="Рекомендация")
    confidence: float = Field(..., ge=0, le=1, description="Общая уверенность")
    expected_return_1h: Optional[float] = Field(None, description="Ожидаемая доходность за 1ч (%)")
    expected_return_24h: Optional[float] = Field(None, description="Ожидаемая доходность за 24ч (%)")
    max_risk: float = Field(..., ge=0, le=1, description="Максимальный риск")
    summary: str = Field(..., description="Краткое резюме")
    action_plan: List[str] = Field(default_factory=list, description="План действий")


# ==============================================
# ОСНОВНАЯ МОДЕЛЬ АНАЛИЗА ТОКЕНА
# ==============================================

class TokenAnalysisRequest(BaseModel):
    """Запрос на анализ токена"""
    mint: str = Field(..., description="Mint адрес токена для анализа")
    include_social: bool = Field(default=True, description="Включить анализ социальных данных")
    include_deep_analysis: bool = Field(default=True, description="Включить глубокий анализ LLaMA")
    priority: str = Field(default="normal", description="Приоритет анализа (low/normal/high)")
    
    @validator('priority')
    def validate_priority(cls, v):
        allowed = ['low', 'normal', 'high']
        if v not in allowed:
            raise ValueError(f'priority должен быть одним из: {allowed}')
        return v


class TokenAnalysisResponse(BaseModel):
    """Полный результат анализа токена"""
    token: str = Field(..., description="Mint адрес токена")
    metadata: Optional[TokenMetadata] = Field(None, description="Метаданные токена")
    price_data: Optional[PriceData] = Field(None, description="Ценовые данные")
    onchain_metrics: Optional[OnChainMetrics] = Field(None, description="On-chain метрики")
    social_data: List[SocialData] = Field(default_factory=list, description="Социальные данные")
    
    # Результаты ИИ анализа
    analysis: Dict[str, Any] = Field(default_factory=dict, description="Результаты анализа")
    mistral_quick: Optional[MistralAnalysis] = Field(None, description="Быстрый анализ Mistral")
    llama_deep: Optional[LlamaAnalysis] = Field(None, description="Глубокий анализ LLaMA")
    aggregated: Optional[AggregatedAnalysis] = Field(None, description="Агрегированный результат")
    
    # Метаинформация
    analysis_id: str = Field(..., description="ID анализа")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Время анализа")
    processing_time_total: float = Field(..., description="Общее время обработки")
    data_sources: List[str] = Field(default_factory=list, description="Использованные источники данных")
    warnings: List[str] = Field(default_factory=list, description="Предупреждения")
    errors: List[str] = Field(default_factory=list, description="Ошибки при анализе")


# ==============================================
# МОДЕЛИ ДЛЯ СОЦИАЛЬНОГО АНАЛИЗА  
# ==============================================

class SocialAnalysisRequest(BaseModel):
    """Запрос на анализ социальных сигналов"""
    token_symbol: Optional[str] = Field(None, description="Символ токена")
    token_mint: Optional[str] = Field(None, description="Mint адрес токена")
    keywords: List[str] = Field(default_factory=list, description="Дополнительные ключевые слова")
    platforms: List[SocialPlatform] = Field(default_factory=lambda: [SocialPlatform.TWITTER, SocialPlatform.TELEGRAM])
    time_range_hours: int = Field(default=24, ge=1, le=168, description="Временной диапазон в часах")


class SocialAnalysisResponse(BaseModel):
    """Результат анализа социальных сигналов"""
    token_info: Dict[str, str] = Field(default_factory=dict, description="Информация о токене")
    social_data: List[SocialData] = Field(default_factory=list, description="Собранные социальные данные")
    
    # Аналитика
    total_mentions: int = Field(default=0, description="Общее количество упоминаний")
    sentiment_average: float = Field(default=0.0, ge=-1, le=1, description="Средняя тональность")
    viral_score: float = Field(default=0.0, ge=0, le=1, description="Оценка вирусности")
    top_keywords: List[str] = Field(default_factory=list, description="Топ ключевых слов")
    platform_breakdown: Dict[str, int] = Field(default_factory=dict, description="Разбивка по платформам")
    
    # Временная динамика
    hourly_activity: Dict[str, int] = Field(default_factory=dict, description="Активность по часам")
    trend_direction: str = Field(default="neutral", description="Направление тренда")
    
    # Метаинформация
    analysis_id: str = Field(..., description="ID анализа")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    processing_time: float = Field(..., description="Время обработки")


# ==============================================
# МОДЕЛИ ДЛЯ ИНТЕГРАЦИИ С ФРИЛАНСЕРОМ №2
# ==============================================

class ExternalAIInsights(BaseModel):
    """Данные от внешней системы ИИ (фрилансер №2)"""
    token: str = Field(..., description="Mint адрес токена")
    
    # Aegis AI - безопасность
    aegis: Dict[str, Any] = Field(default_factory=dict, description="Результаты Aegis AI")
    
    # DeepSeek-V2 - технический анализ
    deepseek: Dict[str, Any] = Field(default_factory=dict, description="Результаты DeepSeek-V2")
    
    # MythoMax-L2 - мемы и вирусность
    mythomax: Dict[str, Any] = Field(default_factory=dict, description="Результаты MythoMax-L2")
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    processing_time: float = Field(..., description="Время обработки внешней системы")


class MergedInsightsResponse(BaseModel):
    """Объединенный результат от обеих систем"""
    token: str = Field(..., description="Mint адрес токена")
    
    # Наши результаты
    internal_analysis: TokenAnalysisResponse = Field(..., description="Результаты внутренней системы")
    
    # Внешние результаты
    external_insights: Optional[ExternalAIInsights] = Field(None, description="Результаты внешней системы")
    
    # Финальная агрегация
    final_recommendation: RecommendationType = Field(..., description="Финальная рекомендация")
    consensus_score: float = Field(..., ge=0, le=1, description="Консенсус между системами")
    conflict_areas: List[str] = Field(default_factory=list, description="Области конфликта мнений")
    
    # Метаинформация
    merge_timestamp: datetime = Field(default_factory=datetime.utcnow)
    total_processing_time: float = Field(..., description="Общее время обработки обеими системами")