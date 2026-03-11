# F5 Pool & Virtual Server Manager

Script Bash para la gestión automatizada de recursos en **F5 BIG-IP** mediante la API REST iControl. Permite crear, editar y eliminar Monitors TCP, Pools y Virtual Servers sin necesidad de acceder a la consola gráfica del F5.

---

## Requisitos

| Herramienta | Versión mínima | Uso |
|-------------|---------------|-----|
| `bash`      | 4.x           | Ejecución del script |
| `curl`      | cualquiera    | Llamadas a la API REST del F5 |
| `jq`        | 1.6+          | Procesamiento de JSON |

Verificar disponibilidad:
```bash
bash --version
curl --version
jq --version
```

---

## Instalación

```bash
# Clonar o copiar el script
cp f5_manager.sh /usr/local/bin/f5_manager.sh

# Dar permisos de ejecución
chmod +x f5_manager.sh
```

---

## Uso

```bash
./f5_manager.sh <acción> [archivo.json]
```

| Acción | Descripción |
|--------|-------------|
| `create` | Crea Monitor TCP + Pool + Virtual Server |
| `edit`   | Edita uno o varios recursos existentes |
| `delete` | Elimina uno o varios recursos existentes |

---

## Acciones

### `create` — Crear recursos

Crea los tres recursos en orden obligatorio: **Monitor TCP → Pool → Virtual Server**.

```bash
./f5_manager.sh create request.json
```

El script solicitará de forma interactiva:
- Credenciales del F5 (host, usuario, contraseña)
- Nombre del Pool (valida que no exista previamente)
- VLAN (opcional — valida que exista en el F5)
- Alias Service Port para el monitor (opcional — ENTER para usar `*:0`)

**Estructura del JSON de entrada:**
```json
{
  "description": "Balanceador para aplicación de facturación electrónica",
  "vs_name": "VS_TIN_ON_ENTORNO_DC_8080",
  "monitor": {
    "alias_service_port": 8080
  },
  "pool": {
    "lb_method": "least-connections-member",
    "members": [
      { "ip": "118.180.85.100", "port": 8080 },
      { "ip": "118.180.85.101", "port": 8080 },
      { "ip": "118.180.85.102", "port": 8080 }
    ]
  },
  "vs": {
    "destination": "192.168.0.174",
    "service_port": 8080,
    "destination_mask": "255.255.255.255",
    "source_address": "0.0.0.0/0",
    "snat": "automap"
  }
}
```

**Campos del JSON — Creación:**

| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| `description` | String | No | Descripción del pool |
| `vs_name` | String | Sí | Nombre del Virtual Server |
| `monitor.alias_service_port` | Integer | No | Alias Service Port del monitor TCP. Si se omite, usa `*:0` (mismo puerto del miembro) |
| `pool.lb_method` | String | No | Algoritmo de balanceo. Default: `least-connections-member` |
| `pool.members` | Array | Sí | Lista de nodos backend con IP y puerto |
| `vs.destination` | String | Sí | IP de destino del Virtual Server (asignada por Network Ops) |
| `vs.service_port` | Integer | Sí | Puerto de escucha del Virtual Server |
| `vs.destination_mask` | String | Sí | Máscara de red. Normalmente `255.255.255.255` |
| `vs.source_address` | String | No | Rango de IPs clientes permitidas. Default: `0.0.0.0/0` |
| `vs.snat` | String | No | Tipo de SNAT. Default: `automap` |

**Recursos creados automáticamente:**

| Recurso | Nombre generado |
|---------|----------------|
| Monitor TCP | `tcp_monitor_<POOL_NAME>` |
| Pool | Nombre ingresado interactivamente |
| Virtual Server | Tomado del campo `vs_name` del JSON |

---

### `edit` — Editar recursos

Edita recursos existentes. Puede ejecutarse de forma interactiva o con un JSON.

```bash
# Interactivo
./f5_manager.sh edit

# Desde archivo JSON
./f5_manager.sh edit edit_request.json
```

Al ejecutar, el script solicitará el nombre del Pool y luego mostrará el menú:

```
  1) Monitor TCP
  2) Pool
  3) Virtual Server
  4) Todo (monitor + pool + VS)
```

**Campos editables por recurso:**

**Monitor TCP:**
| Campo | Descripción |
|-------|-------------|
| `interval` | Intervalo entre verificaciones (segundos) |
| `timeout` | Tiempo máximo de espera. Debe ser >= (interval * 2) + 1 |
| `dest` | Alias Service Port en formato `*:<PUERTO>` |

**Pool:**
| Campo | Descripción |
|-------|-------------|
| `description` | Descripción del pool |
| `loadBalancingMode` | Algoritmo de balanceo |
| `monitor` | Monitor TCP asociado |
| `members` | Agregar / quitar / reemplazar / habilitar / deshabilitar miembros |

**Virtual Server:**
| Campo | Descripción |
|-------|-------------|
| `destination` | IP:PUERTO de destino |
| `mask` | Máscara de red |
| `source` | Rango de IPs clientes |
| `pool` | Pool backend asociado |
| `vlans` | VLAN(s) donde escucha el VS |
| `sourceAddressTranslation.type` | Tipo de SNAT |
| `ipProtocol` | Protocolo IP (tcp/udp) |
| `profiles` | Perfiles de protocolo |
| `enabled` / `disabled` | Estado del VS |

**Estructura del JSON de edición:**
```json
{
  "vs_name": "VS_TIN_ON_ENTORNO_DC_8080",
  "monitor": {
    "interval": 10,
    "timeout": 31,
    "dest": "*:9090"
  },
  "pool": {
    "description": "Nueva descripción",
    "lb_method": "round-robin",
    "monitor": "tcp_monitor_Pool_TIN_ON_ENTORNO_DC_8080",
    "members": [
      { "ip": "118.180.85.100", "port": 8080 },
      { "ip": "118.180.85.200", "port": 8080 }
    ]
  },
  "vs": {
    "destination": "192.168.0.174",
    "service_port": 9090,
    "destination_mask": "255.255.255.255",
    "source_address": "0.0.0.0/0",
    "pool": "Pool_TIN_ON_ENTORNO_DC_8080",
    "vlan": "vlan46",
    "snat": "automap",
    "ip_protocol": "tcp",
    "profile": "/Common/tcp",
    "enabled": "true"
  }
}
```

> **Nota:** Todos los campos del JSON de edición son opcionales. Solo se aplicarán los que estén presentes. Los campos omitidos mantienen su valor actual en el F5.

---

### `delete` — Eliminar recursos

Elimina recursos respetando el orden obligatorio de dependencias: **VS → Pool → Monitor**.

```bash
# Interactivo
./f5_manager.sh delete

# Desde archivo JSON
./f5_manager.sh delete delete_request.json
```

Al ejecutar, el script mostrará el menú:

```
  1) Conjunto completo  (VS + Pool + Monitor)
  2) Solo Virtual Server
  3) Solo Pool completo
  4) Solo un miembro del pool
  5) Solo Monitor TCP
```

> Todas las opciones solicitan **confirmación explícita** antes de ejecutar la eliminación.

**Estructura del JSON de eliminación:**
```json
{
  "vs_name":      "VS_TIN_ON_ENTORNO_DC_8080",
  "pool_name":    "Pool_TIN_ON_ENTORNO_DC_8080",
  "monitor_name": "tcp_monitor_Pool_TIN_ON_ENTORNO_DC_8080"
}
```

> Si `monitor_name` se omite del JSON, el script lo autogenera como `tcp_monitor_<pool_name>`.

---

## Flujo de Creación

```
INICIO
  │
  ▼
Leer credenciales F5
  │
  ▼
Leer nombre del Pool y VLAN (validación contra F5)
  │
  ▼
Validar JSON de entrada
  │
  ▼
PASO 1 — Monitor TCP
  ├─ ¿Existe? → Reutilizar
  └─ No existe → POST /mgmt/tm/ltm/monitor/tcp
  │
  ▼
PASO 2 — Pool
  └─ POST /mgmt/tm/ltm/pool  (con miembros y monitor)
  │
  ▼
PASO 3 — Virtual Server
  └─ POST /mgmt/tm/ltm/virtual  (apuntando al pool)
  │
  ▼
FIN — Recursos operativos
```

## Flujo de Eliminación

```
INICIO
  │
  ▼
Seleccionar opción de eliminación
  │
  ▼
Mostrar resumen + confirmación del operador
  │
  ▼
PASO 1 — DELETE Virtual Server
  │
  ▼
PASO 2 — DELETE Pool
  │
  ▼
PASO 3 — DELETE Monitor TCP
  │
  ▼
FIN
```

---

## Algoritmos de Balanceo Disponibles

| Valor | Descripción | Uso recomendado |
|-------|-------------|-----------------|
| `least-connections-member` | Al miembro con menos conexiones activas | **DEFAULT** — tráfico variable |
| `round-robin` | Distribuye equitativamente en orden | Servidores con capacidad similar |
| `least-connections-node` | Al nodo con menos conexiones | Múltiples pools por nodo |
| `fastest-node` | Al nodo con menor tiempo de respuesta | Servidores heterogéneos |
| `observed-member` | Basado en rendimiento observado | Tráfico dinámico |

---

## Alias Service Port — Comportamiento

El campo `alias_service_port` del JSON mapea al campo **Alias Service Port** de la GUI del F5 y al campo `dest` de la API iControl.

| Valor en JSON | dest en API | Comportamiento |
|---------------|-------------|----------------|
| Omitido / vacío | `*:0` | Monitorea el mismo puerto configurado en cada miembro del pool |
| `8080` | `*:8080` | Monitorea siempre el puerto 8080 sin importar el puerto del miembro |

> El **Alias Address** siempre es `*` (All Addresses). No es configurable en este script.

---

## Errores Comunes

| Código F5 | Mensaje | Causa | Solución |
|-----------|---------|-------|----------|
| `01020066` | Object already exists | El recurso ya existe | Usar un nombre diferente o reutilizar el existente |
| `01020066` | Object not found | El recurso no existe | Verificar nombre exacto del recurso |
| `01020036` | Still in use by... | Dependencia activa | Eliminar en orden: VS → Pool → Monitor |
| `01020036` | Invalid timeout value | Timeout inválido | Ajustar: timeout >= (interval * 2) + 1 |
| `01070022` | Monitor not found | Monitor no existe al crear pool | Crear el monitor antes que el pool |
| `01070335` | VLAN does not exist | VLAN no existe en F5 | Validar VLAN disponible o dejar vacío |
| `01070712` | Reference error | Dependencia activa sobre el recurso | Eliminar todas las referencias primero |
| `01070726` | Invalid dest format | Formato de dest incorrecto | Usar formato `*:<PUERTO>` |
| `01070734` | Invalid destination format | IP:PUERTO del VS incorrecto | Verificar formato `IP:PUERTO` |
| `401`      | Unauthorized | Credenciales incorrectas | Verificar usuario y contraseña del F5 |

---

## Consideraciones de Seguridad

- Las credenciales se solicitan de forma interactiva y **no se almacenan** en ningún archivo.
- El script usa `curl -sk` que deshabilita la validación del certificado SSL del F5. En entornos de producción PCI se recomienda reemplazar por `--cacert /ruta/certificado_f5.pem`.
- Se recomienda usar un **usuario de servicio** en el F5 con permisos mínimos sobre los endpoints: `ltm/pool`, `ltm/virtual`, `ltm/monitor/tcp` y `net/vlan` (solo lectura).
- Para entornos PCI-DSS, cada ejecución debe quedar registrada con número de ticket, usuario y timestamp.

---

## Limitaciones Actuales

| Limitación | Descripción |
|------------|-------------|
| Solo monitor TCP | No soporta creación de monitores HTTP, HTTPS ni otros tipos |
| Una VLAN por VS | El script soporta una sola VLAN por Virtual Server |
| Sin rollback automático | Si falla la creación del VS, el Pool queda huérfano y debe eliminarse manualmente |
| Sin validación de certificados SSL | Usa `-sk` en curl — pendiente corregir para producción PCI |
| Sin soporte multi-partition | Todos los recursos se crean en `/Common` |

---

## Estructura del Proyecto

```
.
├── f5_manager.sh       # Script principal
├── README.md           # Este archivo
└── examples/
    ├── create.json     # JSON de ejemplo para creación
    ├── edit.json       # JSON de ejemplo para edición
    └── delete.json     # JSON de ejemplo para eliminación
```
