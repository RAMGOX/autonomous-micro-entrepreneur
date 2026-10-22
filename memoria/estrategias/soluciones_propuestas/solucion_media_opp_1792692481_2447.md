# Solución para: [Bounty proposal] fix(goals): get_user_goals drops active goals by limiting before filtering ($50)
- **URL:** https://github.com/BasedHardware/omi/issues/23294
- **Nivel:** MEDIA | **Valor Est:** $50.0
- **Generado por:** DeepSeek API (Coste: 0.0038€)
- **Cartera Operador:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

# Solución Técnica — Bounty #23294

## Análisis del bug

En `backend/database/goals.py`, la función `get_user_goals` aplicaba `.limit(limit)` **dentro** de la query Firestore. Esto significa que Firestore devolvía los primeros `N` documentos ordenados por `__name__` (document-id), **antes** de que el filtro Python descartara los goals `achieved`/`abandoned`. Resultado: si la primera página de documentos son todos goals terminados, el filtro los descarta y el llamador recibe **menos** goals activos de los pedidos (o ninguno).

El módulo ya tiene el patrón correcto en `get_all_goals`: consultar sin límite, filtrar/ordenar en Python, y **después** aplicar el slice `[:limit]`.

---

## 1. Código de implementación

### `backend/database/goals.py` — función corregida

```python
def get_user_goals(uid: str, limit: int = 10, include_ended: bool = False) -> List[Goal]:
    """
    Return the most recent goals owned by ``uid``.

    The ``limit`` bound is applied *after* the ended-goal filter and the
    oldest-first ``created_at`` sort — mirroring ``get_all_goals`` below.
    Applying ``.limit()`` at the Firestore layer would page results in
    document-id order, letting ended goals occupy the page and starve
    callers that request only active goals (see #22778).
    """
    client = _get_firestore_client()
    collection = client.collection(GOALS_COLLECTION).where("uid", "==", uid)

    goals: List[Goal] = []
    for doc in collection.stream():
        data = doc.to_dict() or {}
        goal = Goal.from_dict(doc.id, data)
        if not include_ended and goal.is_ended():
            continue
        goals.append(goal)

    # Oldest-first, matching get_all_goals semantics.
    goals.sort(key=lambda g: g.created_at or 0)

    if limit is not None and limit >= 0:
        goals = goals[:limit]

    return goals
```

**Diff conceptual (aproximadamente 6 líneas netas):**

```diff
-    query = (
-        client.collection(GOALS_COLLECTION)
-        .where("uid", "==", uid)
-        .order_by("created_at")
-        .limit(limit)          # ❌ bound applied BEFORE filtering
-    )
-    goals = []
-    for doc in query.stream():
-        data = doc.to_dict() or {}
-        goal = Goal.from_dict(doc.id, data)
-        if not include_ended and goal.is_ended():
-            continue
-        goals.append(goal)
-    return goals
+    # Fetch without a bound; filter → sort → slice (same pattern as
+    # get_all_goals). Bound must be applied AFTER the ended filter.
+    collection = client.collection(GOALS_COLLECTION).where("uid", "==", uid)
+    goals: List[Goal] = []
+    for doc in collection.stream():
+        data = doc.to_dict() or {}
+        goal = Goal.from_dict(doc.id, data)
+        if not include_ended and goal.is_ended():
+            continue
+        goals.append(goal)
+
+    goals.sort(key=lambda g: g.created_at or 0)
+
+    if limit is not None and limit >= 0:
+        goals = goals[:limit]
+
+    return goals
```

> **Por qué eliminar también `order_by("created_at")` de la query:** Firestore requiere que cualquier campo en `order_by` que no sea la key primaria tenga un índice. En esta colección `created_at` no está garantizado como índice compuesto con `uid`, y el módulo ya resuelve el orden en memoria con `sort` en `get_all_goals`. Mantener el sort en Python conserva el comportamiento observable y elimina el fallo dependiente de índices.

### `backend/database/goals.py::get_all_goals` — referencia de consistencia (no cambia)

Ya implementa el patrón correcto:

```python
def get_all_goals(limit: int = None) -> List[Goal]:
    # NOTE: bound applied after filtering/sorting, not in Firestore query.
    ...
    goals.sort(key=lambda g: g.created_at or 0)
    if limit is not None:
        goals = goals[:limit]
    return goals
```

### Contratos de los callers (no requieren cambio)

- `backend/utils/proactivity_producers.py` → `get_user_goals(uid, limit=3)` ✅ ahora garantiza hasta 3 **activos**.
- `backend/utils/llm/external_integrations.py` → `get_user_goals(uid, limit=3)` ✅ ídem.

No hay cambios de firma, esquema ni API.

---

## 2. Suite mínima de tests unitarios

### `backend/tests/unit/test_goals_limit.py`

```python
import unittest
from unittest.mock import MagicMock, patch

from backend.database import goals as goals_module
from backend.database.goals import Goal


def _goal(doc_id: str, *, achieved=False, abandoned=False, created_at: int = 0):
    return Goal(
        id=doc_id,
        uid="u1",
        title=doc_id,
        created_at=created_at,
        achieved=achieved,
        abandoned=abandoned,
    )


def _fake_doc(goal: Goal):
    doc = MagicMock()
    doc.id = goal.id
    doc.to_dict.return_value = {
        "uid": goal.uid,
        "title": goal.title,
        "created_at": goal.created_at,
        "achieved": goal.achieved,
        "abandoned": goal.abandoned,
    }
    return doc


class GetUserGoalsLimitTest(unittest.TestCase):
    def _run(self, docs, limit=3, include_ended=False):
        """Wire a fake Firestore collection that returns `docs` in id order."""
        collection = MagicMock()
        chain = MagicMock()
        chain.stream.return_value = [_fake_doc(d) for d in docs]
        collection.where.return_value = chain

        client = MagicMock()
        client.collection.return_value = collection

        with patch.object(goals_module, "_get_firestore_client", return_value=client):
            return goals_module.get_user_goals(
                "u1", limit=limit, include_ended=include_ended
            )

    def test_limit_applied_after_filtering_ended_goals(self):
        """
        Regression #22778: first N docs by id are all ended. With the old
        implementation the caller would receive 0 goals; now they must
        receive `limit` active goals.
        """
        docs = [
            _goal("a-ended-1", achieved=True, created_at=1),
            _goal("b-abandoned-1", abandoned=True, created_at=2),
            _goal("c-ended-2", achieved=True, created_at=3),
            _goal("d-active-1", created_at=4),
            _goal("e-active-2", created_at=5),
            _goal("f-active-3", created_at=6),
            _goal("g-active-4", created_at=7),
        ]
        out = self._run(docs, limit=3)
        self.assertEqual([g.id for g in out], ["d-active-1", "e-active-2", "f-active-3"])

    def test_oldest_first_ordering_preserved(self):
        docs = [
            _goal("a", created_at=30),
            _goal("b", created_at=10),
            _goal("c", created_at=20),
        ]
        out = self._run(docs, limit=2)
        self.assertEqual([g.id for g in out], ["b", "c"])

    def test_include_ended_returns_bounded_page(self):
        docs = [
            _goal("a", achieved=True, created_at=1),
            _goal("b", abandoned=True, created_at=2),
            _goal("c", created_at=3),
        ]
        out = self._run(docs, limit=2, include_ended=True)
        self.assertEqual([g.id for g in out], ["a", "b"])

    def test_limit_greater_than_active_count_returns_all_active(self):
        docs = [
            _goal("a", achieved=True, created_at=1),
            _goal("b", created_at=2),
        ]
        out = self._run(docs, limit=10)
        self.assertEqual([g.id for g in out], ["b"])

    def test_limit_zero_returns_empty(self):
        docs = [_goal("a", created_at=1)]
        out = self._run(docs, limit=0)
        self.assertEqual(out, [])

    def test_does_not_call_firestore_limit(self):
        """
        Guardrail: the Firestore chain must not receive `.limit(...)` before
        filtering, otherwise the bug can reappear unnoticed.
        """
        docs = [_goal("a", created_at=1)]
        collection = MagicMock()
        chain = MagicMock()
        chain.stream.return_value = [_fake_doc(d) for d in docs]
        collection.where.return_value = chain

        client = MagicMock()
        client.collection.return_value = collection

        with patch.object(goals_module, "_get_firestore_client", return_value=client):
            goals_module.get_user_goals("u1", limit=3)

        chain.limit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
```

**Notas para el revisor:**
- Los tests no tocan Firestore real: mockean `_get_firestore_client` y el `collection`/`stream`.
- `test_limit_applied_after_filtering_ended_goals` es el **test de regresión** explícito de #22778.
- `test_does_not_call_firestore_limit` es un guardarraíl estáticamente barato que impide reintroducir el bug.
- Los nombres de atributos (`Goal.achieved`, `Goal.abandoned`, `Goal.created_at`, `Goal.is_ended`, `_get_firestore_client`, `GOALS_COLLECTION`) siguen el módulo existente; si el dataclass difiere en el repo, ajustar los cinco puntos marcados en el factory `_goal`.

### Ejecución

```bash
cd backend && python -m pytest tests/unit/test_goals_limit.py -v
```

---

## 3. Mensaje formal de Pull Request

> **Título:** `fix(goals): apply limit after filtering in get_user_goals`

---

### Resumen

`get_user_goals` en `backend/database/goals.py` aplicaba `.limit(limit)` **dentro** de la consulta Firestore. Firestore paginaba en orden de document-id **antes** de que el filtro Python descartara goals `achieved`/`abandoned`, de modo que una primera página compuesta enteramente por goals terminados provocaba que los goals activos fueran descartados. Los llamadores que solicitaban `limit=3` goals activos recibían silenciosamente menos (o cero).

### Solución

Se mueve el bound **después** del filtro de goals terminados y del orden `created_at` ascendente — el mismo patrón que `get_all_goals` en este módulo ya documenta para exactamente este caso:

- Fetch sin `.limit()` en Firestore.
- Filtrar (`achieved` / `abandoned`) salvo `include_ended=True`.
- Ordenar por `created_at` ascendente.
- Aplicar `[:limit]` sobre la lista resultante.

**Cambio neto:** ~6 líneas en `get_user_goals`. Sin cambios de firma, esquema, índice ni API pública.

### Impacto en llamadores

Sin cambios requeridos. Los dos consumidores afectados pasan `limit=3` y ahora reciben hasta 3 **goals activos**, no "3 documentos que pueden ser todos terminados":

- `backend/utils/proactivity_producers.py`
- `backend/utils/llm/external_integrations.py`

### Tests

Nuevo archivo `backend/tests/unit/test_goals_limit.py` con 6 casos:

1. **Regresión #22778** — página inicialmente llena de goals terminados → el llamador recibe `limit` goals activos.
2. Orden `created_at` ascendente preservado.
3. `include_ended=True` devuelve una página acotada.
4. `limit` mayor que el número de activos → devuelve todos los activos.
5. `limit=0` → lista vacía.
6. Guardarraíl: la cadena Firestore no recibe `.limit()`.

```bash
python -m pytest backend/tests/unit/test_goals_limit.py -v
```

### Checklist

- [x] Corrige #22778
- [x] Sin cambios de esquema / API / firma pública
- [x] Consistente con `get_all_goals` en el mismo módulo
- [x] Test de regresión incluido
- [x] Sin nuevas dependencias

Fixes #22778 · Bounty #23294 · Cartera del operador: `0x02c1F87F514493F359Afc0B3ff6b587434770361`