"""
Brain Router: Enrutador Inteligente Multi-IA con Control Atómico de Presupuesto (0.50 EUR/día).
Jerarquía adaptativa:
1. Gemini 2.5 Flash (0.00 EUR mientras dure la API gratuita; auto-desactivación limpia al expirar).
2. DeepSeek API (deepseek-chat / deepseek-reasoner) con tope estricto de 0.50 EUR/día y consulta de saldo real.
3. Ollama Local (GTX 1660) en reposo 0W, activado solo como respaldo de emergencia sin coste.
"""
import os
import json
import time
import tempfile
import threading
import urllib.request
from typing import Optional, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / "config" / ".env"
load_dotenv(dotenv_path=ENV_PATH)

STATE_DIR = BASE_DIR / "memoria" / "estado"
STATE_FILE = STATE_DIR / "cerebro_activo.json"
BUDGET_STATE_FILE = STATE_DIR / "deepseek_presupuesto.json"

DAILY_BUDGET_EUR = float(os.getenv("DEEPSEEK_DAILY_BUDGET_EUR", "0.50"))
USD_TO_EUR = 0.92

_budget_lock = threading.Lock()
_balance_cache = {"usd": None, "available": True, "ts": 0.0}
_gemini_disabled_until = 0.0
_gemini_status_note = "activo"


def _atomic_write_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise


def set_brain_state(brain: str, task_type: str, status: str = "activo"):
    try:
        _atomic_write_json(STATE_FILE, {
            "current_brain": brain,
            "task_type": task_type,
            "status": status,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        })
    except Exception:
        pass


def get_today_spent() -> float:
    today = time.strftime("%Y-%m-%d")
    if BUDGET_STATE_FILE.exists():
        try:
            data = json.loads(BUDGET_STATE_FILE.read_text(encoding="utf-8"))
            if data.get("date") == today:
                return float(data.get("spent_eur", 0.0))
        except Exception:
            pass
    return 0.0


def record_spending(cost_eur: float) -> Dict[str, Any]:
    with _budget_lock:
        today = time.strftime("%Y-%m-%d")
        spent = get_today_spent() + max(0.0, float(cost_eur))
        payload = {
            "date": today,
            "spent_eur": round(spent, 5),
            "daily_limit_eur": DAILY_BUDGET_EUR,
            "remaining_eur": round(max(0.0, DAILY_BUDGET_EUR - spent), 5),
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        _atomic_write_json(BUDGET_STATE_FILE, payload)
        return payload


def get_deepseek_real_balance(force: bool = False) -> Dict[str, Any]:
    """Consulta el saldo real disponible en DeepSeek API (cacheado 10 min)."""
    now = time.time()
    if not force and _balance_cache["usd"] is not None and (now - _balance_cache["ts"]) < 600:
        return {
            "balance_usd": _balance_cache["usd"],
            "balance_eur": round(_balance_cache["usd"] * USD_TO_EUR, 2),
            "is_available": _balance_cache["available"],
            "spent_today_eur": round(get_today_spent(), 4),
            "daily_limit_eur": DAILY_BUDGET_EUR
        }

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return {
            "balance_usd": 0.0,
            "balance_eur": 0.0,
            "is_available": False,
            "spent_today_eur": round(get_today_spent(), 4),
            "daily_limit_eur": DAILY_BUDGET_EUR
        }

    try:
        req = urllib.request.Request(
            "https://api.deepseek.com/user/balance",
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            infos = data.get("balance_infos", [])
            bal_usd = float(infos[0].get("total_balance", 0.0)) if infos else 0.0
            avail = bool(data.get("is_available", bal_usd > 0))
            _balance_cache["usd"] = bal_usd
            _balance_cache["available"] = avail
            _balance_cache["ts"] = now
    except Exception:
        if _balance_cache["usd"] is None:
            _balance_cache["usd"] = 0.0

    usd_val = _balance_cache["usd"] or 0.0
    return {
        "balance_usd": round(usd_val, 2),
        "balance_eur": round(usd_val * USD_TO_EUR, 2),
        "is_available": _balance_cache["available"],
        "spent_today_eur": round(get_today_spent(), 4),
        "daily_limit_eur": DAILY_BUDGET_EUR
    }


def get_gemini_status() -> Dict[str, Any]:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        return {"configured": False, "status": "no_configurada"}
    if time.time() < _gemini_disabled_until:
        return {"configured": True, "status": _gemini_status_note}
    return {"configured": True, "status": "activo (temporal)"}


def query_gemini_flash(prompt: str, system: Optional[str] = None) -> Optional[str]:
    """Cerebro 2: Gemini 2.5 Flash (0.00 EUR mientras la clave siga vigente)."""
    global _gemini_disabled_until, _gemini_status_note
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key or time.time() < _gemini_disabled_until:
        return None

    import requests
    text_content = f"{system}\n\n{prompt}" if system else prompt
    payload = {
        "contents": [{"parts": [{"text": text_content}]}],
        "generationConfig": {"temperature": 0.25}
    }

    for model in ("gemini-2.5-flash", "gemini-flash-latest"):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        try:
            r = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=25)
            if r.status_code == 200:
                candidates = r.json().get("candidates", [])
                if candidates:
                    _gemini_status_note = "activo"
                    return candidates[0]["content"]["parts"][0]["text"].strip()
            elif r.status_code in (401, 403):
                # Clave expirada o revocada: desactivar durante 6 horas para no perder tiempo
                _gemini_disabled_until = time.time() + 21600
                _gemini_status_note = "expirada_fallback_deepseek"
                return None
            elif r.status_code == 429:
                # Cuota temporal agotada: pausar 5 minutos
                _gemini_disabled_until = time.time() + 300
                _gemini_status_note = "cuota_pausada_5m"
                return None
        except Exception:
            continue
    return None


def query_deepseek(prompt: str, system: Optional[str] = None, reasoner: bool = False) -> Optional[Dict[str, Any]]:
    """Cerebro 3: DeepSeek V3 / R1 con control estricto de 0.50 EUR/día."""
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        return None
    if get_today_spent() >= DAILY_BUDGET_EUR:
        return None

    import litellm
    model = "deepseek/deepseek-reasoner" if reasoner else "deepseek/deepseek-chat"
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = litellm.completion(
        model=model,
        messages=messages,
        api_key=api_key,
        temperature=0.2 if not reasoner else 0.6
    )
    content = response.choices[0].message.content
    raw_cost_usd = float(response._hidden_params.get("response_cost") or 0.0015)
    cost_eur = raw_cost_usd * USD_TO_EUR
    record_spending(cost_eur)
    return {
        "brain": f"DeepSeek ({'R1' if reasoner else 'V3'})",
        "cost": round(cost_eur, 5),
        "response": content
    }


def query_local_ollama(prompt: str, system: Optional[str] = None) -> str:
    """Cerebro 1: Ollama Local (GTX 1660) — solo respaldo de emergencia a coste 0 EUR."""
    import litellm
    model = f"ollama/{os.getenv('OLLAMA_MODEL', 'qwen2.5-coder:7b')}"
    api_base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = litellm.completion(
        model=model,
        messages=messages,
        api_base=api_base,
        temperature=0.2
    )
    return response.choices[0].message.content


def route_task(task_type: str, prompt: str, difficulty: int = 3, system_prompt: Optional[str] = None) -> Dict[str, Any]:
    """
    Enrutador principal:
    - Tareas de código / análisis profundo (task_type=='code' o difficulty>=5): prioriza DeepSeek (tope 0.50 EUR/día).
    - Chat / clasificación / síntesis: usa Gemini 2.5 Flash gratis si sigue activa; si expiró, usa DeepSeek V3.
    - Respaldo final si se agota el presupuesto diario de 0.50 EUR: Ollama GTX 1660 local.
    """
    prefer_deepseek_first = (task_type == "code" or difficulty >= 5)

    if prefer_deepseek_first:
        try:
            set_brain_state("DeepSeek API", task_type, "generando solución")
            ds_res = query_deepseek(prompt, system_prompt, reasoner=(difficulty >= 8))
            if ds_res:
                set_brain_state("Sistema en Reposo (0W GPU)", "vigilancia", "en espera")
                return ds_res
        except Exception:
            pass

    # Intentar Gemini 2.5 Flash (0.00 EUR mientras dure)
    set_brain_state("Gemini 2.5 Flash", task_type, "procesando")
    gem_reply = query_gemini_flash(prompt, system_prompt)
    if gem_reply:
        set_brain_state("Sistema en Reposo (0W GPU)", "vigilancia", "en espera")
        return {
            "brain": "Gemini 2.5 Flash (0.00€)",
            "cost": 0.0,
            "response": gem_reply
        }

    # Si Gemini expiró/falló y aún no probamos DeepSeek, usar DeepSeek dentro del límite de 0.50 EUR/día
    if not prefer_deepseek_first:
        try:
            set_brain_state("DeepSeek API", task_type, "procesando")
            ds_res = query_deepseek(prompt, system_prompt, reasoner=False)
            if ds_res:
                set_brain_state("Sistema en Reposo (0W GPU)", "vigilancia", "en espera")
                return ds_res
        except Exception:
            pass

    # Último recurso: Ollama Local GTX 1660
    set_brain_state("Ollama Local (GTX 1660)", task_type, "respaldo local")
    try:
        reply = query_local_ollama(prompt, system_prompt)
        set_brain_state("Sistema en Reposo (0W GPU)", "vigilancia", "en espera")
        return {
            "brain": "Ollama Local (GTX 1660)",
            "cost": 0.0,
            "response": reply
        }
    except Exception as e:
        set_brain_state("Sistema en Reposo (0W GPU)", "vigilancia", "error IA")
        return {
            "brain": "Error",
            "cost": 0.0,
            "error": str(e),
            "response": f"No se pudo completar la consulta en ningún motor IA: {e}"
        }
