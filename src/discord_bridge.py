# -*- coding: utf-8 -*-
"""
Discord Bridge: Canal bidireccional UTF-8 puro entre el Cerebro Central y el Usuario en Discord.
"""
import os
import json
import time
import urllib.request
from pathlib import Path
from typing import Optional, Dict, Any, List

try:
    import requests
except ImportError:
    requests = None

try:
    from dotenv import load_dotenv
    load_dotenv_avail = True
except ImportError:
    load_dotenv_avail = False

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / "config" / ".env"
MEMORIA_DIR = BASE_DIR / "memoria" / "estado"
MEMORIA_DIR.mkdir(parents=True, exist_ok=True)

if load_dotenv_avail:
    load_dotenv(dotenv_path=ENV_PATH)
elif ENV_PATH.exists():
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GENERAL_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID_GENERAL", "1562602374298599476")
DASHBOARD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID_DASHBOARD", "1562602493148405830")
AUTHORIZED_USER_ID = os.getenv("DISCORD_AUTHORIZED_USER_ID", "637624631960010782")

PENDING_QUESTION_FILE = MEMORIA_DIR / "esperando_usuario.json"
ORDERS_QUEUE_FILE = MEMORIA_DIR / "cola_ordenes.json"
ORDERS_HISTORY_FILE = MEMORIA_DIR / "historial_ordenes.md"


def notify_user_discord(content: str, title: Optional[str] = None, color: int = 0x3498db, channel: str = "dashboard") -> bool:
    """Envía un mensaje en UTF-8 puro garantizado a Discord."""
    if not BOT_TOKEN:
        return False

    target_channel_id = DASHBOARD_CHANNEL_ID if channel == "dashboard" else GENERAL_CHANNEL_ID
    if not target_channel_id:
        target_channel_id = GENERAL_CHANNEL_ID

    url = f"https://discord.com/api/v10/channels/{target_channel_id}/messages"
    headers = {
        "Authorization": f"Bot {BOT_TOKEN}",
        "Content-Type": "application/json; charset=utf-8"
    }

    payload: Dict[str, Any] = {}
    if title:
        payload["embeds"] = [{
            "title": title,
            "description": content,
            "color": color,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }]
    else:
        payload["content"] = content

    try:
        raw_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if requests is not None:
            res = requests.post(url, headers=headers, data=raw_bytes, timeout=10)
            return res.status_code in (200, 201)
        else:
            req = urllib.request.Request(url, data=raw_bytes, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status in (200, 201)
    except Exception as e:
        print(f"[Bridge Error] Fallo al notificar a Discord: {e}")
        return False


def ask_user_discord(question: str) -> bool:
    data = {
        "id": f"q_{int(time.time())}",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "question": question,
        "status": "pending",
        "answer": None
    }
    with open(PENDING_QUESTION_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    mention = f"<@{AUTHORIZED_USER_ID}> " if AUTHORIZED_USER_ID else ""
    msg = (
        f"{mention}🧠 **CONSULTA DEL CEREBRO CENTRAL:**\n\n"
        f"{question}\n\n"
        f"*Responde directamente a este mensaje en Discord para que el Cerebro continúe.*"
    )
    return notify_user_discord(msg)


def check_active_question() -> Optional[Dict[str, Any]]:
    if not PENDING_QUESTION_FILE.exists():
        return None
    try:
        with open(PENDING_QUESTION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def resolve_active_question(answer: str) -> bool:
    q = check_active_question()
    if not q or q.get("status") != "pending":
        return False

    q["status"] = "answered"
    q["answer"] = answer
    q["answered_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    with open(PENDING_QUESTION_FILE, "w", encoding="utf-8") as f:
        json.dump(q, f, ensure_ascii=False, indent=2)

    with open(ORDERS_HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n### [{q['answered_at']}] Respuesta a consulta\n")
        f.write(f"- **Pregunta:** {q['question']}\n")
        f.write(f"- **Respuesta de Usuario:** {answer}\n")

    return True


def push_order(order_text: str, source: str = "discord") -> Dict[str, Any]:
    orders = []
    if ORDERS_QUEUE_FILE.exists():
        try:
            with open(ORDERS_QUEUE_FILE, "r", encoding="utf-8") as f:
                orders = json.load(f)
        except Exception:
            orders = []

    order = {
        "id": f"ord_{int(time.time())}",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": source,
        "text": order_text,
        "status": "pending"
    }
    orders.append(order)

    with open(ORDERS_QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)

    with open(ORDERS_HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n### [{order['timestamp']}] Nueva orden recibida ({source})\n")
        f.write(f"- **Instrucción:** {order_text}\n")
        f.write(f"- **Estado:** Pendiente\n")

    return order


def pop_pending_orders() -> List[Dict[str, Any]]:
    if not ORDERS_QUEUE_FILE.exists():
        return []
    try:
        with open(ORDERS_QUEUE_FILE, "r", encoding="utf-8") as f:
            orders = json.load(f)
    except Exception:
        return []

    pending = [o for o in orders if o.get("status") == "pending"]
    for o in pending:
        o["status"] = "in_progress"

    with open(ORDERS_QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)

    return pending


def complete_order(order_id: str, result_text: str = "") -> bool:
    if not ORDERS_QUEUE_FILE.exists():
        return False
    try:
        with open(ORDERS_QUEUE_FILE, "r", encoding="utf-8") as f:
            orders = json.load(f)
    except Exception:
        return False

    found = False
    for o in orders:
        if o.get("id") == order_id:
            o["status"] = "completed"
            o["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            o["result"] = result_text
            found = True
            break

    if found:
        with open(ORDERS_QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(orders, f, ensure_ascii=False, indent=2)

        with open(ORDERS_HISTORY_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n### [{time.strftime('%Y-%m-%d %H:%M:%S')}] Orden completada ({order_id})\n")
            f.write(f"- **Resultado:** {result_text}\n")
    return found
