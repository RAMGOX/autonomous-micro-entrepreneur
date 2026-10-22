"""
Obsidian Memory Manager: Memoria persistente a largo plazo
"""
import os
import time
from pathlib import Path
from typing import List, Dict

BASE_DIR = Path(__file__).resolve().parent.parent
MEMORIA_DIR = BASE_DIR / "memoria"

def registrar_leccion(titulo: str, fallo: str, solucion: str, regla_futura: str):
    """
    Registra una lección aprendida para no volver a cometer el mismo error.
    """
    lecciones_dir = MEMORIA_DIR / "lecciones"
    lecciones_dir.mkdir(parents=True, exist_ok=True)
    
    fecha = time.strftime("%Y-%m-%d_%H%M%S")
    safe_title = "".join(c for c in titulo if c.isalnum() or c in (' ', '_', '-')).strip().replace(" ", "_")
    archivo = lecciones_dir / f"{fecha}_{safe_title}.md"
    
    contenido = f"""# Lección Aprendida: {titulo}
**Fecha:** {time.strftime('%Y-%m-%d %H:%M:%S')}

## 1. Qué falló
{fallo}

## 2. Solución aplicada
{solucion}

## 3. Regla para el futuro
> {regla_futura}
"""
    with open(archivo, "w", encoding="utf-8") as f:
        f.write(contenido)
    return str(archivo)

def registrar_estrategia(nombre: str, estado: str, descripcion: str, pasos: List[str]):
    """
    Registra una estrategia de generación de ingresos (activa, pausada o descartada).
    """
    estrategias_dir = MEMORIA_DIR / "estrategias"
    estrategias_dir.mkdir(parents=True, exist_ok=True)
    
    archivo = estrategias_dir / f"{nombre.lower().replace(' ', '_')}.md"
    pasos_md = "\n".join([f"- [ ] {p}" for p in pasos])
    
    contenido = f"""# Estrategia: {nombre}
**Estado:** {estado} (activa | pausada | descartada)
**Fecha:** {time.strftime('%Y-%m-%d %H:%M:%S')}

## Descripción
{descripcion}

## Plan de Ejecución
{pasos_md}
"""
    with open(archivo, "w", encoding="utf-8") as f:
        f.write(contenido)
    return str(archivo)

def actualizar_estado_diario(balance_eur: float, gasto_tokens_eur: float, resumen: str):
    """
    Actualiza el informe de estado diario en /memoria/estado.
    """
    estado_dir = MEMORIA_DIR / "estado"
    estado_dir.mkdir(parents=True, exist_ok=True)
    
    fecha = time.strftime("%Y-%m-%d")
    archivo = estado_dir / f"estado_{fecha}.md"
    
    contenido = f"""# Estado Diario: {fecha}
- **Balance Capital:** {balance_eur:.2f} €
- **Gasto en Tokens Hoy:** {gasto_tokens_eur:.4f} €
- **Última Actualización:** {time.strftime('%H:%M:%S')}

## Resumen de Actividad
{resumen}
"""
    with open(archivo, "w", encoding="utf-8") as f:
        f.write(contenido)
    return str(archivo)

def obtener_ultimas_lecciones(limite: int = 5) -> List[str]:
    """
    Lee las últimas lecciones registradas para inyectarlas como contexto en el agente.
    """
    lecciones_dir = MEMORIA_DIR / "lecciones"
    if not lecciones_dir.exists():
        return []
    archivos = sorted(lecciones_dir.glob("*.md"), reverse=True)[:limite]
    lecciones = []
    for a in archivos:
        try:
            with open(a, "r", encoding="utf-8") as f:
                lecciones.append(f.read())
        except Exception:
            pass
    return lecciones
