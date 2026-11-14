import asyncio
import uuid
import logging
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager

from server.lamport import clock
from server.models import init_db, create_user, user_exists, save_message, get_history
from server import federation

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    await federation.recover_history()
    asyncio.create_task(federation.register_loop())
    asyncio.create_task(federation.heartbeat_loop())
    logger.info("Servidor iniciado")
    yield

app = FastAPI(lifespan=lifespan)


# ---------- Schemas ----------

class UserIn(BaseModel):
    username: str

class MessageIn(BaseModel):
    from_user: str
    body: str

class FedMessage(BaseModel):
    id: str
    from_: str = None
    origin: str
    lamport: int
    sent_at: str
    body: str

    model_config = {"populate_by_name": True}

    @classmethod
    def from_dict(cls, data: dict):
        data = dict(data)
        data["from_"] = data.pop("from", None)
        return cls(**data)


# ---------- Endpoints de federacion (los llama el servidor central) ----------

@app.get("/fed/health")
def fed_health():
    return {"server": federation.GROUP_NAME, "lamport": clock.value}


@app.post("/fed/messages")
async def fed_receive(payload: dict):
    msg = FedMessage.from_dict(payload)

    clock.update(msg.lamport)

    saved = save_message(
        id=msg.id,
        from_user=msg.from_,
        origin=msg.origin,
        lamport=msg.lamport,
        sent_at=msg.sent_at,
        body=msg.body
    )

    if saved:
        logger.info(f"Recibido: id={msg.id} de={msg.from_} lamport={msg.lamport}")
    else:
        logger.info(f"Duplicado descartado: id={msg.id}")

    return JSONResponse(status_code=200, content={"status": "ok"})


# ---------- Endpoints para los clientes del grupo ----------

@app.post("/users", status_code=201)
def register_user(body: UserIn):
    username = f"{body.username}@{federation.GROUP_NAME}"
    created = create_user(username, datetime.now(timezone.utc).isoformat())
    if not created:
        raise HTTPException(status_code=409, detail="Usuario ya existe")
    logger.info(f"Usuario creado: {username}")
    return {"username": username}


@app.post("/messages", status_code=202)
async def send_message(body: MessageIn):
    if not user_exists(body.from_user):
        raise HTTPException(status_code=404, detail="Usuario no existe")

    lamport = clock.tick()
    msg_id = str(uuid.uuid4())
    sent_at = datetime.now(timezone.utc).isoformat()

    save_message(
        id=msg_id,
        from_user=body.from_user,
        origin=federation.GROUP_NAME,
        lamport=lamport,
        sent_at=sent_at,
        body=body.body
    )

    message = {
        "id": msg_id,
        "from": body.from_user,
        "origin": federation.GROUP_NAME,
        "lamport": lamport,
        "sent_at": sent_at,
        "body": body.body
    }

    logger.info(f"Enviando: id={msg_id} de={body.from_user} lamport={lamport}")
    asyncio.create_task(federation.send_to_central(message))

    return {"id": msg_id, "lamport": lamport}


@app.get("/messages")
def get_messages(since: int = 0):
    return get_history(since_lamport=since)
