"""
Brain Router: Enrutador Inteligente de los 4 Cerebros con Control de Presupuesto
Prioridad máxima: Gemini Flash (Cerebro 2 - 0.00€) y DeepSeek API (Cerebro 3 - Código)
"""
import os
import sys
import json
import time
import requests
from typing import Optional, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / "config" / ".env"
load_dotenv(dotenv_path=env_path)

DAILY_BUDGET_EUR = float(os.getenv("DEEPSEEK_DAILY_BUDGET_EUR", "0.50"))
CURRENT_DAY_SPENT = 0.0
LAST_RESET_DAY = time.strftime("%Y-%m-%d")

STATE_FILE = Path(__file__).resolve().parent.parent / "memoria" / "estado" / "cerebro_activo.json"

def set_brain_state(brain: str, task_type: str, status: str = "activo"):
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "current_brain": brain,
            "task_type": task_type,
            "status": status,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[BrainRouter] Error guardando estado: {e}")

def reset_daily_budget_if_needed():
    global CURRENT_DAY_SPENT, LAST_RESET_DAY
    today = time.strftime("%Y-%m-%d")
    if today != LAST_RESET_DAY:
        CURRENT_DAY_SPENT = 0.0
        LAST_RESET_DAY = today

def compress_prompt(prompt: str) -> str:
    # Gemini Flash y modelos modernos disponen de ventana amplia gratuita; compresión CPU evitada
    return prompt

def query_gemini_flash(prompt: str, system: Optional[str] = None) -> Optional[str]:
    """Cerebro 2: Google Gemini Flash (0.00€ con Google AI Studio)"""
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    for model in ["gemini-3.6-flash", "gemini-3.7-flash", "gemini-3.8-flash"]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        text_content = f"{system}\n\n{prompt}" if system else prompt
        payload = {
            "contents": [{"parts": [{"text": text_content}]}],
            "generationConfig": {"temperature": 0.3}
        }
        try:
            r = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=30)
            if r.status_code == 200:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            elif r.status_code == 429:
                print(f"[BrainRouter Quota Exceeded] Gemini {model} límite temporal alcanzado.")
        except Exception:
            pass
    return None

def query_local_ollama(prompt: str, system: Optional[str] = None) -> str:
    """Cerebro 1: Obrero Local (GTX 1660) - 0.00€"""
    import litellm
    model = f"ollama/{os.getenv('OLLAMA_MODEL', 'qwen2.5-coder:7b-instruct-q4_K_S')}"
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
    Enrutamiento inteligente:
    1. Código pesado / Smart contracts (Dificultad >= 6): Cerebro 3 (DeepSeek API)
    2. Rutinas, síntesis, redacción, planificación: Cerebro 2 (Gemini Flash - 0.00€)
    3. Respaldo o sin internet: Cerebro 1 (Ollama GTX 1660 local)
    """
    global CURRENT_DAY_SPENT
    reset_daily_budget_if_needed()
    
    optimized_prompt = compress_prompt(prompt)
    
    # 1. Código pesado (Cerebro 3 - DeepSeek API)
    if task_type == "code" and difficulty >= 6:
        if CURRENT_DAY_SPENT < DAILY_BUDGET_EUR and os.getenv("DEEPSEEK_API_KEY"):
            try:
                set_brain_state("Cerebro 3 (DeepSeek API)", task_type, "procesando código")
                import litellm
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": optimized_prompt})
                
                response = litellm.completion(
                    model="deepseek/deepseek-chat",
                    messages=messages,
                    api_key=os.getenv("DEEPSEEK_API_KEY")
                )
                cost = response._hidden_params.get("response_cost", 0.002)
                CURRENT_DAY_SPENT += cost
                set_brain_state("Cerebro 1 (Ollama GTX 1660)", "vigilancia 24/7", "en espera")
                return {
                    "brain": "Cerebro 3 (DeepSeek API)",
                    "cost": cost,
                    "response": response.choices[0].message.content
                }
            except Exception:
                pass

    # 2. Motor principal: Gemini Flash (Cerebro 2 - 0.00€)
    set_brain_state("Cerebro 2 (Gemini Flash)", task_type, "procesando tarea")
    gemini_reply = query_gemini_flash(optimized_prompt, system_prompt)
    if gemini_reply:
        set_brain_state("Cerebro 1 (Ollama GTX 1660)", "vigilancia 24/7", "en espera")
        return {
            "brain": "Cerebro 2 (Gemini Flash)",
            "cost": 0.0,
            "response": gemini_reply
        }

    # 3. Fallback: Cerebro 1 (Obrero Local en GTX 1660)
    set_brain_state("Cerebro 1 (Ollama GTX 1660)", task_type, "procesando tarea local")
    try:
        reply = query_local_ollama(optimized_prompt, system_prompt)
        set_brain_state("Cerebro 1 (Ollama GTX 1660)", "vigilancia 24/7", "en espera")
        return {
            "brain": "Cerebro 1 (Ollama Qwen 2.5 Coder 7B)",
            "cost": 0.0,
            "response": reply
        }
    except Exception as e:
        set_brain_state("Cerebro 1 (Ollama GTX 1660)", "vigilancia 24/7", "error local")
        return {
            "brain": "Fallback",
            "cost": 0.0,
            "error": str(e),
            "response": "Error conectando con el modelo local. Verifica que Ollama esté en ejecución."
        }
