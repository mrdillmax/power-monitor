#!/usr/bin/env python3
"""
Power Monitor: перевіряє наявність мережі (grid) через Deye Cloud API
і керує Tuya-розеткою через Tuya Cloud API.

Працює повністю в хмарі (GitHub Actions) — локальна мережа не потрібна.

Змінні оточення:
  DEYE_TOKEN          Bearer токен Deye Cloud (або див. нижче)
  DEYE_APP_ID         AppId додатку Deye (необов'язково, для автооновлення токена)
  DEYE_APP_SECRET     AppSecret додатку Deye
  DEYE_EMAIL          email акаунта Deye
  DEYE_PASSWORD       пароль акаунта Deye (звичайний, хешується в скрипті)
  DEYE_SN             серійний номер інвертора
  DEYE_BASE           базовий URL (default https://eu1-developer.deyecloud.com/v1.0)
  TUYA_ACCESS_ID      Tuya Cloud Access ID
  TUYA_ACCESS_SECRET  Tuya Cloud Access Secret
  TUYA_DEVICE_ID      ID розетки
  TUYA_REGION         регіон Tuya (default eu)
  FORCE_ACTION        on|off|none (для тестів, ігнорує стан мережі)
"""

import json
import os
import sys
import hashlib
import urllib.request
import urllib.error

DEYE_TOKEN = os.environ.get("DEYE_TOKEN", "").strip()
DEYE_SN = os.environ.get("DEYE_SN", "").strip()
DEYE_BASE = (os.environ.get("DEYE_BASE", "").strip() or "https://eu1-developer.deyecloud.com/v1.0").rstrip("/")

# Необов'язково: автоматичне оновлення токена (щоб не робити це вручну кожні 60 днів)
DEYE_APP_ID = os.environ.get("DEYE_APP_ID", "").strip()
DEYE_APP_SECRET = os.environ.get("DEYE_APP_SECRET", "").strip()
DEYE_EMAIL = os.environ.get("DEYE_EMAIL", "").strip()
DEYE_PASSWORD = os.environ.get("DEYE_PASSWORD", "").strip()

TUYA_ACCESS_ID = os.environ.get("TUYA_ACCESS_ID", "").strip()
TUYA_ACCESS_SECRET = os.environ.get("TUYA_ACCESS_SECRET", "").strip()
TUYA_DEVICE_ID = os.environ.get("TUYA_DEVICE_ID", "").strip()
TUYA_REGION = os.environ.get("TUYA_REGION", "").strip() or "eu"
FORCE_ACTION = os.environ.get("FORCE_ACTION", "").strip()

UA = "GitHubActions/1.0"


def http(method, url, token=None, body=None, timeout=20, extra_headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("User-Agent", UA)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    for k, v in (extra_headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
            return r.status, raw
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return None, f"EXCEPTION: {type(e).__name__}: {e}"


def get_deye_token():
    """Повертає дійсний токен Deye. Якщо є appId/appSecret/email/password —
    отримує свіжий токен, інакше використовує готовий DEYE_TOKEN."""
    if DEYE_APP_ID and DEYE_APP_SECRET and DEYE_EMAIL and DEYE_PASSWORD:
        print("Оновлюю токен Deye через appId/email...")
        pwd_hash = hashlib.sha256(DEYE_PASSWORD.encode("utf-8")).hexdigest()
        status, raw = http(
            "POST",
            f"{DEYE_BASE}/account/token?appId={DEYE_APP_ID}",
            None,
            {
                "appSecret": DEYE_APP_SECRET,
                "email": DEYE_EMAIL,
                "password": pwd_hash,
            },
        )
        if status == 200:
            try:
                j = json.loads(raw)
                tok = (j.get("accessToken") or "").strip()
                if tok:
                    print(f"✅ Отримано новий токен (len={len(tok)})")
                    return tok
            except Exception:
                pass
        print(f"⚠️ Не вдалося оновити токен (HTTP {status}): {raw[:300]}")
        print("   Використовую DEYE_TOKEN із секретів.")
    return DEYE_TOKEN


def try_deye_endpoints(token):
    """Пробує різні варіанти ендпоінту Deye, повертає (endpoint_name, data_list)."""
    variants = [
        (
            "POST /device/latest",
            lambda: http("POST", f"{DEYE_BASE}/device/latest", token,
                         {"deviceList": [DEYE_SN]}),
        ),
        (
            "POST /device/v1.0/currentData",
            lambda: http("POST", f"{DEYE_BASE}/device/v1.0/currentData", token,
                         {"deviceSn": DEYE_SN}),
        ),
        (
            "POST /device/currentData",
            lambda: http("POST", f"{DEYE_BASE}/device/currentData", token,
                         {"deviceSn": DEYE_SN}),
        ),
        (
            "GET /device/v1.0/currentData?deviceSn=",
            lambda: http("GET", f"{DEYE_BASE}/device/v1.0/currentData?deviceSn={DEYE_SN}", token),
        ),
        (
            "GET /device/currentData?deviceSn=",
            lambda: http("GET", f"{DEYE_BASE}/device/currentData?deviceSn={DEYE_SN}", token),
        ),
    ]

    for name, fn in variants:
        status, raw = fn()
        print(f"\n--- Deye {name} -> HTTP {status}")
        print(raw[:600])
        if status != 200:
            continue
        try:
            j = json.loads(raw)
        except Exception:
            print("  (не JSON)")
            continue
        if j.get("success") is False:
            print("  success=false")
            continue
        dl = extract_data_list(j)
        if dl:
            return name, dl
    return None, None


def extract_data_list(j):
    """Дістає список {key,value,unit,name} з різних форматів відповіді."""
    candidates = []
    if isinstance(j, dict):
        for k in ("deviceDataList", "dataList", "data", "result"):
            v = j.get(k)
            if isinstance(v, list):
                candidates.append(v)
            elif isinstance(v, dict):
                for kk in ("dataList", "deviceDataList"):
                    if isinstance(v.get(kk), list):
                        candidates.append(v[kk])
    for lst in candidates:
        if lst and isinstance(lst[0], dict) and ("value" in lst[0] or "key" in lst[0]):
            return lst
        # deviceDataList: [{deviceSn, dataList:[...]}]
        if lst and isinstance(lst[0], dict) and "dataList" in lst[0]:
            inner = lst[0]["dataList"]
            if isinstance(inner, list):
                return inner
    return None


def pick(items, *needles, max_value=None):
    """Знаходить перше значення, де key/name містить усі needles (без регістру)."""
    for it in items:
        hay = f"{it.get('key','')} {it.get('name','')}".lower()
        if all(n.lower() in hay for n in needles):
            try:
                val = float(it.get("value"))
            except Exception:
                continue
            if max_value is not None and val > max_value:
                continue
            return val
    return None


def analyze_grid(items):
    print("\n=== Дані інвертора ===")
    for it in items:
        print(f"  {it.get('key',''):28} {str(it.get('value','')):>10} {it.get('unit','')}  {it.get('name','')}")

    # 1) точні ключі Deye Cloud: gridVoltageL1 / gridFrequency
    #    max_value відсікає службові поля (наприклад, накопичену енергію)
    v = pick(items, "grid", "voltage", max_value=1000)
    f = pick(items, "grid", "freq", max_value=100)
    # 2) загальніші варіанти
    if v is None:
        v = pick(items, "gridvolt", max_value=1000) or pick(items, "ac", "input", "voltage", max_value=1000)
    if f is None:
        f = pick(items, "gridfreq", max_value=100) or pick(items, "ac", "input", "freq", max_value=100)

    print(f"\nGrid voltage: {v}   Grid frequency: {f}")

    if v is None and f is None:
        # Дані від інвертора є, але полів мережі немає — найімовірніше,
        # інвертор не бачить вхідної мережі (або вона фізично відсутня).
        print("⚠️ Полів напруги/частоти мережі немає у відповіді.")
        return False

    grid_ok = (v is not None and v > 100) or (f is not None and f > 40)
    return grid_ok


def tuya_command(device_id, turn_on):
    try:
        import tinytuya
    except ImportError:
        print("❌ tinytuya не встановлено")
        sys.exit(1)

    c = tinytuya.Cloud(apiRegion=TUYA_REGION, apiKey=TUYA_ACCESS_ID, apiSecret=TUYA_ACCESS_SECRET)
    code = "switch_1"

    # Поточний стан — щоб не смикати розетку даремно
    state = None
    try:
        st = c.getstatus(device_id)
        for item in (st or {}).get("result", []):
            if item.get("code") == code:
                state = item.get("value")
                break
        print(f"Поточний стан розетки: {code}={state}")
    except Exception as e:
        print(f"(не вдалося прочитати стан: {e})")

    if state is not None and bool(state) == bool(turn_on):
        print(f"Розетка вже {'ON' if turn_on else 'OFF'} — змін не потрібно.")
        return True

    payload = [{"code": code, "value": bool(turn_on)}]
    res = c.sendcommand(device_id, payload)
    print(f"Tuya {'ON' if turn_on else 'OFF'} -> {json.dumps(res, ensure_ascii=False)[:300]}")
    return bool(isinstance(res, dict) and res.get("success"))


def main():
    missing = [n for n, v in [
        ("DEYE_SN", DEYE_SN),
        ("TUYA_ACCESS_ID", TUYA_ACCESS_ID),
        ("TUYA_ACCESS_SECRET", TUYA_ACCESS_SECRET),
        ("TUYA_DEVICE_ID", TUYA_DEVICE_ID),
    ] if not v]
    can_refresh = all([DEYE_APP_ID, DEYE_APP_SECRET, DEYE_EMAIL, DEYE_PASSWORD])
    if not DEYE_TOKEN and not can_refresh:
        missing.append("DEYE_TOKEN (або DEYE_APP_ID/DEYE_APP_SECRET/DEYE_EMAIL/DEYE_PASSWORD)")
    if missing:
        print("❌ Відсутні змінні: " + ", ".join(missing))
        sys.exit(1)

    token = get_deye_token()
    if not token:
        print("❌ Немає токена Deye.")
        sys.exit(1)

    print(f"Deye: base={DEYE_BASE} sn={DEYE_SN} token_len={len(token)}")
    print(f"Tuya: region={TUYA_REGION} device={TUYA_DEVICE_ID}")

    name, items = try_deye_endpoints(token)
    if not items:
        print("\n❌ Не вдалося отримати дані з жодного ендпоінту Deye.")
        sys.exit(1)

    print(f"\n✅ Робочий ендпоінт: {name}")
    grid_ok = analyze_grid(items)

    print(f"\nМережа: {'Є' if grid_ok else 'ВІДСУТНЯ'}")

    if FORCE_ACTION in ("on", "off"):
        want_on = FORCE_ACTION == "on"
        print(f"⚠️ FORCE_ACTION={FORCE_ACTION} — примусове керування")
    else:
        want_on = grid_ok

    ok = tuya_command(TUYA_DEVICE_ID, want_on)
    print("\nГотово." if ok else "\n⚠️ Tuya повернула помилку.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
