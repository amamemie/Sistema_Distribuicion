# Instalación en la PC de la oficina (Windows)

Guía para dejar el sistema funcionando en la PC de escritorio de la oficina con Windows, con los
datos de la PC anterior. Pensada para que la siga una persona o Claude Code abierto en este
repositorio. Lo marcado **(persona)** necesita a alguien frente a la PC: permisos de
administrador, iniciar sesión en el navegador o tocar la BIOS.

## Resultado esperado

- El sistema corre con Docker Desktop (motor WSL 2) y arranca solo al encender la PC.
- Se usa desde la oficina en `http://localhost:8080` y desde los celulares en
  `https://inventario.taile52df7.ts.net` (Tailscale Funnel).
- Respaldo diario a las 23:00 en `respaldos/`.

## 1. Requisitos (persona)

1. **Virtualización activada** en la BIOS (Intel VT-x / AMD-V). En el Administrador de tareas →
   Rendimiento → CPU debe decir «Virtualización: Habilitado».
2. Instalar, con las opciones por defecto:
   - **Docker Desktop**: <https://www.docker.com/products/docker-desktop/>. Marcar «Use WSL 2».
     Al terminar pide reiniciar.
   - **Git for Windows**: <https://git-scm.com/download/win>.
   - **Tailscale**: <https://tailscale.com/download/windows>.
3. En Docker Desktop → *Settings → General*, activar **«Start Docker Desktop when you sign in»**.
4. Para que el sistema funcione sin que nadie inicie sesión tras un corte de luz, configurar el
   **inicio de sesión automático** de Windows (`netplwiz`) y, si la BIOS lo permite, **«Restore
   on AC power loss: Power On»**.
5. Energía: *Configuración → Sistema → Energía* → «Suspender: Nunca».

## 2. Código y datos

Los scripts son de Bash: se ejecutan en **Git Bash** (viene con Git for Windows), desde la carpeta
del proyecto.

1. **Acceso a GitHub (persona, una vez):** en Git Bash, `ssh-keygen -t ed25519 -C pc-oficina`
   y agregar el contenido de `~/.ssh/id_ed25519.pub` en GitHub → *Settings → SSH and GPG keys*.
2. Clonar: `git clone git@github.com:amamemie/Sistema_Distribuicion.git ~/sis_dis`
3. Copiar a `~/sis_dis/` el paquete `migracion_AAAAMMDD_HHMMSS.tar.gz` (llega por USB desde la
   PC anterior, creado con `scripts/migrar-exportar.sh`). **Contiene claves y datos: nunca se
   sube a Git ni se envía por internet.**
4. Con Docker Desktop abierto: `cd ~/sis_dis && scripts/migrar-importar.sh migracion_*.tar.gz`.
   Debe terminar con «Listo: sistema restaurado».
5. Comprobar: abrir `http://localhost:8080` e iniciar sesión con el usuario dueño.

Si `migrar-importar.sh` falla en Git Bash por rutas o permisos, se puede ejecutar dentro de WSL
(Ubuntu) con el proyecto clonado en el disco de Linux (`~/sis_dis`), que además es más rápido.

## 3. Enlace público (Tailscale Funnel)

1. **En la PC anterior:** `docker compose stop` y `sudo tailscale funnel --https=443 off`.
2. **(persona)** En <https://login.tailscale.com/admin/machines>, borrar la máquina
   «inventario» anterior para liberar el nombre.
3. **En la PC de la oficina (persona):** abrir Tailscale, iniciar sesión con la misma cuenta y
   renombrar este equipo a `inventario` (en la consola web: ⋯ → *Edit machine name*).
4. En una terminal **de administrador** (PowerShell):
   `tailscale funnel --bg 8080`
5. Verificar desde un celular con datos móviles: `https://inventario.taile52df7.ts.net`.

## 4. Respaldos diarios

Crear una tarea programada de Windows (*Programador de tareas* → «Crear tarea básica»): todos los
días a las 23:00, acción «Iniciar un programa»:

- Programa: `C:\Program Files\Git\bin\bash.exe`
- Argumentos: `-lc "cd ~/sis_dis && scripts/respaldo.sh >> respaldos/respaldo.log 2>&1"`

Copiar cada semana la carpeta `respaldos/` fuera de la PC (USB o Google Drive).

## 5. Verificación final

- Reiniciar la PC. Sin tocar nada, a los 2-3 minutos `http://localhost:8080` y el enlace público
  deben responder.
- `docker compose ps`: los 6 servicios en *Up* (backend y db en *healthy*).
- Ejecutar `scripts/respaldo.sh` una vez a mano y comprobar que aparecen los dos archivos en
  `respaldos/`.
