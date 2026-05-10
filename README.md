## Docker deploy

Deploy to the configured remote host:

`bash deploy/deploy.sh`

Optional variables:

- `SSH_TARGET` for custom ssh target.
- `REMOTE_DIR` for target directory on the server.
- `REMOTE_HOST` for host alias if needed.
# addres-to-ips

Скрипт для рекурсивного поиска IPv4-адресов, связанных с DNS-именем и доменами,
которые реально запрашиваются страницей в браузере. Для этого используется
`Playwright`, поэтому находятся не только ресурсы из исходного HTML, но и
поздние загрузки через JavaScript (`fetch`, `XHR`, lazy-load и подобное).

Резолв DNS-имен выполняется через публичные DNS-серверы `8.8.8.8` и `1.1.1.1`.

## Установка

Установка зависимостей:

```bash
uv sync
```

Установка браузера для `Playwright`:

```bash
PLAYWRIGHT_BROWSERS_PATH=0 uv run playwright install chromium
```

## Пример использования

Простой запуск:

```bash
PLAYWRIGHT_BROWSERS_PATH=0 uv run python main.py example.com
```

С дополнительными параметрами:

```bash
PLAYWRIGHT_BROWSERS_PATH=0 uv run python main.py https://www.example.com/ -t 5 -m 2 -w 3000 -o ip.txt -g 192.168.1.1
```

## API режим

Запуск `FastAPI` сервиса:

```bash
PLAYWRIGHT_BROWSERS_PATH=0 uv run uvicorn app:app --host 0.0.0.0 --port 8000
```

Проверка сервиса:

```bash
curl http://127.0.0.1:8000/health
```

Запрос на поиск IP:

```bash
curl -X POST http://127.0.0.1:8000/resolve \
  -H "Content-Type: application/json" \
  -d '{
    "dns": "https://openai.com",
    "timeout": 10,
    "max_depth": 1,
    "wait_after_load": 3000,
    "gateway": "10.0.0.18"
  }'
```

Пример ответа:

```json
{
  "hostname": "openai.com",
  "count": 2,
  "ips": [
    "104.18.33.45",
    "172.64.154.211"
  ],
  "routes": [
    "route add 104.18.33.45 mask 255.255.255.255 10.0.0.18",
    "route add 172.64.154.211 mask 255.255.255.255 10.0.0.18"
  ]
}
```

## Параметры

- `-t`, `--timeout` — таймаут загрузки страницы в секундах, по умолчанию `10`
- `-m`, `--max-depth` — максимальная глубина рекурсии по найденным доменам, по умолчанию `1`
- `-w`, `--wait-after-load` — сколько ждать после загрузки страницы в миллисекундах, чтобы успели выполниться поздние JS-запросы, по умолчанию `3000`
- `-o`, `--output` — файл для сохранения результата, по умолчанию вывод в `stdout`
- `-g`, `--gateway` — шлюз для `route add`, по умолчанию `10.0.0.18`

Параметры API `POST /resolve`:

- `dns` — DNS-имя или URL
- `timeout` — таймаут навигации в секундах
- `max_depth` — глубина рекурсии по найденным доменам
- `wait_after_load` — ожидание после загрузки страницы в миллисекундах
- `dns_server` — `both`, `google`, `cloudflare` или `custom`
- `custom_dns_server` — собственный DNS-сервер в виде IPv4-адреса, если выбран `custom`
- `gateway` — шлюз для генерации `route add`

## Что означает `-w 3000`

`-w 3000` означает: после основной загрузки страницы скрипт подождёт ещё `3000`
миллисекунд, то есть `3` секунды. Это нужно для сайтов, которые загружают
часть ресурсов не сразу, а чуть позже через JavaScript.

Например:

```bash
PLAYWRIGHT_BROWSERS_PATH=0 uv run python main.py openai.com -w 3000
```

## Формат вывода

Скрипт выводит команды для добавления маршрутов до найденных IP:

```text
route add 93.184.216.34 mask 255.255.255.255 10.0.0.18
route add 151.101.1.69 mask 255.255.255.255 10.0.0.18
...
```
