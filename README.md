# Power Monitor

Автоматичне керування Tuya-розеткою залежно від наявності **вхідної мережі (grid)** на інверторі Deye.

Працює повністю в хмарі: GitHub Actions + Deye Cloud API + Tuya Cloud API.
Локальний ПК, сервер чи відкриті порти не потрібні.

## Логіка

1. Кожні 30 хвилин `cron-job.org` викликає GitHub Actions через API (`workflow_dispatch`).
2. Workflow запускає `monitor.py`.
3. `monitor.py` читає з Deye Cloud напругу/частоту мережі (`gridVoltageL1`, `gridFrequency`).
4. Якщо мережа **є** → розетка вмикається (`switch_1 = true`).
5. Якщо мережа **відсутня** → розетка вимикається (`switch_1 = false`).

Стан розетки спершу читається, тож зайвих перемикань немає.

## Секрети репозиторію

`Settings → Secrets and variables → Actions`:

| Секрет | Обов'язковий | Опис |
|---|---|---|
| `DEYE_TOKEN` | так* | Bearer-токен Deye Cloud |
| `DEYE_DEVICE_SN` | так | Серійний номер інвертора (`2509220055`) |
| `TUYA_ACCESS_ID` | так | Tuya Cloud Access ID |
| `TUYA_ACCESS_SECRET` | так | Tuya Cloud Access Secret |
| `TUYA_DEVICE_ID` | так | ID розетки |
| `DEYE_URL` | ні | База API, за замовчуванням `https://eu1-developer.deyecloud.com/v1.0` |
| `TUYA_REGION` | ні | Регіон Tuya, за замовчуванням `eu` |
| `DEYE_APP_ID` | ні* | AppId додатку Deye |
| `DEYE_APP_SECRET` | ні* | AppSecret додатку Deye |
| `DEYE_EMAIL` | ні* | Email акаунта Deye |
| `DEYE_PASSWORD` | ні* | Пароль акаунта Deye |

\* Токен Deye живе ~60 днів. Щоб не оновлювати його вручну, додайте
`DEYE_APP_ID`, `DEYE_APP_SECRET`, `DEYE_EMAIL`, `DEYE_PASSWORD` — скрипт сам
отримуватиме свіжий токен при кожному запуску.

## Запуск вручну

Actions → **Power Monitor** → **Run workflow**.
Поле `force_action` дозволяє примусово перевірити керування розеткою:

- `none` — звичайна логіка (за мережею)
- `on` — примусово увімкнути розетку
- `off` — примусово вимкнути розетку

## Стабільний розклад через cron-job.org

Вбудований `schedule` у GitHub може затримуватись і вимикається після 60 днів
неактивності. Тому основний тригер — зовнішній.

1. Створіть **fine-grained PAT**: GitHub → Settings → Developer settings →
   Personal access tokens → Fine-grained tokens.
   Repository access: `mrdillmax/power-monitor`.
   Permissions: **Actions → Read and write** (`actions:write`).

2. На [cron-job.org](https://console.cron-job.org) створіть завдання:

   - **URL**
     ```
     https://api.github.com/repos/mrdillmax/power-monitor/actions/workflows/power-monitor.yml/dispatches
     ```
   - **Schedule**: Every 30 minutes
   - **Request method**: `POST`
   - **Request body**
     ```json
     {"ref":"main"}
     ```
   - **Headers**
     ```
     Authorization: Bearer <ВАШ_GITHUB_PAT>
     Accept: application/vnd.github.v3+json
     User-Agent: cronjob
     ```
   - **Content-Type**: `application/json`

3. Натисніть **Test run** — у відповіді має бути HTTP `204 No Content`.

## Діагностика

- Логи кожного запуску: Actions → потрібний run → **Run monitor**.
- Повний лог також зберігається в артефакті `power-monitor-log`.
- Якщо Deye не відповідає — workflow завершується помилкою і **не** змінює
  стан розетки (щоб не вимкнути її через збій API).

## Файли

- `monitor.py` — основна логіка
- `.github/workflows/power-monitor.yml` — workflow
