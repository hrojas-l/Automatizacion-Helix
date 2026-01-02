# Helix to F5 Automation

API que automatiza la creación, modificación y eliminación de Virtual Servers en F5 desde tickets de BMC Helix.

## ¿Qué hace?

Recibe solicitudes desde **Helix** y automáticamente configura balanceadores de carga **F5** sin intervención manual.

### Operaciones soportadas:
-  **CREAR** nuevo Virtual Server con pool de servidores
-  **MODIFICAR** configuración existente (IPs, puertos, servidores)
-  **ELIMINAR** aplicaciones del F5

---

## Instalación

```bash
# Instalar dependencias
pip install -r requirements.txt

# Configurar credenciales en main.py
F5_USER = "tu_usuario"
F5_PASS = "tu_password"
```

---

## Ejecutar

```bash
# Iniciar API
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Documentación interactiva
http://localhost:8000/docs
```

---

## Uso Básico

### Crear Virtual Server

```bash
curl -X POST http://localhost:8000/api/helix-to-f5 \
  -H "Content-Type: application/json" \
  -d '{
    "entorno": "DEV",
    "pci": "NO",
    "dc": "DC1",
    "tipo_requerimiento": "NUEVO",
    "proyecto": "MiApp",
    "descripcion": "Aplicación web",
    "arquitecto": "Juan Perez",
    "ip": "10.10.10.100",
    "puerto": 443,
    "protocolo": "HTTPS",
    "puerto_escucha": 8080,
    "pool_members": ["192.168.1.10", "192.168.1.11"],
    "request_id": "REQ001"
  }'
```

### Modificar Pool

```bash
curl -X POST http://localhost:8000/api/helix-to-f5 \
  -H "Content-Type: application/json" \
  -d '{
    "entorno": "DEV",
    "tipo_requerimiento": "MODIFICAR",
    "tipo_modificacion": "POOL",
    "app_name_existente": "MiApp_DC1_DEV",
    "pool_members": ["192.168.1.10", "192.168.1.11", "192.168.1.12"],
    "puerto_escucha": 8080,
    "request_id": "REQ002",
    "proyecto": "MiApp",
    "dc": "DC1",
    "pci": "NO",
    "descripcion": "Agregar servidor",
    "arquitecto": "Juan Perez"
  }'
```

### Eliminar Aplicación

```bash
curl -X POST http://localhost:8000/api/helix-to-f5 \
  -H "Content-Type: application/json" \
  -d '{
    "entorno": "DEV",
    "tipo_requerimiento": "ELIMINAR",
    "app_name_existente": "MiApp_DC1_DEV",
    "request_id": "REQ003",
    "proyecto": "MiApp",
    "dc": "DC1",
    "pci": "NO",
    "descripcion": "Eliminar app",
    "arquitecto": "Juan Perez"
  }'
```

---

## Endpoints

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/helix-to-f5` | Crear/Modificar/Eliminar VS |
| GET | `/api/f5-apps/{entorno}` | Listar aplicaciones |
| GET | `/health` | Health check |

---

## Configuración

Edita `main.py` para configurar tus entornos F5:

```python
F5_CONFIG = {
    "DEV": {"host": "https://f5-dev.company.com", "tenant": "DEV_Tenant"},
    "QA": {"host": "https://f5-qa.company.com", "tenant": "QA_Tenant"},
    "PROD": {"host": "https://f5-prod.company.com", "tenant": "PROD_Tenant"}
}
```

---

## Tipos de Modificación

Al usar `tipo_requerimiento: "MODIFICAR"`, especifica en `tipo_modificacion`:

- **POOL** - Cambiar servidores backend
- **PUERTO** - Cambiar puerto del Virtual Server
- **IP** - Cambiar IP virtual
- **PROTOCOLO** - Cambiar entre HTTP/HTTPS/TCP/UDP

---

## Flujo de Trabajo

```
┌─────────────┐       ┌──────────────┐       ┌─────────────┐
│ BMC Helix   │──────▶│  FastAPI     │──────▶│  F5 BIG-IP  │
│  (Tickets)  │       │  (AS3 Build) │       │  (Config)   │
└─────────────┘       └──────────────┘       └─────────────┘
```

1. Helix envía solicitud con datos del ticket
2. API construye declaración AS3 para F5
3. F5 aplica la configuración automáticamente

---

## Respuesta Exitosa

```json
{
  "status": "success",
  "message": "Configuración creada exitosamente en DEV",
  "application_name": "MiApp_DC1_DEV",
  "tenant": "DEV_Tenant",
  "helix_request_id": "REQ001",
  "action": "NUEVO"
}
```

---

## Requisitos

- Python 3.8+
- F5 BIG-IP con AS3 instalado
- Credenciales con permisos de administración en F5

---

## Seguridad

⚠️ **En producción:**
- Usa variables de entorno para credenciales
- Habilita HTTPS
- Implementa autenticación (JWT, OAuth2)
- Activa rate limiting

---

## Soporte

Para problemas o sugerencias, abre un issue en GitHub.

## Licencia

MIT License
