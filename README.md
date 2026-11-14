# Chat Distribuido — Proyecto Final Sistemas Distribuidos

Servidor de chat del grupo para el proyecto final de Sistemas Distribuidos UIS.
Se conecta al servidor central del curso y permite que los usuarios del grupo participen en la sala global `#general`.

## Cómo levantar el sistema

1. Clonar el repositorio
2. Crear el archivo `.env` con las variables de entorno (ver sección siguiente)
3. Ejecutar:

```bash
docker compose up
```

## Variables de entorno

Crear un archivo `.env` en la raíz con:

```
GROUP_NAME=gN          # Nombre del grupo, ej: g3
GROUP_URL=http://...   # URL pública de este servidor
CENTRAL_URL=http://... # URL del servidor central del profesor
```

## Estructura del proyecto

```
server/        - Servidor FastAPI (lógica principal)
client/        - Cliente de línea de comandos
experiment/    - Script de medición del experimento
```

## Integrantes

- (nombre 1)
- (nombre 2)  
- (nombre 3)
