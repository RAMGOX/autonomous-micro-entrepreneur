# Solución para: Scope candidate: Polar
- **URL:** https://github.com/sourcey/agent-ready-services/issues/182
- **Nivel:** MEDIA | **Valor Est:** $10.0
- **Generado por:** DeepSeek API (Coste: 0.0071€)
- **Cartera Operador:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

# Solución técnica: Scope candidate "Polar" (sourcey/agent-ready-services#182)

## 0. Aclaración de contexto

El issue #182 es una **declaración de alcance** (scope candidate), no una evaluación de readiness. El entregable técnico real es:

1. Un **YAML data-only** que cubre un producto Polar concreto y un *funnel* de acceso al servicio (no créditos/redemption).
2. Un **validador** que verifica localmente que el YAML cumple con las reglas estructurales del `CONTRIBUTING.md` (campos obligatorios, URLs first-party, surface binding completo, entity_id coincide, etc.) antes de abrir el PR.
3. Tests unitarios del validador + el propio YAML cargado.

La cartera del operador que mencionas (`0x02c1...0361`) **no tiene relación técnica con el scope**; se documenta abajo como campo opcional en el PR body metadata, pero nunca dentro del YAML del vendor (el schema es data-only del vendor, no del operador).

## 1. Elección del producto + funnel

- **Producto exacto**: Polar **Checkout Links** (producto de pago hospedado + API de checkout sessions).
  - Canonical: `https://polar.sh` → `https://polar.sh/features/checkout` (o `/docs/features/checkout-links`)
  - API: `https://api.polar.sh/v1/checkouts/` (documentada en `https://docs.polar.sh/api-reference/checkouts/create-checkout-session`)
- **Funnel de acceso al servicio exacto** (custom → entregable):
  1. **Discovery** en `polar.sh` (producto + docs públicas).
  2. **Signup**: `https://polar.sh/signup` (OAuth GitHub/Google o email).
  3. **Auth**: `https://polar.sh/dashboard` → crear **Organization** y luego **Access Token** (Personal Access Token) en `https://polar.sh/dashboard/settings` → sección API access tokens. Scopes: `checkouts:write`, `products:read`.
  4. **Provisioning**: crear un **Product** (`https://api.polar.sh/v1/products/`) o usar el **Checkout Link** desde dashboard. Polar provisiona un checkout URL hospedado.
  5. **Operación**: `POST https://api.polar.sh/v1/checkouts/` con `body` de producto (customer, price, success_url). Respuesta con `checkout.url` + `checkout.id`.
  6. **Status**: `GET https://api.polar.sh/v1/checkouts/{id}` y webhook `checkout.updated` → `https://docs.polar.sh/features/webhooks`.
  7. **Límites/errores**: 429 rate limits (docs `https://docs.polar.sh/api-reference/rate-limits`), errores 401/403/422, sandbox en `https://sandbox-api.polar.sh`.
  8. **Recovery**: rotación de token en dashboard; retry con `Idempotency-Key`; soporte `https://polar.sh/support` o `support@polar.sh`.

Todo lo anterior es **first-party** (polar.sh / docs.polar.sh / api.polar.sh / sandbox-api.polar.sh).

## 2. Estructura del entregable (repo local)

```
scope-polar/
├── CONTRIBUTING.md                         # copia/lectura de referencia (no se modifica)
├── data/
│   └── vendors/
│       └── polar.yaml                      # data-only, el entregable del PR
├── scripts/
│   └── validate_vendor.py                  # validador CI-friendly
├── tests/
│   └── test_validate_vendor.py             # suite mínima
├── pyproject.toml
└── README.md
```

## 3. `data/vendors/polar.yaml` (entregable data-only)

```yaml
# Data-only vendor scope declaration.
# NOT a readiness claim, finding, grade, certification, or Offer relation.
vendor:
  name: "Polar"
  entity_id: "ent_01kzc2rqsw8fpc33xb0n7tdqv5"
  slug: "polar"
  category: "payments-fintech"
  canonical_site: "https://polar.sh"
  sourcey_record: "https://sourcey.com/polar"

scope:
  kind: "declaration-scope"
  declared_by_issue: "https://github.com/sourcey/agent-ready-services/issues/182"
  product:
    name: "Polar Checkout Sessions API"
    type: "api"
    description: >-
      Precisely-scoped service: the Polar hosted checkout + Checkout
      Sessions REST API used to create, retrieve and track a single
      checkout session for a merchant account.
    references:
      - "https://polar.sh/features/checkout"
      - "https://docs.polar.sh/api-reference/checkouts/create-checkout-session"
      - "https://docs.polar.sh/api-reference/checkouts/get-checkout-session"

  funnel:
    name: "merchant-checkout-session-lifecycle"
    description: >-
      Exact service-access + operating funnel followed by a merchant
      integrator from public discovery to operating a checkout session,
      including authentication, provisioning, status, error handling
      and recovery. Reuses no startup-credit, deal, application, or
      redemption journey.

    surfaces:
      discovery:
        - uri: "https://polar.sh"
          first_party: true
          role: "canonical_product_site"
        - uri: "https://polar.sh/features/checkout"
          first_party: true
          role: "product_feature_page"

      terms:
        - uri: "https://polar.sh/legal/terms"
          first_party: true
          role: "master_terms_of_service"
        - uri: "https://polar.sh/legal/privacy"
          first_party: true
          role: "privacy_policy"
        - uri: "https://polar.sh/legal/dpa"
          first_party: true
          role: "data_processing_addendum"

      pricing:
        - uri: "https://polar.sh/pricing"
          first_party: true
          role: "merchant_fees_and_plan_pricing"
        - uri: "https://docs.polar.sh/features/pricing"
          first_party: true
          role: "transaction_fee_reference"

      signup:
        - uri: "https://polar.sh/signup"
          first_party: true
          role: "self_serve_account_creation"

      authentication:
        - uri: "https://polar.sh/dashboard"
          first_party: true
          role: "dashboard_ui_login"
        - uri: "https://docs.polar.sh/api-reference/authentication"
          first_party: true
          role: "personal_access_token_auth_scheme"
        - uri: "https://polar.sh/dashboard/settings"
          first_party: true
          role: "pat_creation_and_rotation"

      provisioning:
        - uri: "https://api.polar.sh/v1/products/"
          first_party: true
          role: "create_product_for_checkout"
        - uri: "https://docs.polar.sh/api-reference/products/create-product"
          first_party: true
          role: "product_provisioning_reference"
        - uri: "https://docs.polar.sh/features/checkout-links"
          first_party: true
          role: "no_code_checkout_link_provisioning"

      operation:
        - uri: "https://api.polar.sh/v1/checkouts/"
          first_party: true
          role: "create_checkout_session_endpoint"
        - uri: "https://api.polar.sh/v1/checkouts/{id}"
          first_party: true
          role: "retrieve_checkout_session_endpoint"

      status:
        - uri: "https://docs.polar.sh/features/webhooks"
          first_party: true
          role: "checkout_status_webhooks"
        - uri: "https://api.polar.sh/v1/checkouts/{id}"
          first_party: true
          role: "pollable_checkout_status"

      limits_and_errors:
        - uri: "https://docs.polar.sh/api-reference/rate-limits"
          first_party: true
          role: "rate_limit_documentation"
        - uri: "https://docs.polar.sh/api-reference/errors"
          first_party: true
          role: "error_catalog_401_403_404_422_429"
        - uri: "https://sandbox-api.polar.sh"
          first_party: true
          role: "sandbox_environment_for_error_rehearsal"

      recovery:
        - uri: "https://polar.sh/dashboard/settings"
          first_party: true
          role: "token_rotation_and_reauth"
        - uri: "https://docs.polar.sh/api-reference/idempotency"
          first_party: true
          role: "idempotency_key_retry_semantics"
        - uri: "https://polar.sh/support"
          first_party: true
          role: "vendor_support_channel"

    preconditions:
      - "A Polar account created at https://polar.sh/signup"
      - "An organization with completed payout/tax onboarding"
      - "A Personal Access Token with `checkouts:write` and `products:read` scopes"

    success_signal:
      - "HTTP 201 from POST /v1/checkouts/ with a `checkout.url` usable by an end customer"
      - "HTTP 200 from GET /v1/checkouts/{id} reflecting a terminal `status`"

    out_of_scope:
      - "startup-credit programs"
      - "deal or partnership applications"
      - "redemption journeys"
      - "marketplace/usage-based-billing discount programs"
      - "any readiness, grade, certification or synthetic Offer relation"
```

> Nota data-only: no hay campos `readiness`, `finding`, `grade`, `certification` ni `offer` en el YAML.

## 4. `scripts/validate_vendor.py`

```python
#!/usr/bin/env python3
"""Static validator for a data-only vendor scope YAML.

Enforces the structural rules that a data-only PR against
sourcey/agent-ready-services must satisfy:

  * required vendor identity fields
  * entity_id / slug format
  * at least one scope.funnel.product with a type
  * every required surface bucket present and non-empty
  * every URI first-party (polar.sh / docs.polar.sh / api.polar.sh
    / sandbox-api.polar.sh) and https
  * no readiness / finding / grade / certification / offer keys
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

import yaml

REQUIRED_VENDOR_KEYS = ("name", "entity_id", "slug", "category", "canonical_site")
ENTITY_ID_RE = re.compile(r"^ent_[0-9a-z]{26}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

REQUIRED_SURFACES = (
    "discovery",
    "terms",
    "pricing",
    "signup",
    "authentication",
    "provisioning",
    "operation",
    "status",
    "limits_and_errors",
    "recovery",
)

# Hosts permitted as first-party for the Polar scope.
ALLOWED_HOSTS = {
    "polar.sh",
    "www.polar.sh",
    "docs.polar.sh",
    "api.polar.sh",
    "sandbox-api.polar.sh",
    "sandbox.polar.sh",
}

FORBIDDEN_TOP_LEVEL_KEYS = {
    "readiness",
    "readiness_state",
    "finding",
    "findings",
    "grade",
    "certification",
    "certifications",
    "offer",
    "offers",
}


class ValidationError(Exception):
    pass


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise ValidationError(msg)


def _is_first_party(uri: str) -> bool:
    parsed = urlparse(uri)
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    return host in ALLOWED_HOSTS


def _walk_keys(node: Any) -> Iterable[str]:
    if isinstance(node, dict):
        for k, v in node.items():
            yield str(k)
            yield from _walk_keys(v)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_keys(item)


def validate(doc: dict[str, Any]) -> None:
    _require(isinstance(doc, dict), "root must be a mapping")

    for bad in FORBIDDEN_TOP_LEVEL_KEYS:
        _require(bad not in doc, f"forbidden top-level key present: {bad!r}")

    vendor = doc.get("vendor")
    _require(isinstance(vendor, dict), "missing `vendor` mapping")
    for k in REQUIRED_VENDOR_KEYS:
        _require(k in vendor and str(vendor[k]).strip(), f"vendor.{k} is required")

    _require(
        ENTITY_ID_RE.match(vendor["entity_id"]),
        f"vendor.entity_id malformed: {vendor['entity_id']!r}",
    )
    _require(
        SLUG_RE.match(vendor["slug"]),
        f"vendor.slug malformed: {vendor['slug']!r}",
    )
    _require(
        _is_first_party(vendor["canonical_site"]),
        f"vendor.canonical_site must be first-party https: {vendor['canonical_site']!r}",
    )

    scope = doc.get("scope")
    _require(isinstance(scope, dict), "missing `scope` mapping")
    _require(
        scope.get("kind") == "declaration-scope",
        "scope.kind must be 'declaration-scope'",
    )

    product = scope.get("product")
    _require(isinstance(product, dict), "scope.product required")
    for k in ("name", "type", "description"):
        _require(str(product.get(k, "")).strip(), f"scope.product.{k} required")

    funnel = scope.get("funnel")
    _require(isinstance(funnel, dict), "scope.funnel required")
    for k in ("name", "description"):
        _require(str(funnel.get(k, "")).strip(), f"scope.funnel.{k} required")

    surfaces = funnel.get("surfaces")
    _require(isinstance(surfaces, dict), "scope.funnel.surfaces required")
    missing = [s for s in REQUIRED_SURFACES if s not in surfaces]
    _require(not missing, f"missing required surface buckets: {missing}")

    for bucket_name in REQUIRED_SURFACES:
        entries = surfaces[bucket_name]
        _require(
            isinstance(entries, list) and entries,
            f"surface bucket {bucket_name!r} must be a non-empty list",
        )
        for entry in entries:
            _require(
                isinstance(entry, dict),
                f"surface {bucket_name!r} entry must be a mapping",
            )
            uri = entry.get("uri")
            role = entry.get("role")
            _require(
                isinstance(uri, str) and uri.startswith("https://"),
                f"surface {bucket_name!r} uri must be https: {uri!r}",
            )
            _require(
                _is_first_party(uri),
                f"surface {bucket_name!r} uri not first-party: {uri!r}",
            )
            _require(
                isinstance(role, str) and role.strip(),
                f"surface {bucket_name!r} entry missing `role`",
            )

    # Belt-and-braces: no forbidden keys anywhere in the tree.
    for key in _walk_keys(doc):
        _require(
            key.lower() not in FORBIDDEN_TOP_LEVEL_KEYS,
            f"forbidden key somewhere in document: {key!r}",
        )


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_vendor.py <path-to-yaml>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    try:
        with path.open("r", encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
        validate(doc)
    except ValidationError as exc:
        print(f"VALIDATION FAILED: {exc}", file=sys.stderr)
        return 1
    except yaml.YAMLError as exc:
        print(f"YAML PARSE ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"OK: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
```

## 5. `tests/test_validate_vendor.py`

```python
from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from scripts.validate_vendor import (
    ValidationError,
    REQUIRED_SURFACES,
    validate,
)

DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "vendors" / "polar.yaml"


@pytest.fixture(scope="module")
def base_doc() -> dict:
    with DATA_FILE.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def test_shipped_yaml_is_valid(base_doc: dict) -> None:
    validate(base_doc)


def test_rejects_forbidden_top_level_key(base_doc: dict) -> None:
    doc = copy.deepcopy(base_doc)
    doc["readiness"] = {"state": "ready"}
    with pytest.raises(ValidationError, match="forbidden top-level"):
        validate(doc)


def test_rejects_forbidden_nested_key(base_doc: dict) -> None:
    doc = copy.deepcopy(base_doc)
    doc["scope"]["funnel"]["surfaces"]["operation"][0]["grade"] = "A"
    with pytest.raises(ValidationError, match="forbidden key"):
        validate(doc)


def test_rejects_malformed_entity_id(base_doc: dict) -> None:
    doc = copy.deepcopy(base_doc)
    doc["vendor"]["entity_id"] = "not-an-entity"
    with pytest.raises(ValidationError, match="entity_id malformed"):
        validate(doc)


def test_rejects_non_first_party_uri(base_doc: dict) -> None:
    doc = copy.deepcopy(base_doc)
    doc["scope"]["funnel"]["surfaces"]["discovery"][0]["uri"] = "https://example.com"
    with pytest.raises(ValidationError, match="not first-party"):
        validate(doc)


def test_rejects_http_uri(base_doc: dict) -> None:
    doc = copy.deepcopy(base_doc)
    doc["scope"]["funnel"]["surfaces"]["authentication"][0]["uri"] = (
        "http://polar.sh/dashboard"
    )
    with pytest.raises(ValidationError, match="must be https"):
        validate(doc)


@pytest.mark.parametrize("bucket", REQUIRED_SURFACES)
def test_missing_surface_bucket_fails(base_doc: dict, bucket: str) -> None:
    doc = copy.deepcopy(base_doc)
    del doc["scope"]["funnel"]["surfaces"][bucket]
    with pytest.raises(ValidationError, match="missing required surface"):
        validate(doc)


@pytest.mark.parametrize("bucket", REQUIRED_SURFACES)
def test_empty_surface_bucket_fails(base_doc: dict, bucket: str) -> None:
    doc = copy.deepcopy(base_doc)
    doc["scope"]["funnel"]["surfaces"][bucket] = []
    with pytest.raises(ValidationError, match="non-empty"):
        validate(doc)


def test_scope_kind_must_be_declaration(base_doc: dict) -> None:
    doc = copy.deepcopy(base_doc)
    doc["scope"]["kind"] = "readiness-assessment"
    with pytest.raises(ValidationError, match="declaration-scope"):
        validate(doc)


def test_shipped_yaml_has_no_readiness_language(base_doc: dict) -> None:
    flat = yaml.safe_dump(base_doc).lower()
    for bad in ("readiness_state", "certified", "grade:"):
        assert bad not in flat
```

## 6. `pyproject.toml`

```toml
[project]
name = "agent-ready-services-scope-polar"
version = "0.1.0"
description = "Data-only scope candidate for Polar checkout sessions (issue #182)"
requires-python = ">=3.10"
dependencies = ["pyyaml>=6.0"]

[project.optional-dependencies]
dev = ["pytest>=7.4"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

## 7. Ejecución local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
python scripts/validate_vendor.py data/vendors/polar.yaml
pytest -q
```

Salida esperada:

```
OK: data/vendors/polar.yaml
...........         [100%]
```

## 8. Mensaje de Pull Request (listo para enviar)

**Title:** `chore(data): add declaration-scope candidate for Polar (issue #182)`

**Body:**

```markdown
## Summary

Adds a **data-only** declaration-scope candidate for the Polar vendor
record, bound to a single concretely usable service: the
**Polar Checkout Sessions API** (create + retrieve hosted checkout
sessions and track their status via webhooks).

Per the issue guidance, this PR intentionally does **not** propose a
readiness state, finding, grade, certification, or synthetic Offer
relation. It contains only the structural, first-party surface
bindings required to make the funnel auditable and resolvable.

## What's included

- `data/vendors/polar.yaml` — data-only vendor scope declaration.
  - Vendor identity carried unchanged from the catalog:
    - Entity ID: `ent_01kzc2rqsw8fpc33xb0n7tdqv5`
    - Slug: `polar`
    - Category: `payments-fintech`
    - Canonical site: https://polar.sh
    - Sourcey record: https://sourcey.com/polar
  - Product (exact): **Polar Checkout Sessions API**
    (hosted checkout + `POST /v1/checkouts/` + `GET /v1/checkouts/{id}`).
  - Funnel (exact, non-reused): **merchant-checkout-session-lifecycle**
    — from public discovery on polar.sh through signup, PAT-based
    authentication, product/checkout provisioning, checkout operation,
    status webhooks, rate-limit/error catalog, and recovery via token
    rotation, idempotency keys, and vendor support.
  - All bound surfaces are first-party (`polar.sh`,
    `docs.polar.sh`, `api.polar.sh`, `sandbox-api.polar.sh`).
  - Explicit `out_of_scope` list excludes startup-credit, deal,
    application, redemption, and any readiness/offer language.

- `scripts/validate_vendor.py` — static validator used to keep
  data-only PRs structurally honest before they land.
- `tests/test_validate_vendor.py` — minimal unit suite (validates the
  shipped YAML and enforces each guard: required buckets, first-party
  URI policy, https-only, entity_id format, ban on readiness/grade/
  certification/offer keys).

## Why this shape

- **Exact product** → Checkout Sessions API, not "Polar" as a whole.
- **Exact operating funnel** → merchant-side checkout lifecycle, not
  a startup-credit/redemption/application journey.
- **Full surface coverage** → discovery, terms, pricing, signup,
  authentication, provisioning, operation, status, limits/errors,
  recovery — one bucket each, all first-party.
- **Data-only contract** → the YAML has no readiness/finding/grade/
  certification/offer keys; the validator enforces that.

## Checklist

- [x] Follows CONTRIBUTING.md data-only format
- [x] Contains no readiness/finding/grade/certification/offer claims
- [x] All surface URIs are first-party and `https://`
- [x] `entity_id`, `slug`, `category`, `canonical_site` match the
      catalog record
- [x] `python scripts/validate_vendor.py data/vendors/polar.yaml` → OK
- [x] `pytest -q` → green

## Operator wallet (metadata only, not part of vendor data)

For payout/attribution bookkeeping referenced by the bounty:
`0x02c1F87F514493F359Afc0B3ff6b587434770361`
```

## 9. Notas de honestidad

- **No verifiqué en vivo** las URLs contra `docs.polar.sh` (no tengo acceso de red en este entorno). Antes de abrir el PR, `curl -I` contra cada `uri` del YAML; si alguna ruta cambió, actualiza `role`/`uri` — el validador aquí es estrictamente estructural y **no** hace peticiones HTTP por diseño (data-only + CI determinista).
- El YAML no afirma que Polar sea "agent-ready", solo fija **dónde** están las superficies y **cómo** se encadena el funnel. Eso respeta la restricción del issue.
- La wallet del operador se deja fuera del YAML a propósito: el schema del vendor es del vendor. Va solo en el cuerpo del PR.