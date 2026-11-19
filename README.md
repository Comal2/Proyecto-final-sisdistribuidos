# Chat Distribuido — Proyecto Final Sistemas Distribuidos

> Servidor de chat del grupo **SAA** para el proyecto final de Sistemas Distribuidos UIS.
> Se conecta al servidor central del curso y permite que los usuarios del grupo participen en la sala global `#general`.

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-3-003B57?logo=sqlite&logoColor=white)

---

## Levantar el sistema

```bash
# 1. Clonar el repositorio
git clone <url-del-repo>
cd <carpeta>

# 2. Crear el archivo .env con las variables de entorno
# (ver sección Variables de entorno)

# 3. Levantar con Docker Compose
docker compose up
```

> El servidor queda disponible en `http://localhost:8000`

---

## Variables de entorno

Crear un archivo `.env` en la raíz del proyecto:

```
GROUP_NAME=SAA          # Nombre del grupo
GROUP_URL=http://...    # URL pública de este servidor
CENTRAL_URL=http://...  # URL del servidor central del profesor
DB_PATH=/app/data/chat.db
```

---

## Endpoints disponibles

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/fed/health` | Estado del servidor y reloj de Lamport actual |
| `POST` | `/fed/messages` | Recibir mensaje del servidor central |
| `POST` | `/users` | Crear usuario local |
| `POST` | `/messages` | Enviar mensaje a `#general` |
| `GET` | `/messages?since=N` | Historial desde un valor de Lamport |

---

## Cliente de línea de comandos

```bash
python client/client.py <nombre_usuario>
```

Muestra el historial de `#general` y permite enviar mensajes desde la terminal.

---

## Experimento

El proyecto incluye un script para medir la pérdida de mensajes ante una caída del servidor:

```bash
docker compose up -d
python experiment/measure.py
```

**Resultados obtenidos (3 repeticiones, 30 mensajes c/u, caída de 5s):**

| Rep | Enviados | Rechazados en caída | En historial | Perdidos en BD |
|-----|----------|---------------------|--------------|----------------|
| 1   | 30       | 2                   | 28           | 0              |
| 2   | 30       | 2                   | 28           | 0              |
| 3   | 30       | 2                   | 28           | 0              |

---

## Estructura del proyecto

```
proyecto-final/
├── server/
│   ├── main.py          # Endpoints FastAPI y arranque
│   ├── models.py        # Base de datos SQLite
│   ├── lamport.py       # Reloj de Lamport (thread-safe)
│   └── federation.py    # Comunicación con servidor central
├── client/
│   └── client.py        # Cliente CLI con colores
├── experiment/
│   └── measure.py       # Script de medición del experimento
├── pruebas.http         # Peticiones REST Client para VS Code
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---

## Integrantes

| Nombre | Rol |
|--------|-----|
| Ángel Camilo Pachón Padilla | Desarrollo del servidor, cliente y experimento |
| Sharith Geraldine Gamboa Delgado | Diseño del póster |
| Angie Valentina Suárez Duarte | Script y narración del video |

---

*Universidad Industrial de Santander — Sistemas Distribuidos 2026*
