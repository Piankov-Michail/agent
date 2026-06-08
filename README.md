# AI Agent with Web Search

LangChain-агент на Ollama Cloud с веб-поиском через Tavily и UI на Chainlit.

## Возможности

- Streaming ответов токен за токеном
- Автоматический поиск в интернете через Tavily
- Визуализация вызовов инструментов (Steps) в UI
- Чат-интерфейс на Chainlit, встраиваемый через iframe
- Персистентная история диалогов в PostgreSQL (LangGraph checkpointer + Chainlit DataLayer)
- Автоматическая суммаризация длинных диалогов
- Контекст текущего времени/даты для агента (DateTimeMiddleware)

## Архитектура

```mermaid
flowchart TB
    subgraph UI["Chainlit UI"]
        direction LR
        WC[Web Client] --> CA[chainlit_app.py<br/>on_chat_start / on_message]
    end

    subgraph ML["Middleware Layer"]
        direction TB
        DT[DateTimeMiddleware<br/>Внедряет время сервера<br/>перед каждым вызовом]
        SM[SummaryMemoryMiddleware<br/>Суммаризирует историю<br/>при превышении лимита]
    end

    subgraph AG["Agent Layer"]
        AGT[DefaultAgentFactory<br/>create_agent<br/>+ system prompt<br/>+ tools]
    end

    subgraph MC["Model & Checkpointer"]
        OLL[Ollama Cloud<br/>ChatOllama]
        CP[Checkpointer<br/>Postgres / MemorySaver]
    end

    subgraph DB["PostgreSQL"]
        LG_DB[(LangGraph<br/>checkpoints<br/>+ writes)]
        CL_DB[(Chainlit<br/>threads<br/>+ steps<br/>+ elements)]
    end

    CA --> DT
    DT --> SM
    SM --> AGT
    AGT --> OLL
    AGT --> CP
    CP --> LG_DB
    CA --> CL_DB
```

## Memory & Agent Pipeline

```mermaid
sequenceDiagram
    participant U as User
    participant CL as Chainlit
    participant DT as DateTimeMiddleware
    participant SM as SummaryMemory
    participant AG as Agent
    participant LLM as Ollama
    participant CP as Checkpointer

    U->>CL: Message
    CL->>CL: Get agent config<br/>thread_id = "{session_id}::{chat_id}"
    CL->>DT: before_agent / abefore_agent
    DT->>DT: datetime.now(UTC/local)
    DT-->>AG: + SystemMessage("Current time: ...")
    
    CL->>AG: ainvoke(messages)
    Note over AG,CP: LangGraph processes messages

    AG->>SM: before_model / abefore_model
    SM->>SM: Проверка len(messages) > max_messages (20)
    alt История превышает лимит
        SM->>LLM: Запрос суммаризации старых сообщений
        LLM-->>SM: Краткое содержание
        SM->>SM: RemoveMessage(все старые) +<br/>SystemMessage(суммаризация) +<br/>оставить keep_messages (10)
    end
    SM-->>AG: Обновлённый список сообщений

    AG->>LLM: Inference
    LLM-->>AG: Ответ
    AG->>CP: Сохранение checkpoint
    CP-->>DB: checkpoint + writes
    AG-->>CL: Streaming ответа
    CL-->>U: Токены
    CL-->>DB: Thread / Steps
```

### Thread ID Scheme

Каждый диалог идентифицируется составным ключом:

```
thread_id = "{session_id}::{chat_id}"
```

- **session_id** — UUID пользователя; генерируется один раз на сессию, хранится в `cl.user_session` и в `metadata` треда Chainlit
- **chat_id** — UUID конкретного чата; новый при `on_chat_start`, восстанавливается из metadata при `on_chat_resume`

В CLI-режиме (`main.py`) `session_id` фиксирован на время процесса, `chat_id` = `"42"`.

### Middleware Chain

Оба middleware реализуют интерфейс `AgentMiddleware` из `langchain.agents.middleware`.

| Middleware | Хук | Назначение |
|---|---|---|
| `DateTimeMiddleware` | `before_agent / abefore_agent` | Вставляет SystemMessage с текущим UTC/server/local временем перед каждым вызовом агента |
| `SummaryMemoryMiddleware` | `before_model / abefore_model` | При превышении `max_messages` (20) суммаризирует старые сообщения, заменяя их кратким пересказом; оставляет `keep_messages` (10) последних |

Middleware применяются в порядке массива `middleware=[DateTimeMiddleware, SummaryMemoryMiddleware]`, переданного в `create_agent`. LangGraph вызывает их цепочкой: сначала `DateTimeMiddleware.before_agent`, затем, перед обращением к LLM, — `SummaryMemoryMiddleware.before_model`.

### Checkpointer

LangGraph сохраняет checkpoint после каждого шага обработки. Выбор хранилища:

| Драйвер | Условие |
|---|---|
| `AsyncPostgresSaver` | `DB_URI` начинается с `postgres://` или `postgresql://` |
| `MemorySaver` | fallback при недоступности PostgreSQL |

Конфигурация:
- `memory/postgres.py`: исправленная версия `AsyncPostgresSaver` (убрано `CREATE INDEX CONCURRENTLY`, не работающее внутри транзакции)
- Миграции LangGraph применяются автоматически при создании checkpointer'а (`get_checkpointer`)

Каждый запуск приложения проходит все pending-миграции (версионирование через таблицу `checkpoint_migrations`).

## Chainlit User & Chat Logic

### Аутентификация

```python
@cl.password_auth_callback
async def auth_callback(username: str, password: str) -> cl.User | None:
    if not CHAINLIT_AUTH_SECRET:
        return None
    return cl.User(identifier=username, metadata={"provider": "credentials"})
```

- Любая пара логин/пароль создаёт `cl.User`
- Если `CHAINLIT_AUTH_SECRET` не задан — аутентификация отключена
- `CHAINLIT_AUTH_SECRET` используется для JWT-токенов в Chainlit

### Жизненный цикл чата

```mermaid
flowchart LR
    subgraph Start["Новый чат"]
        CS["on_chat_start"]
        CS --> S1[session_id = UUID]
        CS --> S2[chat_id = UUID]
        CS --> S3[thread_id = session_id::chat_id]
        CS --> S4[Сохранение в user_session]
    end

    subgraph Resume["Перезагрузка потока"]
        CR["on_chat_resume<br/>(thread: ThreadDict)"]
        CR --> R1[session_id =<br/>user_session<br/>или thread.metadata]
        CR --> R2[chat_id =<br/>user_session<br/>или thread.metadata]
        CR --> R3[thread_id = session_id::chat_id]
    end

    subgraph Message["Обработка сообщения"]
        OM["on_message"]
        OM --> M1[thread_id из user_session]
        OM --> M2[agent.astream<br/>stream_mode=messages]
        OM --> M3[Streaming токенов<br/>через AsyncLangchainCallbackHandler]
    end

    Start --> Message
    Resume --> Message
```

### Сохранение данных

Два уровня персистентности:

1. **Chainlit Data Layer** (PostgreSQL, таблицы `threads`, `steps`, `elements`, `users`)
   - Инициализируется в `@cl.on_app_startup` через `init_chainlit_database()`
   - Схема создаётся автоматически (`chainlit_db/schema.py`)
   - `SQLAlchemyDataLayer` сохраняет каждый шаг выполнения (вызовы инструментов, ответы LLM)

2. **LangGraph Checkpointer** (PostgreSQL через psycopg3)
   - Сохраняет полное состояние графа после каждого шага
   - Позволяет восстанавливать диалог при перезагрузке страницы
   - `thread_id` одинаков для обоих уровней (единый ключ)

### Chainlit Database Schema

```mermaid
erDiagram
    users {
        id TEXT PK
        identifier TEXT
        createdAt TEXT
        metadata JSONB
    }
    threads {
        id TEXT PK
        createdAt TEXT
        name TEXT
        userId TEXT
        userIdentifier TEXT
        tags JSONB
        metadata JSONB
    }
    steps {
        id TEXT PK
        name TEXT
        type TEXT
        threadId TEXT
        parentId TEXT
        streaming BOOLEAN
        waitForAnswer BOOLEAN
        isError BOOLEAN
        metadata JSONB
        tags JSONB
        input TEXT
        output TEXT
        createdAt TEXT
        start TEXT
        end TEXT
        generation JSONB
        showInput TEXT
        language TEXT
        defaultOpen BOOLEAN
        autoCollapse BOOLEAN
    }
    feedbacks {
        id TEXT PK
        forId TEXT
        value DOUBLE PRECISION
        comment TEXT
    }
    elements {
        id TEXT PK
        threadId TEXT
        type TEXT
        chainlitKey TEXT
        url TEXT
        objectKey TEXT
        name TEXT
        display TEXT
        size TEXT
        language TEXT
        page TEXT
        forId TEXT
        mime TEXT
        props TEXT
        autoPlay TEXT
        playerConfig TEXT
    }
    threads ||--o{ steps : "threadId"
    threads ||--o{ elements : "threadId"
    steps ||--o{ feedbacks : "forId"
    steps ||--o{ elements : "forId"
```

## DateTimeMiddleware — актуализация времени

### Назначение

Предоставляет LLM точный контекст текущего времени сервера перед каждым вызовом. Без этого LLM оперирует только своей датой обучения (например, "knowledge cutoff 2025") и не может корректно отвечать на вопросы о текущих датах, событиях, возрасте и т.п.

### Принцип работы

```mermaid
flowchart LR
    A[Вызов агента] --> B[abefore_agent<br/>datetime.now(UTC)]
    B --> C[Формирование SystemMessage]
    C --> D[UTC: 2026-06-08 12:04:34]
    C --> E[Server: 2026-06-08 15:04:34 +0300]
    C --> F[User timezone: Europe/Moscow]
    D --> G[SystemMessage добавляется<br/>в начало списка сообщений]
    E --> G
    F --> G
    G --> H[LLM получает актуальное<br/>время в контексте]
```

Middleware перехватывает вызов на этапе `abefore_agent` — это выполняется **один раз за инвокацию агента**, а не на каждом шаге внутри агента.

### Формат сообщения

```
Current date and time (internal context):
  UTC:  Monday, 2026-06-08 12:04:34 UTC
  Server: Monday, 2026-06-08 15:04:34 +0300
  User timezone: Europe/Moscow

Do NOT mention or announce the current date or time to the user unless they explicitly ask about it.
Use this context internally for tool calls and queries that need date/time information.
```

Две ключевые особенности:
1. Время передаётся как **SystemMessage** — модель видит его, но оно скрыто от пользователя в UI
2. Инструкция "Do NOT mention..." предотвращает лишние упоминания времени моделью

### Конфигурация

```env
DEFAULT_TIMEZONE="Europe/Moscow"   # Часовой пояс пользователя (опционально)
```

Если `DEFAULT_TIMEZONE` не задан, используется системный часовой пояс сервера (`datetime.now().astimezone().tzname()`).

### Отличие от before_model

| Хук | Момент вызова | Количество за вызов |
|---|---|---|
| `before_agent` / `abefore_agent` | Перед стартом агента (один раз) | 1 |
| `before_model` / `abefore_model` | Перед каждым обращением к LLM | Может быть несколько (ReAct-циклы) |

`DateTimeMiddleware` использует `before_agent`, так как время достаточно получить один раз перед началом обработки запроса. `SummaryMemoryMiddleware` использует `before_model`, так как суммаризация должна выполняться перед каждым обращением к LLM (с учётом уже накопленных шагов).

## LangGraph Checkpointer — персистентность истории

### Схема данных (Postgres)

LangGraph использует собственные таблицы `checkpoints`, `checkpoint_blobs`, `checkpoint_writes` и `checkpoint_migrations`:

```
checkpoints
├── thread_id    TEXT         ← thread_id = "{session_id}::{chat_id}"
├── checkpoint_ns TEXT
├── checkpoint_id UUID
├── parent_checkpoint_id UUID?
├── type         TEXT
├── metadata    JSONB
└── values      JSONB         ← Полное состояние графа (messages + config)
```

При перезагрузке страницы Chainlit вызывает `on_chat_resume`, который:
1. Извлекает `session_id` и `chat_id` из metadata треда
2. Восстанавливает `thread_id`
3. LangGraph загружает последний checkpoint по этому `thread_id`
4. Chainlit также загружает шаги (steps) из своей таблицы

## Требования

- Python 3.12+
- Docker (для PostgreSQL)
- Виртуальное окружение (рекомендуется)

## Установка

```bash
git clone <repo-url> && cd agent

python3 -m venv env
source env/bin/activate

pip install -r requirements.txt
pip install chainlit
```

## Настройка

Скопировать `.env.template` в `.env` и заполнить ключи:

```env
OLLAMA_API_KEY="your-ollama-api-key"
OLLAMA_CLOUD_MODEL="gemma4:31b-cloud"
OLLAMA_CLOUD_ENDPOINT="https://ollama.com"
TAVILY_API="your-tavily-api-key"

DB_URI="postgres://postgres:postgres@localhost:5432/postgres?sslmode=disable"

DEFAULT_TIMEZONE="Europe/Moscow"

CHAINLIT_AUTH_SECRET="your-secret-for-jwt-tokens"
CHAINLIT_DB_URI="postgresql+asyncpg://postgres:postgres@localhost:5432/chainlit"
```

### PostgreSQL

```bash
docker run -d --name my-postgres -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres
docker exec my-postgres psql -U postgres -c "CREATE DATABASE chainlit;"
```

## Запуск

### Chainlit UI

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

## Структура проекта

```
agent/
├── agents/
│   ├── __init__.py
│   ├── agents.py                  # AgentFabric (ABC)
│   └── default_agent.py           # DefaultAgentFactory + DEFAULT_SYSTEM_PROMPT
├── middleware/
│   ├── __init__.py
│   └── time_middleware.py         # DateTimeMiddleware
├── memory/
│   ├── __init__.py
│   ├── checkpointer.py            # CheckpointerFabric, create_checkpointer
│   ├── postgres.py                # FixedAsyncPostgresSaver
│   └── summary.py                 # SummaryMemoryMiddleware
├── models/
│   ├── __init__.py
│   ├── models.py                  # ModelFabric (ABC)
│   └── ollama_cloud.py            # OllamaCloudFactory
├── tools/
│   ├── __init__.py
│   └── tavily_tool.py             # create_tavily_search
├── chainlit_db/
│   ├── __init__.py
│   ├── init.py                    # init_chainlit_database
│   └── schema.py                  # CHAINLIT_SCHEMA_SQL
├── chainlit_app.py                # Точка входа Chainlit
├── main.py                        # Точка входа CLI
├── env/                           # Виртуальное окружение
├── .chainlit/config.toml          # Конфигурация Chainlit UI
├── .env                           # Конфигурация
└── chainlit.md                    # Welcome screen
```
