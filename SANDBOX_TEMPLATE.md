# Guía de Template y Replicación de Sandbox

## ¿Qué se copia al usar un Template?
- Se copia el contenido del repositorio: código, directorios, workflows (`.github/workflows`), issues, labels, etc.
- No se copian configuraciones sensibles ni de protección:
  - Secrets, variables del repo, environments (QA/PROD) y sus reviewers, branch protections, Actions permissions.

Conclusión: al crear un sandbox desde este Template, hay que configurar variables/environments de nuevo.

## Convertir este repo en Template
1. Ve a `Settings` → `General` → sección “Template repository”.
2. Activa “Template repository” y guarda.

## Crear un Sandbox nuevo desde el Template
1. En GitHub, pulsa “Use this template” → “Create a new repository”.
2. Elige owner/organización, nombre del repo y visibilidad.
3. Crea el repositorio.

## Configuración posterior en el nuevo Sandbox
1. Variables del repositorio:
   - `APP_UUID`: UUID de la aplicación Appian que representa este Sandbox.
2. Environments:
   - Crea `qa` y `prod` en `Settings` → `Environments`.
   - Define reviewers/aprobaciones si quieres gating manual.
3. Actions permissions (repo Sandbox):
   - Permite usar reusable workflows. Si usas allowlist, agrega:
     - `vrgroup-lab/appian-cicd-core/.github/workflows/export.yml@*`
     - `vrgroup-lab/appian-cicd-core/.github/workflows/promote.yml@*`
4. Reusable workflows (repo Core):
   - En el repo Core, `Settings` → `Actions` → `General` → “Access for reusable workflows”.
   - Debe permitir acceso desde repos de la organización (o agregar el nuevo Sandbox si es lista seleccionada).
5. Opcional: Protecciones de rama y políticas de aprobación según tus estándares.

## Probar el flujo
1. Ve a `Actions` → ejecuta “Deploy Package” o “Deploy App”.
2. Inputs sugeridos:
   - `plan=dev-to-qa`, `package_name=nightly` (sólo paquetes).
3. Observa:
   - Export: publica `artifact_name`, sube los artefactos y procesa la plantilla ICF mediante `.github/scripts/prepare_icf_template.py`.
   - Promote QA/PROD: consume `artifact_name` y, si corresponde, pide approval por environment.
  - Se crea una issue automática (basada en `.github/templates/icf-issue.md`) con instrucciones para actualizar los secretos `ICF_JSON_OVERRIDES_QA` y `ICF_JSON_OVERRIDES_PROD`, adjunta el extracto del template real y entrega un JSON base para copiar en cada uno antes de aprobar la importación.

## Notas de versión del Core
- Este Sandbox referencia el Core en `@sql` por defecto. Para estabilidad en producción:
  - Pinea a un tag (ej. `@v0.1.0`) o a un SHA específico en `/.github/workflows/deploy.yml`.
