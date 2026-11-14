# ADR 0002 — Despliegue en un equipo de la oficina

- **Estado:** propuesta; la parte de acceso remoto y HTTPS se decide antes de la Fase 2.

## Contexto

El cliente quiere costo de servidor cero o mínimo (D-14): el sistema correrá en una PC de la
oficina y se usará desde 4–5 dispositivos. En la Fase 2 los encargados fotografiarán OC con el
celular, y **los navegadores solo permiten usar la cámara en páginas servidas por HTTPS** (o en
`localhost`).

## Decisión (Fase 0)

- Todo corre con `docker compose up -d` en la PC de la oficina: PostgreSQL, Redis, API, worker y
  Caddy (sirve el frontend y hace de proxy de la API).
- En la red local se accede por `http://IP-DE-LA-PC:8080`.
- Respaldos diarios con `scripts/respaldo.sh` (cron), copiados fuera del equipo.

## Opciones para HTTPS y acceso desde fuera de la oficina (por decidir)

| Opción | Costo | Ventajas | Desventajas |
|---|---|---|---|
| **Tailscale** (VPN entre dispositivos; certificados `*.ts.net`) | Gratis para uso personal y equipos pequeños (verificar condiciones vigentes) | HTTPS real, sin abrir puertos, funciona fuera de la oficina | Hay que instalar la app de Tailscale en cada celular |
| **Cloudflare Tunnel** con dominio propio | Túnel gratis; dominio ~10 USD/año | URL pública con HTTPS, no requiere app en los celulares | Expone el sistema a internet (se apoya en el login); depende de Cloudflare |
| **Caddy con CA interna** en la red local | Gratis | Sin servicios externos | Hay que instalar el certificado raíz en cada celular; solo funciona dentro de la oficina |

**Recomendación preliminar:** Tailscale, por ser gratuito, no exponer el sistema a internet y
funcionar desde cualquier lugar.

## Estado actual (2026-11-14)

- La red Wi-Fi de pruebas aísla a los clientes entre sí: los celulares no llegan a la PC por la IP
  local. Confirmado con una captura de tráfico.
- Para las pruebas se usa **Tailscale Funnel**, elegido por el usuario: publica el sistema en
  `https://<equipo>.<tailnet>.ts.net` con HTTPS y sin instalar nada en los celulares.
  - Contrapartida: el sistema es accesible desde internet. Se protege con contraseñas, bloqueo
    por intentos fallidos y `COOKIE_SEGURA=true`.
  - Activar: `sudo tailscale funnel --bg 8080` · Desactivar: `sudo tailscale funnel --https=443 off`.
- Para la producción en la oficina sigue pendiente elegir entre Funnel y Tailscale privado.

## Riesgos

- Si la PC de la oficina se apaga o falla, nadie puede trabajar. Mitigación: respaldos fuera del
  equipo y procedimiento documentado de restauración en otra PC.
- Recursos: la Fase 2 añade OCR local (~2–4 GB de RAM adicionales). Hay que confirmar las
  características de la PC.
