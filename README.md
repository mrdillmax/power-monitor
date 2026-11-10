# Power Monitor — автоматичне вимкнення розетки при відключенні мережі

## Як це працює
- GitHub Actions запускається кожні 10 хвилин (або вручну)
- Запитує Deye Cloud API токеном (`DEYE_TOKEN`)
- Якщо мережа пропадає — викликає Tuya Cloud API для вимкнення розетки
- Працює **без вашого ПК** — лише потрібен інтернет і GitHub акаунт

## Встановлення

### 1. Створіть репозиторій на GitHub
```bash
# Створіть новий репозиторій (публічний) через веб-інтерфейс
# Назва: power-monitor (або будь-яка)
# НЕ потрібні README, .gitignore, ліцензія — залиште порожнім
```

### 2. Додайте файли
```bash
# Скопіюйте вміст папки /tmp/opencode/Boiler у репозиторій
# Наприклад:
cp -r /tmp/opencode/Boiler/* /path/to/your/local/repo/
```

### 3. Зберігайте секрети в GitHub
Перейдіть до репозиторію → Settings → Secrets and variables → Actions → New repository secret

| Secret | Значення | Де взяти |
|--------|---------|-----------|
| `DEYE_TOKEN` | Bearer токен з Deye Cloud (EMEA) | `POST /v1.0/account/token?appId=...` з developer.deyecloud.com |
| `DEYE_DEVICE_SN` | `2509220055` | Скопіюйте з Deye Cloud → пристрої |
| `TUYA_DEVICE_ID` | `bf800fa90a4aebe7feenvx` | Знайдено раніше командою `tinytuya scan` |
| `TUYA_ACCESS_ID` | Access ID з Tuya Cloud | Tuya Cloud → Developer → Access ID |
| `TUYA_ACCESS_SECRET` | Access Secret з Tuya Cloud | Tuya Cloud → Developer → Access Secret |

### 4. Налаштуйте cron-job.org
1. Перейдіть на <https://console.cron-job.org> → створіть нове завдання → **Custom HTTP Request**
2. Налаштуйте:
   - **URL**: `https://raw.githubusercontent.com/yourusername/power-monitor/main/monitor.sh`
   - **Schedule**: `*/10 * * * *`
   - **Environment variables** (Advanced):
     - `DEYE_TOKEN`: значення з GitHub Secrets
     - `DEYE_DEVICE_SN`: `2509220055`
     - `TUYA_DEVICE_ID`: `bf800fa90a4aebe7feenvx`
     - `TUYA_ACCESS_ID`: значення з GitHub Secrets
     - `TUYA_ACCESS_SECRET`: значення з GitHub Secrets
     - `LOG_WEBHOOK`: (опціонально) webhook URL для логів
3. Збережіть.

## Тестування
- У GitHub: запустіть workflow вручну (`workflow_dispatch`).
- У cron-job.org: перегляньте логи останнього запуску.
- Якщо мережа пропадає → розетка вимкнеться, лог з'явиться у `power_monitor.log`.

## Примітка
- Токен дійсний 60 днів — оновіть `DEYE_TOKEN` в GitHub Secrets і запустіть workflow знову.
- Скрипт використовує `jq` і `curl` — вони є в стандартному образі Ubuntu.
