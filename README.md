
# SNOMED Annotator (demo)

Servicio **listo para desplegar** que recibe texto clínico en español y devuelve conceptos SNOMED CT detectados usando el servidor público **Snowstorm** (demo). **No es para producción**. Si querés producción, montá tu propio Snowstorm y cambiá la variable `SNOWSTORM_BASE`.

## 1) Desplegar en Render (sin programar)

1. Creá un repositorio en GitHub llamado `snomed-annotator`.
2. Subí estos 4 archivos: `main.py`, `requirements.txt`, `render.yaml`, este `README.md`.
3. En [Render](https://render.com), elegí **New > Web Service** y conectá tu repo.
4. Render detectará `render.yaml`. Aceptá los valores por defecto.
5. Esperá a que figure **Live**. Vas a tener una URL tipo `https://snomed-annotator.onrender.com`.

> Variables ya preconfiguradas (en `render.yaml`):
> - `SNOWSTORM_BASE=https://snowstorm.snomedtools.org` (servidor público de demo)
> - `ACCEPT_LANGUAGE=es` (resultados en español si existen)

## 2) Probar

```bash
# Salud
curl -s https://TU-URL/healthz

# POST de ejemplo
curl -s -X POST https://TU-URL/annotate \
  -H "Content-Type: application/json" \
  -d '{"text":"Paciente con infarto agudo de miocardio y fibrilación auricular. Niega dolor torácico. PA 150/95 mmHg."}' | jq .
```

Respuesta (ejemplo recortado):
```json
{
  "matches": [
    {
      "match": "infarto agudo de miocardio",
      "conceptId": "22298006",
      "fsn": "Infarto agudo de miocardio (trastorno)",
      "semanticTag": "trastorno",
      "offsets": [{"start": 15, "end": 41}]
    },
    {
      "match": "fibrilación auricular",
      "conceptId": "49436004",
      "fsn": "Fibrilación auricular (trastorno)",
      "semanticTag": "trastorno",
      "offsets": [{"start": 44, "end": 65}]
    }
  ],
  "candidates": ["Paciente","con","infarto","agudo","..."],
  "lang": "es",
  "source": "https://snowstorm.snomedtools.org",
  "disclaimer": "Demo only ..."
}
```

> Los números como `150/95 mmHg` no son descripciones en SNOMED, por eso rara vez vuelven como “match”. En producción podrías tratarlos como **valores** (no conceptos) con otra lógica.

## 3) Integración rápida (sidebar)

```html
<script>
async function enviarAHerramienta(texto) {
  const r = await fetch("https://TU-URL/annotate", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ text: texto })
  });
  const data = await r.json();
  console.log("SNOMED:", data.matches);
  // acá podés resaltar en el DOM usando data.matches[i].offsets
}
</script>
```

## 4) Cambios mínimos útiles
- **Limitar llamadas**: `max_candidates` en el body (por defecto 60).
- **Idioma**: cambiá `ACCEPT_LANGUAGE` a `es-AR`, `es` o `en`.

## 5) Avisos importantes
- Este servicio usa **Snowstorm público (demo)** y puede rate‑limitar o cambiar.
- Para producción, **hosteá tu propio Snowstorm** con tus ediciones (AR/ES).
- Cumplí licencias de SNOMED CT según tu país/afiliación.

---

Hecho para pruebas rápidas desde un sidebar.
