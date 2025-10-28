#!/usr/bin/env python3
import base64
import json
import os
import sys
from pathlib import Path
from urllib import request, error


def log(msg: str) -> None:
  print(msg, flush=True)


def read_issue_template(workspace: Path, template_path: str) -> str:
  try:
    resolved = workspace / template_path
    return resolved.read_text(encoding="utf-8")
  except FileNotFoundError:
    log(f"::warning::No se encontró el template de issue en {template_path}")
  except OSError as exc:
    log(f"::warning::Error al leer {template_path}: {exc}")
  return ""


def read_provisioning_template(workspace: Path, provisioning_path: str) -> list[str]:
  try:
    content = (workspace / provisioning_path).read_text(encoding="utf-8")
  except FileNotFoundError:
    log(f"::warning::No se encontró la plantilla de provisioning en {provisioning_path}")
    return []
  except OSError as exc:
    log(f"::warning::Error al leer {provisioning_path}: {exc}")
    return []
  return content.splitlines()


def extract_properties_section(lines: list[str], source_path: str) -> str:
  label = source_path or "plantilla"
  if not lines:
    return f"> **Nota:** No se encontró `{label}`. Carga la plantilla antes de continuar."

  start_idx = 0
  for idx, line in enumerate(lines):
    if line.strip().startswith("##") and "----" in line:
      start_idx = idx + 1
      break

  relevant = [line.rstrip() for line in lines[start_idx:] if line.strip()]
  if not relevant:
    return f"> **Nota:** No se detectó contenido utilizable en `{label}`. Verifica la plantilla."

  block = "\n".join(relevant)
  return f"### Extracto de la plantilla ({label})\n```properties\n{block}\n```"


def build_overrides_json(lines: list[str]) -> str:
  if not lines:
    return json.dumps({}, indent=2, ensure_ascii=False)

  start_idx = 0
  for idx, line in enumerate(lines):
    if line.strip().startswith("##") and "----" in line:
      start_idx = idx + 1
      break

  overrides: dict[str, str] = {}
  for raw_line in lines[start_idx:]:
    stripped = raw_line.strip()
    if not stripped or stripped.startswith("##"):
      continue
    if stripped.startswith("#"):
      stripped = stripped.lstrip("#").strip()
    if not stripped or stripped.startswith("#"):
      continue
    if "=" not in stripped:
      continue
    key, value = stripped.split("=", 1)
    key = key.strip()
    value = value.strip()
    overrides[key] = value or ""

  return json.dumps(overrides, indent=2, ensure_ascii=False)


def render_body(template: str, replacements: dict[str, str]) -> str:
  result = template
  for token, value in replacements.items():
    result = result.replace(token, value)
  return result


def github_request(method: str, endpoint: str, token: str, payload: dict | None = None) -> dict:
  api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com")
  url = f"{api_url}{endpoint}"
  headers = {
      "Authorization": f"Bearer {token}",
      "Accept": "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
  }

  data = None
  if payload is not None:
    data = json.dumps(payload).encode("utf-8")
    headers["Content-Type"] = "application/json"

  req = request.Request(url, data=data, headers=headers, method=method)
  try:
    with request.urlopen(req) as resp:
      body = resp.read()
      if not body:
        return {}
      return json.loads(body.decode("utf-8"))
  except error.HTTPError as http_err:
    detail = http_err.read().decode("utf-8", errors="replace")
    raise RuntimeError(f"GitHub API {method} {endpoint} failed: {http_err.status} {http_err.reason} – {detail}") from http_err


def set_output(name: str, value: str) -> None:
  output_path = os.environ.get("GITHUB_OUTPUT")
  if not output_path:
    return
  with open(output_path, "a", encoding="utf-8") as fh:
    fh.write(f"{name}={value}\n")


def main() -> int:
  token = os.environ.get("GITHUB_TOKEN")
  if not token:
    log("::error::Falta GITHUB_TOKEN en el entorno.")
    return 1

  repository = os.environ.get("GITHUB_REPOSITORY")
  if not repository or "/" not in repository:
    log("::error::Variable GITHUB_REPOSITORY inválida o ausente.")
    return 1
  owner, repo = repository.split("/", 1)

  run_number = os.environ.get("GITHUB_RUN_NUMBER", "unknown")
  title = f"[CI] Completar ICF_JSON_OVERRIDES – Run #{run_number}"

  target_map_raw = os.environ.get("TARGET_MAP", "{}")
  try:
    target_map = json.loads(target_map_raw)
  except json.JSONDecodeError as exc:
    log(f"::warning::TARGET_MAP inválido ({target_map_raw}): {exc}")
    target_map = {}

  plan = os.environ.get("PLAN", "desconocido")
  targets = target_map.get(plan, [])
  targets_list = "- _(no se identificó entorno de destino)_"
  if targets:
    targets_list = "\n".join(f"- `{env}`" for env in targets)

  def secret_name(env: str) -> str:
    return f"ICF_JSON_OVERRIDES_{env.upper()}"

  secrets_lines: list[str] = []
  for env in targets:
    secrets_lines.append(f"- `{secret_name(env)}` (env: `{env}`)")
  if not secrets_lines:
    secrets_lines.append("- _(no se identificó entorno de destino para actualizar)_")
  secrets_section = "\n".join(secrets_lines)

  workspace = Path(os.environ.get("GITHUB_WORKSPACE", Path.cwd()))
  template_path = os.environ.get("TEMPLATE_PATH", ".github/templates/icf-issue.md")
  provisioning_path = os.environ.get("PROVISIONING_TEMPLATE_PATH", "provisioning/icf-template.properties")

  template_body = read_issue_template(workspace, template_path)

  template_lines: list[str] = []
  source_label = provisioning_path

  content_b64 = os.environ.get("ICF_TEMPLATE_CONTENT_B64", "").strip()
  overrides_b64 = os.environ.get("ICF_OVERRIDES_JSON_B64", "").strip()
  overrides_qa_b64 = os.environ.get("ICF_OVERRIDES_QA_JSON_B64", "").strip()
  overrides_prod_b64 = os.environ.get("ICF_OVERRIDES_PROD_JSON_B64", "").strip()
  template_source = os.environ.get("ICF_TEMPLATE_SOURCE", "").strip()

  if content_b64:
    try:
      decoded = base64.b64decode(content_b64).decode("utf-8")
      template_lines = decoded.splitlines()
      source_label = template_source or "artifact"
      log("Plantilla recibida vía output codificado.")
    except (ValueError, UnicodeDecodeError) as exc:
      log(f"::warning::No se pudo decodificar ICF_TEMPLATE_CONTENT_B64: {exc}")

  override_path = os.environ.get("ICF_TEMPLATE_PATH", "").strip()

  if not template_lines and override_path:
    log(f"Se recibió ICF_TEMPLATE_PATH: {override_path}")
    candidate = Path(override_path)
    if not candidate.is_absolute():
      candidate = workspace / candidate
    try:
      template_lines = candidate.read_text(encoding="utf-8").splitlines()
      source_label = str(candidate)
      log(f"Plantilla exportada cargada desde {candidate}")
    except FileNotFoundError:
      log(f"::warning::No se encontró la plantilla exportada en {candidate}")
    except OSError as exc:
      log(f"::warning::No se pudo leer la plantilla exportada {candidate}: {exc}")

  if not template_lines:
    template_lines = read_provisioning_template(workspace, provisioning_path)
    source_label = provisioning_path
    log(f"Usando plantilla local de fallback: {provisioning_path}")

  template_section = extract_properties_section(template_lines, source_label)

  if overrides_b64:
    try:
      overrides_json = base64.b64decode(overrides_b64).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
      log(f"::warning::No se pudo decodificar ICF_OVERRIDES_JSON_B64: {exc}")
      overrides_json = build_overrides_json(template_lines)
  else:
    overrides_json = build_overrides_json(template_lines)

  def decode_override(custom_b64: str, fallback: str) -> str:
    if not custom_b64:
      return fallback
    try:
      return base64.b64decode(custom_b64).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
      log(f"::warning::No se pudo decodificar overrides específicos ({custom_b64[:8]}…): {exc}")
      return fallback

  overrides_qa_json = decode_override(overrides_qa_b64, overrides_json)
  overrides_prod_json = decode_override(overrides_prod_b64, overrides_json)

  targeted_envs = set(targets)
  if not targeted_envs:
    targeted_envs = {"qa"}

  env_sections: list[str] = []
  if "qa" in targeted_envs:
    env_sections.append(f"#### QA\n```json\n{overrides_qa_json}\n```")
  if "prod" in targeted_envs:
    env_sections.append(f"#### Prod\n```json\n{overrides_prod_json}\n```")
  overrides_by_env = "\n\n".join(env_sections) if env_sections else "_(No hay overrides sugeridos)_"

  replacements = {
      "{{PLAN}}": plan,
      "{{ARTIFACT_DIR}}": os.environ.get("ARTIFACT_DIR", "(sin directorio publicado)"),
      "{{METADATA_PATH}}": os.environ.get("METADATA_PATH", "(sin metadata)"),
      "{{RUN_URL}}": os.environ.get("RUN_URL", ""),
      "{{TARGETS_LIST}}": targets_list,
      "{{TEMPLATE_SECTION}}": template_section,
      "{{OVERRIDES_JSON}}": overrides_json,
      "{{OVERRIDES_QA_JSON}}": overrides_qa_json,
      "{{OVERRIDES_PROD_JSON}}": overrides_prod_json,
      "{{SECRETS_SECTION}}": secrets_section,
      "{{OVERRIDES_BY_ENV}}": overrides_by_env,
      "{{DRY_RUN}}": os.environ.get("DRY_RUN", "false"),
  }

  if template_body:
    body = render_body(template_body, replacements)
  else:
    body = render_body(
        (
            "## ✅ Acción requerida\n\n"
            "1. Ve a **Settings → Secrets and variables → Actions → Repository secrets**.\n"
            "2. Actualiza los siguientes secretos (uno por entorno):\n"
            "{{SECRETS_SECTION}}\n"
            "3. Usa la plantilla `provisioning/icf-template.properties` como referencia para los valores obligatorios.\n"
            "4. Una vez actualizadas las credenciales, guarda los secretos y continúa con la aprobación en GitHub Actions.\n\n"
            "### Contexto de la ejecución\n"
            "- Plan seleccionado: `{{PLAN}}`\n"
            "- Dry run: `{{DRY_RUN}}`\n"
            "- Directorio de artefacto: `{{ARTIFACT_DIR}}`\n"
            "- Metadata export: `{{METADATA_PATH}}`\n"
            "- Ejecución: {{RUN_URL}}\n\n"
            "### Entornos objetivo detectados\n"
            "{{TARGETS_LIST}}\n\n"
            "> Cierra esta issue cuando los overrides estén listos. Si la promoción se repite, se generará una issue nueva.\n\n"
            "{{TEMPLATE_SECTION}}\n\n"
            "### Plantillas sugeridas por entorno\n"
            "{{OVERRIDES_BY_ENV}}\n"
        ),
        replacements,
    )

  log(f"Buscando issue existente con título: {title}")
  issues = github_request(
      "GET",
      f"/repos/{owner}/{repo}/issues?state=open&per_page=100",
      token,
  )
  existing = next((issue for issue in issues if issue.get("title") == title), None)

  if existing:
    log(f"Issue ya existe: #{existing['number']} – {existing['html_url']}")
    set_output("issue_number", str(existing["number"]))
    set_output("issue_url", existing["html_url"])
    return 0

  log("Creando issue nueva...")
  created = github_request(
      "POST",
      f"/repos/{owner}/{repo}/issues",
      token,
      {"title": title, "body": body},
  )

  issue_number = str(created.get("number", ""))
  issue_url = created.get("html_url", "")
  log(f"Issue creada: #{issue_number} – {issue_url}")

  set_output("issue_number", issue_number)
  set_output("issue_url", issue_url)
  return 0


if __name__ == "__main__":
  sys.exit(main())
