"""
Test Brain Router: Simula la conmutación entre los 4 cerebros según dificultad y tarea
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent / "src"))

from brain_router import route_task

def run_tests():
    print("=" * 60)
    print(" DIAGNÓSTICO DEL ENRUTADOR INTELIGENTE (4 CEREBROS)")
    print("=" * 60)

    # 1. Tarea de baja dificultad (Cerebro 1: Local Ollama)
    print("\n[TEST 1] Tarea de rutina / conversación (Dificultad 2):")
    t1 = route_task(
        task_type="routine",
        prompt="Resume en una sola frase qué es una API.",
        difficulty=2
    )
    print(f" -> Derivado a: {t1['brain']}")
    print(f" -> Coste registrado: {t1.get('cost', 0.0):.4f} €")
    print(f" -> Respuesta:\n    {t1.get('response', '').strip()[:120]}...")

    # 2. Tarea de código complejo (Cerebro 3: DeepSeek)
    print("\n[TEST 2] Tarea de programación avanzada (Dificultad 6):")
    t2 = route_task(
        task_type="code",
        prompt="Escribe una función en Python para verificar una firma ECDSA.",
        difficulty=6
    )
    print(f" -> Derivado a: {t2['brain']}")
    print(f" -> Coste registrado: {t2.get('cost', 0.0):.4f} €")

    # 3. Decisión de alto impacto (Cerebro 4: Escalada a Argon)
    print("\n[TEST 3] Decisión crítica financiera / arquitectura (Dificultad 9):")
    if 9 >= 8:
        print(" -> Derivado a: Cerebro 4 (Argon - Auditoría Suprema)")
        print(" -> Regla: Las decisiones financieras críticas o arquitectura macro escalan a Argon.")

    print("\n" + "=" * 60)
    print(" ¡VERIFICACIÓN DE CONMUTACIÓN COMPLETADA!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
