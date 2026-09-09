# МастерЧеб

Сайт-презентация и браузерная демонстрация ИИ-консультанта Маши, которая объясняет услуги МастерЧеб и собирает заявки для Александра Мастерова.

- Проект: `C:\ai26\MasterCheb`.
- Исходный проект: `C:\ai26\UmMachine_2` (сохранить отдельно).
- Сайт: https://mastercheb.ru
- Backend: https://api.mastercheb.ru
- Git: https://github.com/ChudoPes13/MasterCheb.git, ветка `main`.
- Frontend: React / TypeScript / Vite, `frontend/src`.
- Backend: FastAPI, `app`; база знаний: `docs/rag/mastercheb.jsonl`.

## Документы для продолжения

1. [AGENTS.md](AGENTS.md) — правила работы и согласованные требования.
2. [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md) — состояние, ограничения и задачи.
3. [docs/RUNBOOK.md](docs/RUNBOOK.md) — запуск, проверки и публикация.
4. [docs/NEXT_CHAT_PROMPT.md](docs/NEXT_CHAT_PROMPT.md) — промпт нового диалога.

## Быстрый запуск

На рабочем столе создан ярлык **«МастерЧеб — запуск backend»**. Он открывает консоль с логами. Остановка — Ctrl+C.

Из PowerShell:

```powershell
Set-Location C:\ai26\MasterCheb
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-backend.ps1
```

Для работы публичного API дополнительно нужны настроенный Nginx, сертификат, проброс портов и включённый ПК. Ярлык запускает локальную Ministral при свободном порте 8080, затем backend; Nginx не запускает.

## Локальная Маша

Три параллельных ответа с очередью до окончания озвучки. Голос включён по умолчанию. Подробная конфигурация, сценарий Б, проверки и ограничения — [LOCAL_LLM_PRODUCTION.md](docs/LOCAL_LLM_PRODUCTION.md).
