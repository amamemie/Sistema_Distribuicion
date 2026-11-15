# ADR 0004 — Servidor gratuito en Oracle Cloud (Always Free)

- **Estado:** aceptada (2026-11-15). Reemplaza la PC de la oficina de la [ADR 0002](0002-despliegue-en-oficina.md)
  como servidor de producción.

## Contexto

El cliente quiere que el sistema funcione la mayor parte del día sin pagar servidor (D-14) y sin
depender de que una PC de la oficina esté encendida. El sistema necesita PostgreSQL, Redis, la API,
el worker con OCR local (≈ 1-2 GB de memoria), el programador de tareas y HTTPS (cámara en
celulares).

## Opciones

| Opción | Costo | Por qué sí / por qué no |
|---|---|---|
| **Oracle Cloud Always Free (Ampere A1)** | USD 0 | Máquina real 24/7 con 2 OCPU y 12 GB: entra todo el `docker compose`. Pide tarjeta para verificar y puede recuperar instancias inactivas. |
| Render / Railway / Fly.io (planes gratis) | USD 0 con límites | Se duermen, sin worker en segundo plano y la base gratuita caduca o es mínima. |
| Google Cloud e2-micro | USD 0 | 1 GB de memoria: no alcanza para la base de datos y el OCR. |
| PC de la oficina + Tailscale Funnel | USD 0 | Funciona solo mientras la PC esté encendida. |

## Decisión

- Oracle Cloud Always Free, VM.Standard.A1.Flex (ARM) de 2 OCPU / 12 GB con Ubuntu 24.04.
- El mismo `docker-compose.yml`; Caddy obtiene el certificado de Let's Encrypt para
  `<ip>.sslip.io` (sin comprar dominio) o para un dominio propio.
- `scripts/desplegar.sh` envía `main` por SSH y `scripts/instalar-servidor.sh` prepara el servidor
  (Docker, firewall, `.env` con claves aleatorias, respaldo diario por cron).
- Guía para el cliente: [despliegue-oracle.md](../despliegue-oracle.md).

## Consecuencias

- Los respaldos diarios quedan en el servidor; hay que copiarlos fuera periódicamente.
- Para evitar que Oracle recupere la instancia por baja actividad se recomienda pasar la cuenta a
  Pay As You Go (sigue sin costo dentro de los límites gratuitos) con una alerta de presupuesto.
