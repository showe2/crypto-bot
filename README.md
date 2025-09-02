## Руководство пользователя

### 📋 Обзор системы

**Solana Token Analysis AI System** — это мощная система анализа токенов Solana с интеграцией искусственного интеллекта, обеспечивающая комплексную оценку безопасности, рыночных показателей и инвестиционных рисков.

#### Ключевые возможности:

- 🤖 **AI-Enhanced анализ** с использованием Llama 3.3-70B
- 🛡️ **Многоуровневые проверки безопасности** (GOplus, RugCheck, SolSniffer)
- 📊 **Комплексный рыночный анализ** (Birdeye, DexScreener, Helius)
- ⚡ **Real-time webhook** обработка новых токенов
- 📄 **DOCX отчеты** с детальным анализом
- 🗄️ **Векторное хранилище** (ChromaDB) для истории анализов
- 🚀 **Redis кэширование** для высокой производительности

---

## 🌐 Web Interface

### Основные страницы

#### 📊 Dashboard - `/`

- **Системные метрики** : статистика анализов, скорость ответа, активные токены
- **Статус сервисов** : мониторинг всех API сервисов в реальном времени
- **Последние анализы** : список недавно проанализированных токенов
- **AI модели** : статус Llama и других моделей

#### 🔍 Token Analysis - `/analysis`

- **Интерактивный анализ** : ввод адреса токена для анализа
- **Выбор типа** : быстрый или глубокий AI-анализ
- **Примеры токенов** : готовые адреса для тестирования
- **Real-time результаты** : мгновенное отображение результатов

#### 📚 All Analyses - `/analyses`

- **История анализов** : все проведенные анализы с пагинацией
- **Фильтрация** : по дате, риску, статусу безопасности, источнику
- **Поиск** : по адресу, имени или символу токена
- **Экспорт** : загрузка DOCX отчетов

---

## 🔗 API Endpoints

### 🎯 Анализ токенов

#### **Глубокий AI-анализ**

```http
POST /deep/{token_mint}
GET  /deep/{token_mint}?force_refresh=false
```

**Параметры:**

- `token_mint`: Адрес токена Solana (обязательный)
- `force_refresh`: Принудительное обновление кэша (опционально)

**Пример запроса:**

```bash
curl -X POST "http://localhost:8000/deep/So11111111111111111111111111111111111111112"
```

**Ответ содержит:**

- AI-анализ с рекомендациями Llama 3.3
- Детальные метрики рисков (киты, снайперы, волатильность)
- Комплексная оценка безопасности
- Рыночные данные из множественных источников
- Итоговый verdict: GO/WATCH/NO

#### **Быстрый анализ**

```http
POST /quick/{token_mint}
```

**Особенности:**

- Только проверки безопасности и базовый рыночный анализ
- Без AI-обработки
- Быстрое выполнение (5-15 секунд)
- Подходит для массовых проверок

### 📋 Управление данными

#### **API для получения данных дашборда**

```http
GET /api/dashboard
```

**Возвращает:**

- Метрики системы (общие анализы, успешность, время ответа)
- Статус сервисов
- Последние анализы
- Статус AI моделей

#### **История анализов с фильтрацией**

```http
GET /api/analyses?page=1&per_page=20&risk_level=high&date_from=2024-01-01
```

**Параметры фильтрации:**

- `page`: Номер страницы (по умолчанию 1)
- `per_page`: Элементов на странице (1-100)
- `source_event`: Фильтр по источнику (`webhook`, `api_request`)
- `date_from/date_to`: Диапазон дат (YYYY-MM-DD)
- `risk_level`: Уровень риска (`low`, `medium`, `high`, `critical`)
- `security_status`: Статус безопасности (`passed`, `failed`, `warning`)
- `search`: Поиск по адресу, имени или символу

### 📄 DOCX отчеты

#### **Скачивание отчета**

```http
GET /document/{cache_key}
```

**Как получить cache_key:**

- После анализа в ответе есть поле `docx_cache_key`
- Срок действия: 2 часа после анализа
- Автоматическое имя файла с датой и временем

**Содержимое DOCX отчета:**

- AI Investment Verdict (GO/WATCH/NO)
- Таблица рисков с цветовой кодировкой
- Top 3 причины покупать/избегать
- AI рассуждения и объяснения
- Детальные рыночные данные
- Анализ безопасности и LP статуса

---

## ⚡ WebHook система

### 🔄 Автоматическая обработка

#### **Create события**

```http
POST /webhooks/helius/mint
```

**Процесс обработки:**

1. Получение webhook от Helius
2. Извлечение адреса нового токена
3. Автоматический запуск **глубокого AI-анализа**
4. Обработка в фоновых workers
5. Сохранение в ChromaDB для истории

**Особенности:**

- Дедупликация: предотвращение повторных анализов
- Фоновая обработка: не блокирует webhook ответ
- AI-анализ: каждый новый токен автоматически получает полный AI-анализ

## 🏗️ Архитектура системы

### 📊 Поток данных

#### **Глубокий анализ (Deep Analysis Flow):**

```
1. Security Checks (GOplus + RugCheck + SolSniffer)
   ↓ (STOP если критические проблемы)
2. Market Analysis (Birdeye + DexScreener + Helius)
   ↓
3. AI Analysis (Llama 3.3-70B processing)
   ↓
4. Enhanced Scoring (60% traditional + 40% AI)
   ↓
5. Storage (ChromaDB + Redis cache)
   ↓
6. Response (JSON + DOCX cache key)
```

#### **WebHook обработка:**

```
Helius WebHook → Background Queue → Deep AI Analysis → ChromaDB Storage
```

### 🔧 Используемые сервисы

#### **Анализ безопасности:**

- **GOplus** : mint/freeze authority, honeypot detection
- **RugCheck** : rug pull анализ, LP безопасность
- **SolSniffer** : дополнительные проверки токенов

#### **Рыночные данные:**

- **Birdeye** : цены, объемы, ликвидность в реальном времени
- **DexScreener** : DEX данные, торговые пары
- **Helius** : on-chain метаданные, supply информация
- **SolanaFM** : дополнительная on-chain аналитика

#### **AI и обработка:**

- **Groq Llama 3.3-70B** : анализ рисков и рекомендации
- **Redis** : кэширование и rate limiting
- **ChromaDB** : векторное хранилище анализов

---

## 📈 Система скоринга

### 🎯 Enhanced Scoring Algorithm

#### **Компоненты оценки:**

**Security Base (60-95 баллов):**

- Базовая оценка: 60 баллов за прохождение проверки
- Штрафы: -8 баллов за каждое предупреждение
- Максимум: 95 баллов при отсутствии предупреждений

**Market Data Quality (0-20 баллов):**

- Наличие цены: +10 баллов
- Данные изменения цены: +5 баллов
- Актуальность данных: +5 баллов

**Volatility Analysis (0-15 баллов):**

- Низкая волатильность (≤5%): +15 баллов
- Умеренная (≤15%): +10 баллов
- Высокая (≤30%): +5 баллов
- Критическая (>30%): 0 баллов

**Whale Risk Assessment (0-20 баллов):**

- Нет китов (0%): +20 баллов
- Низкая концентрация (<30%): +15 баллов
- Умеренная (30-60%): +10 баллов
- Высокая (>60%): 0 баллов

**Sniper Detection (0-10 баллов):**

- Нет паттернов: +10 баллов
- Возможная активность: +5 баллов
- Высокий риск снайперов: 0 баллов

**Volume Analysis (0-25 баллов):**

- Отличный объем ($1M+): +25 баллов
- Очень хороший ($100K+): +20 баллов
- Хороший ($10K+): +15 баллов
- Умеренный ($1K+): +10 баллов
- Низкий (<$1K): +3 балла

**Liquidity Depth (0-15 баллов):**

- Отличная ($500K+): +15 баллов
- Очень хорошая ($100K+): +12 баллов
- Хорошая ($50K+): +10 баллов
- Умеренная ($10K+): +6 баллов
- Низкая (<$10K): +2 балла

**Price Stability (0-10 баллов):**

- Очень стабильная (±5%): +10 баллов
- Умеренная волатильность (±15%): +6 баллов
- Высокая (±30%): +3 балла
- Экстремальная (>±30%): 0 баллов

**Data Sources (0-10 баллов):**

- 5+ источников: +10 баллов
- 4 источника: +8 баллов
- 3 источника: +6 баллов
- 2 источника: +3 балла

**Metadata Completeness (0-5 баллов):**

- Полная информация о токене: +5 баллов

#### **AI Enhancement:**

- **Итоговый счет** : 60% традиционный + 40% AI
- **Минимальная оценка** : 60 баллов для токенов, прошедших безопасность
- **Бонус согласия** : +15 баллов когда AI и традиционный анализ совпадают

---

## 📊 Структура ответов

### 🎯 Глубокий анализ (Deep Analysis Response)

```json
{
  "analysis_id": "deep_analysis_1704067200_So111111",
  "token_address": "So11111111111111111111111111111111111111112",
  "timestamp": "2024-01-01T12:00:00.000000",
  "source_event": "api_deep",
  "analysis_type": "deep",

  "security_analysis": {
    "overall_safe": true,
    "critical_issues": [],
    "warnings": ["Some minor warning"],
    "goplus_result": {...},
    "rugcheck_result": {...},
    "solsniffer_result": {...}
  },

  "ai_analysis": {
    "ai_score": 78.5,
    "risk_assessment": "medium",
    "recommendation": "CONSIDER",
    "confidence": 85.0,
    "key_insights": [
      "Good liquidity depth ($150K verified)",
      "Low whale concentration (5 whales, 25% control)",
      "Stable recent volatility (8%)"
    ],
    "risk_factors": [
      "Moderate trading volume needs monitoring"
    ],
    "stop_flags": [],
    "market_metrics": {
      "volatility_risk": "low",
      "whale_risk": "low",
      "sniper_risk": "low",
      "liquidity_health": "good",
      "dev_risk": "medium",
      "lp_security": "likely_secure"
    },
    "llama_reasoning": "Token показывает здоровые рыночные метрики...",
    "processing_time": 3.2,
    "model_used": "llama-3.3-70b-versatile"
  },

  "overall_analysis": {
    "score": 82.4,
    "risk_level": "low",
    "recommendation": "consider",
    "confidence_score": 87.5,
    "summary": "AI-Enhanced Analysis: 82.4/100 | AI Recommendation: CONSIDER | Risk: LOW | 6 data sources",
    "positive_signals": [...],
    "risk_factors": [...],
    "security_passed": true,
    "ai_enhanced": true,
    "ai_score": 78.5,
    "traditional_score": 85.2,
    "score_breakdown": {
      "traditional_weight": 0.6,
      "ai_weight": 0.4,
      "final_score": 82.4,
      "agreement_bonus": true
    },

    "volatility": {
      "recent_volatility_percent": 8.2,
      "volatility_risk": "low"
    },
    "whale_analysis": {
      "whale_count": 5,
      "whale_control_percent": 25.3,
      "top_whale_percent": 8.1,
      "whale_risk_level": "low"
    },
    "sniper_detection": {
      "similar_holders": 2,
      "pattern_detected": false,
      "sniper_risk": "low"
    }
  },

  "service_responses": {
    "birdeye": {...},
    "goplus": {...},
    "rugcheck": {...},
    "dexscreener": {...},
    "helius": {...}
  },

  "metadata": {
    "processing_time_seconds": 18.5,
    "services_attempted": 6,
    "services_successful": 5,
    "security_check_passed": true,
    "ai_analysis_completed": true,
    "analysis_stopped_at_security": false
  },

  "docx_cache_key": "enhanced_token_analysis:analysis:So111111",
  "docx_expires_at": "2024-01-01T14:00:00.000000"
}
```

### ⚡ Быстрый анализ (Quick Analysis Response)

```json
{
  "analysis_type": "quick",
  "overall_analysis": {
    "score": 75.0,
    "risk_level": "medium",
    "recommendation": "caution",
    "confidence_score": 78.0,
    "ai_enhanced": false,
    "security_passed": true,
    "verdict": {
      "decision": "WATCH"
    }
  },
  "security_analysis": {...},
  "service_responses": {...},
  "metadata": {
    "processing_time_seconds": 8.2,
    "ai_analysis_completed": false
  }
}
```

### ❌ Остановка на безопасности

```json
{
  "analysis_type": "deep",
  "overall_analysis": {
    "score": 10.0,
    "risk_level": "critical",
    "recommendation": "avoid",
    "summary": "SECURITY FAILED: 2 critical issues, 1 warnings",
    "security_focused": true,
    "critical_security_issues": [
      "Token has active mint authority - unlimited supply possible",
      "Token has freeze authority - accounts can be frozen"
    ]
  },
  "metadata": {
    "security_check_passed": false,
    "analysis_stopped_at_security": true,
    "ai_analysis_completed": false
  }
}
```

---

## 🧠 AI-Enhanced функции

### 🎯 Расширенная метрика рисков

#### **Whale Analysis (Анализ китов):**

- **Обнаружение** : держатели с >2% токенов
- **Оценка риска** : контроль китов vs распределение
- **AI интеграция** : влияние на рекомендации

**Примеры оценок:**

- 0 китов = ОТЛИЧНО (идеальное распределение)
- 1-3 кита, <30% контроль = ХОРОШО
- 4+ китов, >50% контроль = ВЫСОКИЙ РИСК

#### **Sniper Detection (Детекция снайперов):**

- **Паттерны** : похожие проценты владения
- **Ботовая активность** : координированные покупки
- **AI анализ** : влияние на естественный спрос

**Алгоритм:**

- Анализ топ-50 держателей
- Поиск похожих процентов (±0.05%)
- 10 похожих паттернов = ВЫСОКИЙ РИСК

#### **Volatility Assessment (Оценка волатильности):**

- **Источник** : последние 20 торгов от Birdeye
- **Расчет** : (max_price - min_price) / avg_price \* 100
- **Категории** : низкая (<15%), умеренная (15-30%), высокая (>30%)

### 🔮 AI Reasoning Engine

#### **Llama 3.3-70B Features:**

- **Multi-source validation** : проверка данных из нескольких источников
- **Realistic expectations** : понимание ограничений данных
- **Risk weighting** : интеллектуальное взвешивание рисков
- **Confidence scaling** : адаптивная уверенность в анализе

#### **Примеры AI рассуждений:**

```
"Token показывает здоровые рыночные метрики с ликвидностью $150K
из Birdeye и отсутствием китов согласно GOplus анализу.
Низкая волатильность 8% указывает на стабильность,
но умеренный объем торгов требует мониторинга."
```

---

## 💾 Система хранения

### 🗄️ ChromaDB Integration

#### **Векторное хранилище:**

- **Коллекция** : `token_analyses`
- **Автоматическое хранение** : всех анализов
- **Семантический поиск** : по содержимому анализов
- **Metadata фильтры** : точная фильтрация

#### **Поиск анализов:**

```http
GET /api/analyses
```

**Возможности поиска:**

- По адресу токена
- По имени/символу

---

### 📊 Мониторинг метрик

#### **Ключевые KPI:**

- **Success Rate** : % успешных анализов
- **Average Response Time** : среднее время ответа
- **System Health**: статус работы елементов системы

---

## 🎯 Практические примеры

### 🔍 Анализ конкретного токена

**Wrapped SOL (безопасный токен):**

```bash
curl -X POST "http://localhost:8000/deep/So11111111111111111111111111111111111111112"
```

**Ожидаемый результат:**

- Оценка: 85-95 баллов
- Риск: low
- AI рекомендация: CONSIDER или BUY
- Причины: отличная ликвидность, нет китов, проверенный токен

**Высокорисковый токен:**

```bash
curl -X POST "http://localhost:8000/deep/RISKY_TOKEN_ADDRESS"
```

**Возможный результат:**

- Остановка на этапе безопасности
- Оценка: 10-25 баллов
- Риск: critical
- AI рекомендация: AVOID
- Причины: активные authorities, проблемы ликвидности

---

## 🎉 Заключение

Solana Token Analysis AI System предоставляет комплексную платформу для анализа токенов с использованием передовых технологий AI и множественных источников данных. Система спроектирована для высокой производительности, надежности и точности анализа.

**Ключевые преимущества:**

- Безопасность прежде всего (security-first подход)
- AI-enhanced анализ для глубокого понимания
- Автоматизация через WebHook интеграцию
- Comprehensive data coverage из 7+ источников
- Готовые DOCX отчеты для документирования
