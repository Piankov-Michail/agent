# AI Agent with Web Search

LangChain-агент на Ollama Cloud с веб-поиском, памятью диалогов и веб-интерфейсом на Chainlit.

## Что это и зачем

Проект — шаблон AI-агента, который умеет:
- отвечать на вопросы (через LLM — языковую модель)
- искать свежую информацию в интернете (Tavily)
- помнить историю чата (даже после перезагрузки страницы)
- автоматически сжимать длинные диалоги в краткое содержание
- отображать ответы по-токенно (streaming) в веб-интерфейсе

Собран на **LangChain / LangGraph** — это стандартный фреймворк для сборки LLM-приложений.  
Код разбит на фабрики (Factory Pattern), чтобы можно было менять модель, базу данных или инструменты, не переписывая всё остальное.

---

## Как устроен агент (простыми словами)

Есть два файла, откуда всё стартует:

| Файл | Что делает |
|---|---|
| `chainlit_app.py` | Веб-интерфейс (запускается через `chainlit run`) |
| `main.py` | Консольный режим (просто ввод/вывод в терминале) |

Оба делают одно и то же: собирают агента из готовых блоков и запускают.

### Фабрики — что это

Каждый блок (модель, инструменты, память) создаётся через свою фабрику. Это просто класс, который возвращает готовый объект.

```
OllamaCloudFactory.get_model(...)   →  возвращает ChatOllama (языковую модель)
DefaultAgentFactory.get_agent(...)  →  возвращает собранного агента
create_checkpointer(...)            →  возвращает модуль памяти (Postgres или MemorySaver)
create_tavily_search(...)           →  возвращает инструмент поиска в интернете
```

**Зачем фабрики?** Чтобы можно было заменить Ollama на OpenAI или другую модель, просто написав новую фабрику, а не переписывая весь код агента.

### Как поменять провайдера

Сейчас модель — **Ollama Cloud** (можно запускать open-source модели удалённо).  
Чтобы переключиться на другую, нужно написать класс, наследующий `ModelFabric`, и вернуть в нём нужную модель LangChain (например, `ChatOpenAI`).

То же самое с памятью: сейчас используется PostgreSQL, но можно подключить SQLite или что угодно — достаточно реализовать `CheckpointerFabric`.

---

## Схема работы (упрощённо)

```mermaid
flowchart LR
    subgraph UI["Веб-интерфейс"]
        WC[Браузер] --> CA[Chainlit]
    end

    CA --> A[Агент]

    subgraph A[Агент = create_agent]
        DT["1. DateTimeMiddleware<br/>(вставляет текущее время)"]
        SM["2. SummaryMemoryMiddleware<br/>(сжимает историю если много сообщений)"]
        AGT["3. LLM + инструменты<br/>(Ollama + Tavily)"]
        DT --> SM --> AGT
    end

    A --> DB[(PostgreSQL)]
    DB --> CH[checkpoints + шаги + треды]
```

1. Пользователь пишет сообщение в чате
2. Chainlit получает его, находит `thread_id` (уникальный ID диалога)
3. Перед вызовом модели срабатывает **DateTimeMiddleware** — добавляет в контекст текущее время (чтобы модель знала, какой сегодня день)
4. Если диалог стал слишком длинным, **SummaryMemoryMiddleware** сжимает старые сообщения в краткое содержание
5. Модель генерирует ответ, агент может вызвать Tavily для поиска в интернете
6. Ответ по-токенно отправляется пользователю, а всё состояние сохраняется в PostgreSQL

---

## Память: как агент помнит историю

Два уровня сохранения (оба в PostgreSQL):

### 1. LangGraph Checkpointer

Сохраняет **всё состояние агента** после каждого шага (какие сообщения были, какие инструменты вызывались, какие промежуточные результаты получены).

```python
thread_id = "{session_id}::{chat_id}"
# session_id — кто пользователь (UUID)
# chat_id    — какой чат (UUID)
```

При перезагрузке страницы Chainlit находит `thread_id` в metadata треда, LangGraph загружает последний сохранённый checkpoint — и диалог продолжается с того же места.

### 2. Chainlit Data Layer

Сохраняет шаги (steps) — вызовы инструментов, ответы модели. Это нужно для отображения в UI (чтобы пользователь видел, как агент думал).

```mermaid
flowchart LR
    M[Сообщение] --> CP[LangGraph сохраняет checkpoint]
    M --> CL[Chainlit сохраняет step]
    CP --> DB1[(checkpoints таблицы)]
    CL --> DB2[(threads / steps таблицы)]
```

### SummaryMemoryMiddleware — сжатие истории

Без него диалог рос бы бесконечно, и каждый запрос к модели стоил бы всё дороже (и по времени, и по деньгам).

Порог срабатывания:
- Если сообщений стало больше **20** → старые (кроме последних **10**) отправляются модели на суммаризацию
- Модель пишет краткое содержание вроде: "Пользователь спросил про Х, я ответил Y"
- Старые сообщения удаляются, вместо них вставляется SystemMessage с этим содержанием

---

## Аутентификация

```python
@cl.password_auth_callback
async def auth_callback(username, password):
    return cl.User(identifier=username)
```

Любой логин/пароль пускает. Аутентификация отключается, если не задан `CHAINLIT_AUTH_SECRET`.

---

## Цикл чата (on_chat_start → on_message → on_chat_resume)

```mermaid
flowchart LR
    subgraph Start["Новый чат"]
        CS["on_chat_start"]
        CS --> S1[session_id = UUID]
        CS --> S2[chat_id = UUID]
        CS --> S3[thread_id = session_id::chat_id]
        CS --> S4[сохранить в user_session]
    end

    subgraph Resume["После перезагрузки"]
        CR["on_chat_resume"]
        CR --> R1[достать session_id из metadata треда]
        CR --> R2[достать chat_id из metadata треда]
        CR --> R3[восстановить thread_id]
    end

    subgraph Message["Ответ на сообщение"]
        OM["on_message"]
        OM --> M1[astream — отправка запроса модели]
        OM --> M2[stream_token — отправка токенов]
        OM --> M3[автосохранение в БД]
    end

    Start --> Message
    Resume --> Message
```

---

## DateTimeMiddleware — зачем агенту время

LLM знает только свою дату обучения. Без подсказки она не знает, какой сегодня день.

DateTimeMiddleware перед каждым ответом добавляет в начало списка сообщений SystemMessage с текущим временем:

```
Current date and time (internal context):
  UTC:  Monday, 2026-06-08 12:04:34 UTC
  Server: Monday, 2026-06-08 15:04:34 +0300
  User timezone: Europe/Moscow

(Не упоминай время в ответе, если пользователь не спросил)
```

Модель видит это время, может использовать для поиска "новости за сегодня", но не пишет "Сегодня 8 июня..." каждое сообщение (её просят этого не делать).

---

## Структура проекта

```
agent/
├── agents/                 # Фабрика агента
│   └── default_agent.py    #   собирает модель, инструменты, middleware в одного агента
├── models/                 # Фабрика языковой модели
│   └── ollama_cloud.py     #   ChatOllama с API-ключом
├── tools/                  # Инструменты агента
│   └── tavily_tool.py      #   поиск в интернете
├── middleware/              # Плагины, вставляемые до/после вызова модели
│   └── time_middleware.py   #   DateTimeMiddleware
├── memory/                 # Память диалогов
│   ├── checkpointer.py     #   выбор хранилища (Postgres / MemorySaver)
│   ├── postgres.py         #   сохранение в PostgreSQL
│   └── summary.py          #   SummaryMemoryMiddleware
├── chainlit_db/            # База данных для Chainlit (таблицы threads, steps)
│   ├── schema.py           #   SQL-схема
│   └── init.py             #   создание таблиц при старте
├── chainlit_app.py         # Точка входа — веб-интерфейс
├── main.py                 # Точка входа — консоль
├── .chainlit/config.toml   # Настройки Chainlit
└── .env                    # Ключи API, настройки БД
```

---

## База данных (PostgreSQL)

Две группы таблиц:

**Chainlit Data Layer** (создаются автоматически при запуске):

| Таблица | Хранит |
|---|---|
| `users` | Пользователи |
| `threads` | Треды (диалоги) |
| `steps` | Шаги (вызовы инструментов, ответы) |
| `elements` | Файлы, изображения |
| `feedbacks` | Оценки ответов |

**LangGraph Checkpointer** (создаются библиотекой LangGraph):

| Таблица | Хранит |
|---|---|
| `checkpoints` | Полное состояние графа |
| `checkpoint_writes` | Промежуточные записи |
| `checkpoint_blobs` | Большие объекты |
| `checkpoint_migrations` | Версии миграций |

---

## Установка и запуск

```bash
# 1. PostgreSQL через Docker
docker run -d --name my-postgres -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres
docker exec my-postgres psql -U postgres -c "CREATE DATABASE chainlit;"

# 2. Виртуальное окружение
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
pip install chainlit

# 3. .env файл (скопировать .env.template → .env, вставить ключи)

# 4. Запуск
chainlit run chainlit_app.py --port 8000
# или в консоли:
python3 main.py
```

### Переменные окружения (.env)

```env
OLLAMA_API_KEY="ключ от Ollama Cloud"
OLLAMA_CLOUD_MODEL="rnj-1:8b-cloud"        # какая модель
OLLAMA_CLOUD_ENDPOINT="https://ollama.com"
TAVILY_API="ключ от Tavily"                # поиск в интернете

DB_URI="postgres://postgres:postgres@localhost:5432/postgres?sslmode=disable"

DEFAULT_TIMEZONE="Europe/Moscow"           # часовой пояс (опционально)

CHAINLIT_AUTH_SECRET="секрет для JWT"      # если нужен логин/пароль
CHAINLIT_DB_URI="postgresql+asyncpg://postgres:postgres@localhost:5432/chainlit"
```
