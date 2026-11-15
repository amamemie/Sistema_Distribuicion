# Despliegue en Oracle Cloud (Always Free)

El sistema corre las 24 horas en una máquina virtual gratuita de Oracle Cloud, con HTTPS. Decisión
en [ADR 0004](adr/0004-servidor-oracle-always-free.md).

## 1. Crear la cuenta (una sola vez)

1. Entre a <https://signup.cloud.oracle.com> y regístrese con el correo de la empresa.
2. **Región principal (Home Region):** elija la más cercana a Bolivia con disponibilidad, por
   ejemplo **Brazil East (São Paulo)** o **Chile Central (Santiago)**. **No se puede cambiar
   después.**
3. Oracle pide una tarjeta **solo para verificar la identidad**. La cuenta gratuita no cobra
   mientras se usen solo recursos «Always Free».

## 2. Crear la máquina virtual

Menú ☰ → **Compute → Instances → Create instance**:

| Campo | Valor |
|---|---|
| Name | `inventario` |
| Image | **Canonical Ubuntu 24.04** |
| Shape | **Ampere → VM.Standard.A1.Flex**, **2 OCPU y 12 GB** de memoria (lo máximo gratuito) |
| Networking | Crear una VCN nueva con subred **pública**; «Assign a public IPv4 address» activado |
| Add SSH keys | «Paste public keys» y pegar la clave pública que le indiquen (la del equipo que despliega) |
| Boot volume | 50 GB (el plan gratuito incluye hasta 200 GB en total) |

Si dice «Out of capacity», pruebe otro *Availability Domain* o vuelva a intentar más tarde.

Anote la **IP pública** de la instancia.

## 3. Abrir los puertos 80 y 443

Instancia → subred → **Security List** por defecto → **Add Ingress Rules**:

- Source CIDR `0.0.0.0/0`, protocolo TCP, puerto de destino **80**.
- Lo mismo con el puerto **443**.

(El puerto 22 para SSH ya viene abierto.)

## 4. Instalar el sistema (desde el equipo que despliega)

```bash
DUENO_CORREO=dueno@distribuidora.bo DUENO_PASSWORD='...' DUENO_NOMBRE=Dueno \
  scripts/desplegar.sh ubuntu@IP_PUBLICA
```

El script envía el código, instala Docker, abre el firewall de Ubuntu, genera el `.env` con claves
aleatorias, levanta todo y crea el usuario dueño. La dirección queda en
`https://IP-CON-GUIONES.sslip.io` (gratuita, con certificado de Let's Encrypt). Con un dominio
propio: agregue `SITIO_DIRECCION=inventario.midominio.bo` (con un registro DNS A hacia la IP).

**Actualizar** a una versión nueva de `main`: `scripts/desplegar.sh ubuntu@IP_PUBLICA`.
Los datos no se tocan y las migraciones se aplican solas.

## 5. Respaldos

- Todos los días a las 23:00 se guarda la base de datos y los archivos en `~/sis_dis/respaldos/`
  del servidor; se conservan 30 días.
- **Copiarlos fuera del servidor** (p. ej. una vez por semana, a la PC de la oficina):

  ```bash
  rsync -av ubuntu@IP_PUBLICA:sis_dis/respaldos/ respaldos-servidor/
  ```

## Riesgos del plan gratuito

- **Recuperación de instancias inactivas:** Oracle puede detener una instancia gratuita si durante
  7 días usa menos del 20 % de CPU, red y memoria. Este sistema usa poco, así que el riesgo existe.
  Para evitarlo, pase la cuenta a **Pay As You Go** (Billing → Upgrade): sigue sin costo mientras
  se usen solo recursos Always Free. Cree además un **presupuesto con alerta de USD 1**
  (Billing → Budgets) para enterarse de cualquier cargo.
- **Límites:** Oracle redujo en 2026 la cuota gratuita de Ampere de 4 OCPU / 24 GB a
  2 OCPU / 12 GB. Si una instancia supera la cuota, la apagan. Use 2 OCPU y 12 GB o menos.
- **Sin garantía de servicio:** es un plan gratuito. Los respaldos fuera del servidor son la
  protección real.
