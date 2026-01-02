from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
from typing import Literal, Optional, List

app = FastAPI()

class HelixRequest(BaseModel):
    entorno: Literal["DEV", "QA", "PROD"]
    pci: Literal["SI", "NO"]
    dc: str
    tipo_requerimiento: Literal["NUEVO", "MODIFICAR", "ELIMINAR"]  # ← AGREGADO
    proyecto: str
    descripcion: str
    arquitecto: str
    ip: Optional[str] = None
    puerto: Optional[int] = None
    protocolo: Optional[Literal["HTTP", "HTTPS", "TCP", "UDP"]] = None
    puerto_escucha: Optional[int] = None
    tipo_modificacion: Optional[str] = None
    pool_members: Optional[List[str]] = []
    request_id: str
    # Nuevo para identificar aplicación a eliminar
    app_name_existente: Optional[str] = None

F5_CONFIG = {
    "DEV": {"host": "https://f5-dev.company.com", "tenant": "DEV_Tenant"},
    "QA": {"host": "https://f5-qa.company.com", "tenant": "QA_Tenant"},
    "PROD": {"host": "https://f5-prod.company.com", "tenant": "PROD_Tenant"}
}

F5_USER = "api_helix_user"
F5_PASS = "secure_password"

def generar_nombre_app(data: HelixRequest) -> str:
    pci_prefix = "PCI_" if data.pci == "SI" else ""
    return f"{pci_prefix}{data.proyecto}_{data.dc}_{data.entorno}"

def construir_as3_nuevo(data: HelixRequest) -> dict:
    """Crear nuevo Virtual Server"""
    f5_config = F5_CONFIG[data.entorno]
    app_name = generar_nombre_app(data)
    vs_name = f"vs_{app_name}"
    pool_name = f"pool_{app_name}"
    
    service_class_map = {
        "HTTP": "Service_HTTP",
        "HTTPS": "Service_HTTPS",
        "TCP": "Service_TCP",
        "UDP": "Service_UDP"
    }
    
    service_class = service_class_map.get(data.protocolo, "Service_HTTP")
    
    pool_config = {
        "class": "Pool",
        "monitors": ["tcp"] if data.protocolo in ["TCP", "UDP"] else ["http"],
        "members": [{
            "servicePort": data.puerto_escucha,
            "serverAddresses": data.pool_members,
            "enable": True
        }] if data.pool_members else []
    }
    
    vs_config = {
        "class": service_class,
        "virtualAddresses": [data.ip],
        "virtualPort": data.puerto,
        "pool": pool_name,
        "remark": f"Helix: {data.request_id} | Arq: {data.arquitecto}"
    }
    
    if data.protocolo == "HTTPS":
        vs_config["serverTLS"] = {"bigip": "/Common/clientssl"}
    
    as3_declaration = {
        "class": "AS3",
        "action": "deploy",
        "persist": True,
        "declaration": {
            "class": "ADC",
            "schemaVersion": "3.50.0",
            f5_config["tenant"]: {
                "class": "Tenant",
                app_name: {
                    "class": "Application",
                    "template": "generic",
                    "label": f"{data.proyecto} - {data.descripcion}",
                    vs_name: vs_config,
                    pool_name: pool_config
                }
            }
        }
    }
    
    return as3_declaration

def construir_as3_modificar(data: HelixRequest) -> dict:
    """Modificar Virtual Server existente"""
    f5_config = F5_CONFIG[data.entorno]
    app_name = data.app_name_existente or generar_nombre_app(data)
    
    # Obtener configuración actual completa del tenant
    current_tenant = obtener_tenant_completo(data.entorno)
    
    if not current_tenant or app_name not in current_tenant:
        raise HTTPException(status_code=404, detail=f"Aplicación {app_name} no encontrada")
    
    # Copiar configuración actual
    app_actual = current_tenant[app_name].copy()
    
    # Buscar VS y Pool
    vs_name = None
    pool_name = None
    
    for key, value in app_actual.items():
        if isinstance(value, dict):
            if value.get("class", "").startswith("Service_"):
                vs_name = key
            elif value.get("class") == "Pool":
                pool_name = key
    
    if not vs_name or not pool_name:
        raise HTTPException(status_code=400, detail="No se encontró VS o Pool en la aplicación")
    
    # MODIFICACIONES SEGÚN TIPO
    tipo_mod = (data.tipo_modificacion or "").upper()
    
    if "POOL" in tipo_mod or "MIEMBRO" in tipo_mod:
        # Modificar miembros del pool
        if data.pool_members:
            app_actual[pool_name]["members"] = [{
                "servicePort": data.puerto_escucha or app_actual[pool_name]["members"][0]["servicePort"],
                "serverAddresses": data.pool_members,
                "enable": True
            }]
    
    if "PUERTO" in tipo_mod:
        # Cambiar puerto del VS
        if data.puerto:
            app_actual[vs_name]["virtualPort"] = data.puerto
    
    if "IP" in tipo_mod:
        # Cambiar IP del VS
        if data.ip:
            app_actual[vs_name]["virtualAddresses"] = [data.ip]
    
    if "PROTOCOLO" in tipo_mod:
        # Cambiar protocolo (requiere recrear VS)
        if data.protocolo:
            service_class_map = {
                "HTTP": "Service_HTTP",
                "HTTPS": "Service_HTTPS",
                "TCP": "Service_TCP",
                "UDP": "Service_UDP"
            }
            app_actual[vs_name]["class"] = service_class_map[data.protocolo]
            
            # Ajustar SSL si es HTTPS
            if data.protocolo == "HTTPS":
                app_actual[vs_name]["serverTLS"] = {"bigip": "/Common/clientssl"}
            else:
                app_actual[vs_name].pop("serverTLS", None)
    
    # Actualizar remark con info del ticket
    app_actual[vs_name]["remark"] = f"Modificado - Helix: {data.request_id}"
    
    # Reconstruir tenant completo con la app modificada
    current_tenant[app_name] = app_actual
    
    return {
        "class": "AS3",
        "action": "deploy",
        "persist": True,
        "declaration": {
            "class": "ADC",
            "schemaVersion": "3.50.0",
            f5_config["tenant"]: {
                "class": "Tenant",
                **current_tenant
            }
        }
    }

def construir_as3_eliminar(data: HelixRequest) -> dict:
    """Eliminar aplicación completa del F5"""
    f5_config = F5_CONFIG[data.entorno]
    app_name = data.app_name_existente or generar_nombre_app(data)
    
    # Obtener tenant completo
    current_tenant = obtener_tenant_completo(data.entorno)
    
    if not current_tenant or app_name not in current_tenant:
        raise HTTPException(status_code=404, detail=f"Aplicación {app_name} no existe")
    
    # Remover la aplicación del tenant
    current_tenant.pop(app_name)
    
    # Si el tenant queda vacío, agregar una app dummy para evitar errores
    if not current_tenant or len(current_tenant) == 0:
        current_tenant["dummy_app"] = {
            "class": "Application",
            "template": "generic"
        }
    
    return {
        "class": "AS3",
        "action": "deploy",
        "persist": True,
        "declaration": {
            "class": "ADC",
            "schemaVersion": "3.50.0",
            f5_config["tenant"]: {
                "class": "Tenant",
                **current_tenant
            }
        }
    }

def obtener_tenant_completo(entorno: str) -> dict:
    """Obtiene toda la configuración del tenant"""
    f5_config = F5_CONFIG[entorno]
    
    response = requests.get(
        f"{f5_config['host']}/mgmt/shared/appsvcs/declare/{f5_config['tenant']}",
        auth=(F5_USER, F5_PASS),
        verify=False,
        timeout=30
    )
    
    if response.status_code == 200:
        data = response.json()
        # Remover metadatos de AS3
        tenant_data = data.copy()
        tenant_data.pop("class", None)
        tenant_data.pop("schemaVersion", None)
        return tenant_data
    
    return {}

@app.post("/api/helix-to-f5")
async def procesar_solicitud_helix(data: HelixRequest):
    """Endpoint principal - CRUD completo"""
    
    try:
        if data.entorno not in F5_CONFIG:
            raise HTTPException(status_code=400, detail=f"Entorno {data.entorno} no válido")
        
        # Seleccionar operación
        if data.tipo_requerimiento == "NUEVO":
            as3_declaration = construir_as3_nuevo(data)
            accion = "creada"
            
        elif data.tipo_requerimiento == "MODIFICAR":
            as3_declaration = construir_as3_modificar(data)
            accion = "modificada"
            
        elif data.tipo_requerimiento == "ELIMINAR":
            as3_declaration = construir_as3_eliminar(data)
            accion = "eliminada"
            
        else:
            raise HTTPException(status_code=400, detail="Tipo de requerimiento no válido")
        
        # Enviar a F5
        f5_config = F5_CONFIG[data.entorno]
        
        response = requests.post(
            f"{f5_config['host']}/mgmt/shared/appsvcs/declare",
            auth=(F5_USER, F5_PASS),
            json=as3_declaration,
            verify=False,
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        if response.status_code in [200, 202]:
            result = response.json()
            
            # Verificar si AS3 reportó errores
            if result.get("results"):
                for res in result["results"]:
                    if res.get("code") not in [200, 202]:
                        raise HTTPException(
                            status_code=500,
                            detail=f"AS3 Error: {res.get('message', 'Unknown error')}"
                        )
            
            return {
                "status": "success",
                "message": f"Configuración {accion} exitosamente en {data.entorno}",
                "f5_response": result,
                "application_name": data.app_name_existente or generar_nombre_app(data),
                "tenant": f5_config["tenant"],
                "helix_request_id": data.request_id,
                "action": data.tipo_requerimiento
            }
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Error F5: {response.text}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

# Endpoint adicional para consultar aplicaciones existentes
@app.get("/api/f5-apps/{entorno}")
async def listar_aplicaciones(entorno: str):
    """Listar todas las aplicaciones en un tenant"""
    if entorno not in F5_CONFIG:
        raise HTTPException(status_code=400, detail="Entorno no válido")
    
    tenant_config = obtener_tenant_completo(entorno)
    
    apps = []
    for app_name, app_config in tenant_config.items():
        if isinstance(app_config, dict) and app_config.get("class") == "Application":
            apps.append({
                "name": app_name,
                "label": app_config.get("label", ""),
                "template": app_config.get("template", "")
            })
    
    return {"entorno": entorno, "aplicaciones": apps}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "operations": ["NUEVO", "MODIFICAR", "ELIMINAR"]}