# 📦 CI/CD Pipeline – Appian - GitHub Actions

> Estado: este repo ahora actúa como Sandbox de una aplicación Appian y consume workflows reutilizables del repo Core (`vrgroup-lab/appian-cicd-core@sql`). El material del antiguo monorepo fue archivado en `legacy_monorepo/`.

## Uso rápido (wrappers hacia el Core)
- Workflows: `deploy-app.yml` (aplicaciones) y `deploy-package.yml` (paquetes).
- Ambos apuntan a `vrgroup-lab/appian-cicd-core/.github/workflows/{export,promote}.yml@sql` y requieren `vars.APP_UUID`.
- Cada ejecución descarga el template de customización generado por Appian, lo procesa con `.github/scripts/prepare_icf_template.py` y abre una issue automática (`.github/templates/icf-issue.md`) con:
  - Extracto del `.properties` real exportado.
- JSON listo para pegar en los secretos `ICF_JSON_OVERRIDES_QA` y `ICF_JSON_OVERRIDES_PROD`.
- Inputs disponibles:
  - `plan` (`dev-to-qa`, `dev-qa-prod`, `qa-to-prod`).
  - `package_name` (sólo en `deploy-package.yml`).

Consulta `SANDBOX_TEMPLATE.md` para convertir este repo en template y los pasos de configuración al crear sandboxes nuevos.


> **Versión:** 2025-07-01 · *Owner: M. Tombolini (VR Group)*

---

## ✅ Propósito

Orquestar **dos procesos de promoción** mediante GitHub Actions para mover artefactos entre entornos con trazabilidad y control:

### 1. Pipeline de **Aplicaciones completas**
Soporta las cuatro rutas de despliegue definidas:
1. **Dev → QA** (validación funcional)  
2. **Dev → QA → Prod** (flujo estándar)  
3. **Dev → Prod** (fast-track de emergencia)  
4. **QA → Prod** (hot-fix)  

### 2. Pipeline de **Paquetes (features)**
Optimizado para entrega continua de mejoras parciales:
1. **Dev → QA**  
2. **Dev → QA → Prod**  

**Garantías comunes:**
- Etapas **export → inspect → import** completamente automatizadas.  
- Aprobaciones manuales gobernadas por **GitHub Environments**.  
- Credenciales segregadas por entorno (URL + API Key).  
- Artefacto inmutable: lo validado es lo que se importa.  


---

## 🌍 Topología de entornos

| GitHub Environment | URL de Appian                                                          | Estado                       |
| ------------------ | ---------------------------------------------------------------------- | ---------------------------- |
| `dev`              | [https://dev‑bicevida.appian.cloud](https://dev‑bicevida.appian.cloud) | ✅ Connected                  |
| `qa`               | [https://qa‑bicevida.appian.cloud](https://qa‑bicevida.appian.cloud)   | ✅ Connected                  |
| `prod`             | **simulado – apunta a QA**                                             | ⏳ A la espera de acceso real |

> **Nota:** mientras Prod no esté disponible, los jobs con `environment: prod` se ejecutan contra QA. Esto mantiene la firma del pipeline intacta para el día en que Prod se habilite.

---

## ⚙️ Arquitectura general

```
┌────────────┐   export  ┌────────────┐   import   ┌──────────────┐
│ Appian Dev │──────────►│     QA     │──────────► │ Prod*(QA URL)│
└────────────┘           └────────────┘            └──────────────┘
        ▲                       ▲                         ▲
        │  secrets.dev          │  secrets.qa             │  secrets.prod
        ▼                       ▼                         ▼
      GitHub Actions ——— Workflows & Artifacts ——— Branch Protection
```

---

## 🔐 Autenticación

Actual: cada llamada REST incluye cabecera `Appian-API-Key` obtenida de `{{ secrets.[env].APPIAN_API_KEY }}`.

### 🔄 Alternativas evaluadas

| Opción                   | Descripción                                                                              | Pros                                             | Contras                                 |
| ------------------------ | ---------------------------------------------------------------------------------------- | ------------------------------------------------ | --------------------------------------- |
| **Directo (actual)**     | GitHub llama a `/deployments` con API Key por environment                                | Menos capas, fácil de auditar                    | API Key vive en GitHub; rotación manual |

---

## 🌳 Branching Model (repositorio)

| Rama        | Rol                                                         | Reglas                           |
| ----------- | ----------------------------------------------------------- | -------------------------------- |
| `main`      | Línea estable; artefactos desplegados (o simulados) en Prod | **Protegida**: PR + 1 aprobación |
| `dev`       | Desarrollo de workflows y experimentos                      | Libre                            |
| `feature/*` | Cambios puntuales                                           | Merge ► `dev`                    |

> No se protegen ramas secundarias; el control de despliegues recae en **GitHub Environments**.

---

## 📁 Estructura de artefactos

Cada export queda versionada en `appian-artifacts/<artifact_name>/` junto con todos los archivos complementarios que entrega el Core.

```
appian-artifacts/
  <artifact_name>/
    export-metadata.json
    <artifact_name>.zip
    database-scripts/            # opcional: SQL/DDL empaquetados por el Core
    customization/               # opcional: customization.properties exportado
    customization-template/      # opcional: template properties
    plugins/                     # opcional: bundle de plug-ins
```

- `export-metadata.json` conserva los paths originales (`artifact_path`, `artifact_dir`) y los metadatos que devuelve Appian (`deployment_uuid`, `deployment_status`, `downloaded_files`).
- Los jobs posteriores consumen los mismos nombres de artifact (`<artifact_name>`, `<artifact_name>-db-scripts`, etc.) publicados desde el Core.

---

## 🛠️ Workflows disponibles

| Archivo                       | Tipo         | ¿Lo usa el usuario final? | Descripción breve                               |
| ----------------------------- | ------------ | ------------------------- | ----------------------------------------------- |
| `deploy_app_pipeline.yml`     | **Pipeline** | ✅ **Sí**                  | Dev → QA → Prod para **aplicaciones completas** |
| `deploy_package_pipeline.yml` | **Pipeline** | ✅ **Sí**                  | Dev → QA → Prod para **paquetes**               |
| `wf_export_app.yml`           | Job helper   | ❌                         | Exporta ZIP de app desde Dev                    |
| `wf_export_package.yml`       | Job helper   | ❌                         | Exporta ZIP de paquete                          |
| `wf_inspect.yml`              | Job helper   | ❌                         | Ejecuta `/deployments?action=inspect`           |
| `wf_import.yml`               | Job helper   | ❌                         | Importa ZIP en QA o Prod                        |
| `wf_list_packages.yml`        | Job helper   | ❌                         | Lista paquetes por app                          |

> Los usuarios disparan los **pipelines**, no los helpers.

---

## 🔗 Endpoints Appian

| Método & Ruta                              | Uso actual               |
| ------------------------------------------ | ------------------------ |
| `GET /applications/{uuid}/packages`        | Obtener UUIDs            |
| `POST /deployments` `Action-Type: export`  | Exportar paquete/app     |
| `GET /deployments/{uuid}`                  | Ver estado export/import |
| `POST /deployments` `Action-Type: inspect` | Validar zip en QA/Prod   |
| `POST /deployments` `Action-Type: import`  | Importar zip             |

---

## 📂 CI/CD Manager (Appian)

- Persistencia temporal → `apps_config.json` en repo.
- **Próximo sprint**: migración a **Data Fabric** + Record Actions.

---

## 🛣️ Roadmap (Q3–Q4 2025)

1. Migrar CI/CD Manager a Data Fabric y exponer Record Actions para una gestión robusta de aplicaciones y versiones.

2. Extender los pipelines para incluir artefactos de configuración (Admin Console, SQL, plugins) junto al ZIP principal.

3. Optimizar el flujo de aprobaciones en GitHub Environments, eliminando pasos redundantes y definiendo criterios claros de aceptación.

---

## 📞 Contacto

- **Consultor / Developer:** Maximiliano Tombolini – [mtombolini@vr-group.cl](mailto:mtombolini@vr-group.cl)
- **Lead Delivery Service:** *Ángel Barroyeta* – [abarroyeta@vrgroup.cl](mailto:abarroyeta@vrgroup.cl)
- **Arquitecto Appian:** *Ignacio Arriagada* – [iarriagada@vrgroup.cl](mailto:iarriagada@vrgroup.cl)
