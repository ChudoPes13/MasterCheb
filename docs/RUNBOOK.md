# Запуск, тестирование и публикация

## Backend с видимой консолью

Ярлык: `C:\Users\Master\Desktop\МастерЧеб — запуск backend.lnk`.

Он вызывает `scripts/start-backend.ps1`, который выбирает Python из `.venv`, затем `venv` проекта, затем резервный `C:\ai26\UmMachine_2\venv`. Последний путь существовал при проверке. Скрипт запускает `python -u -m scripts.run_backend`; параметры и .env загружаются через `app/config.py`.

Логи приложения и Uvicorn выводятся в консоль. Ctrl+C останавливает процесс. При занятом порте скрипт сообщает об этом, не завершает чужой процесс. Ярлык не запускает Nginx и не создаёт автозапуск.

```powershell
Set-Location C:\ai26\MasterCheb
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-backend.ps1
```

## Проверки

```powershell
Set-Location C:\ai26\MasterCheb
$env:PYTHONPATH = '.'
& 'C:\ai26\UmMachine_2\venv\Scripts\python.exe' -m pytest -q
```

```powershell
Set-Location C:\ai26\MasterCheb\frontend
npm run build
```

`scripts/verify_live.py` содержит дополнительные проверки текста/голоса. Перед запуском прочитать его: нужны работающий сервис и модели, тест может создавать сессии. Не путать успешную синтетическую проверку с тестом микрофона на Samsung S24.

С 9 сентября `pytest.ini` ограничивает сбор каталогом `tests/`: не запускать тесты сторонних библиотек из `outputs/`. Последний проверенный результат — 81 тест. Backend запускается ярлыком в Windows Terminal с заголовком `MasterCheb - Backend logs`; прогрев моделей выполняется после запуска HTTP, поэтому готовность текста и голоса проверять отдельно через `/health`.

Проверка произношения публичных фраз (аудио клиентов не читает):

```powershell
$env:PYTHONPATH = '.'
$env:PYTHONUTF8 = '1'
& 'C:\ai26\UmMachine_2\venv\Scripts\python.exe' -m scripts.audit_pronunciation --synthesize
& 'C:\ai26\UmMachine_2\venv\Scripts\python.exe' -m scripts.check_pronunciation_audio
```

Открыть `output/pronunciation-audit/index.html` для прослушивания. Синтез по умолчанию этого скрипта идёт на CPU; обратное распознавание использует настроенный Whisper. ASR не оценивает ударение и может добавлять собственные слова. Результаты не включать в Git и не копировать в публичный dist.

Проверять desktop и мобильный viewport, переполнение, контраст языка, раскрытый FAQ, онлайн/офлайн чат. Команды npm выполнять из frontend.

## Jino

1. Собрать frontend. Проверить содержимое `frontend/dist`.
2. Упаковать содержимое dist без внешней папки dist. Не включать backend, .env и сессии.
3. Через файловый менеджер Jino загрузить в `/domains/mastercheb.ru`, распаковать с перезаписью. Существующий `.htaccess` сначала изучить, если требуется его изменение.
4. Проверить права: каталоги 0755, статические файлы 0644. Ранее папка assets имела 0700 и вызывала 403. Не использовать 0777.
5. Получить публичный HTML, проверить актуальные имена JS/CSS и ответы 200 на них. Открыть сайт в браузере, проверить язык и интерфейс.
6. Frontend на Jino и локальный backend обновляются отдельно. При изменении Python/RAG перезапустить backend в его консоли и проверить API.

Архив `output/mastercheb-production.zip` — артефакт последней сборки, не гарантированно текущая версия. Перед публикацией пересобрать при изменении исходников.

## Git

Рабочая ветка main. Проверять `git status --short` и diff перед коммитом. Добавлять только относящиеся к задаче файлы; `outputs/` не включать автоматически. Push ранее разрешён для запрошенных изменений; документация сама по себе ещё не означает выполненный deploy.
