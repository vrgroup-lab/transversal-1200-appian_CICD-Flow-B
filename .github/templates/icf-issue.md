## ✅ Acción requerida

1. Ve a **Settings → Secrets and variables → Actions → Repository secrets**.
2. Actualiza los siguientes secretos (uno por entorno):
{{SECRETS_SECTION}}
3. Usa la plantilla `provisioning/icf-template.properties` como referencia para los valores obligatorios.
4. Una vez actualizadas las credenciales, guarda los secretos y continúa con la aprobación en GitHub Actions.

### Contexto de la ejecución
- Plan seleccionado: `{{PLAN}}`
- Directorio de artefacto: `{{ARTIFACT_DIR}}`
- Metadata export: `{{METADATA_PATH}}`
- Ejecución: {{RUN_URL}}

### Entornos objetivo detectados
{{TARGETS_LIST}}

> Cierra esta issue cuando los overrides estén listos. Si la promoción se repite, se generará una issue nueva.

{{TEMPLATE_SECTION}}

### Plantillas sugeridas por entorno
{{OVERRIDES_BY_ENV}}
