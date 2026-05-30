# AI Agent with Web Search

LangChain-агент на Ollama Cloud с веб-поиском через Tavily и UI на Chainlit.

## Возможности

- Streaming ответов токен за токеном
- Автоматический поиск в интернете через Tavily
- Визуализация вызовов инструментов (Steps) в UI
- Чат-интерфейс на Chainlit, встраиваемый через iframe

## Требования

- Python 3.12+
- Виртуальное окружение (рекомендуется)

## Установка

```bash
# Клонировать репозиторий
git clone <repo-url> && cd agent

# Создать и активировать виртуальное окружение
python3 -m venv env
source env/bin/activate

# Установить зависимости
pip install -r requirements.txt
pip install chainlit
```

## Настройка

Скопировать `.env.template` в `.env` и заполнить ключи:

```env
OLLAMA_API_KEY="your-ollama-api-key"       # API-ключ Ollama Cloud
OLLAMA_CLOUD_MODEL="gemma4:31b-cloud"       # Модель
OLLAMA_CLOUD_ENDPOINT="https://ollama.com"  # Эндпоинт
TAVILY_API="your-tavily-api-key"            # API-ключ Tavily
DB_URI="postgres://..."                     # База данных (опционально)
```

## Запуск

### Chainlit UI (рекомендуется)

```bash
source env/bin/activate
chainlit run chainlit_app.py --port 8000
```

Открыть `http://localhost:8000`.

### CLI

```bash
source env/bin/activate
python3 main.py
```

## Встраивание в сервис

```html
<iframe src="http://localhost:8000" width="400" height="600" frameborder="0"></iframe>
```

## Структура

```
agent/
├── agents/           # Фабрика агента (LangGraph create_agent)
├── models/           # Фабрика модели (ChatOllama)
├── tools/            # Инструменты (Tavily search)
├── chainlit_app.py   # Точка входа Chainlit
├── main.py           # Точка входа CLI
└── .env              # Конфигурация
```
