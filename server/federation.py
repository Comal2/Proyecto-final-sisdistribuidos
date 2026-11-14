import asyncio
import httpx
import os
import logging

from server.lamport import clock
from server.models import save_message

logger = logging.getLogger(__name__)

CENTRAL_URL       = os.getenv("CENTRAL_URL", "")
GROUP_NAME        = os.getenv("GROUP_NAME", "")
GROUP_URL         = os.getenv("GROUP_URL", "")
REGISTER_INTERVAL = int(os.getenv("REGISTER_INTERVAL", "30"))
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "10"))
MAX_FAILURES      = int(os.getenv("MAX_HEARTBEAT_FAILURES", "3"))

central_up = True
_pending: list[dict] = []
_failures = 0


async def _post_with_backoff(client: httpx.AsyncClient, url: str, payload: dict) -> bool:
    """POST con reintentos exponenciales.
    Retorna True si se entrego (o es 4xx y no hay que reintentar).
    Retorna False si fallaron todos los intentos (5xx o red).
    """
    delay = 1
    for attempt in range(6):
        try:
            r = await client.post(url, json=payload, timeout=5.0)
            if 400 <= r.status_code < 500:
                logger.error(f"HTTP {r.status_code} en {url} - descartado: id={payload.get('id', '')}")
                return True  # no reintentar
            if r.status_code < 400:
                logger.info(f"Entregado: id={payload.get('id', '')} lamport={payload.get('lamport', '')}")
                return True
            logger.warning(f"Intento {attempt + 1}: HTTP {r.status_code} en {url}")
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            logger.warning(f"Intento {attempt + 1}: error de red en {url}: {e}")

        if attempt < 5:
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60)

    logger.error(f"No entregado tras 6 intentos: id={payload.get('id', '')}")
    return False


async def send_to_central(message: dict):
    """Envia un mensaje al servidor central. Si esta caido, lo encola."""
    if not central_up:
        logger.info(f"Central caida - encolando: id={message['id']}")
        _pending.append(message)
        return

    async with httpx.AsyncClient() as client:
        ok = await _post_with_backoff(client, f"{CENTRAL_URL}/messages", message)
        if not ok:
            _pending.append(message)


async def _flush_pending():
    """Envia los mensajes acumulados durante la caida del servidor central."""
    if not _pending:
        return
    logger.info(f"Enviando {len(_pending)} mensajes pendientes")
    async with httpx.AsyncClient() as client:
        sent = []
        for msg in list(_pending):
            ok = await _post_with_backoff(client, f"{CENTRAL_URL}/messages", msg)
            if ok:
                sent.append(msg)
        for msg in sent:
            _pending.remove(msg)


async def recover_history():
    """Pide al servidor central los mensajes posteriores al ultimo lamport conocido."""
    since = clock.value
    logger.info(f"Recuperando historial desde lamport={since}")
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{CENTRAL_URL}/history",
                params={"since": since},
                timeout=10.0
            )
            if r.status_code == 200:
                for msg in r.json():
                    saved = save_message(
                        id=msg["id"],
                        from_user=msg["from"],
                        origin=msg["origin"],
                        lamport=msg["lamport"],
                        sent_at=msg["sent_at"],
                        body=msg["body"]
                    )
                    if saved:
                        clock.update(msg["lamport"])
                        logger.info(f"Recuperado: id={msg['id']} lamport={msg['lamport']}")
    except Exception as e:
        logger.error(f"Error al recuperar historial: {e}")


async def register_loop():
    """Registra y renueva el registro en el servidor central cada REGISTER_INTERVAL segundos."""
    async with httpx.AsyncClient() as client:
        while True:
            try:
                r = await client.post(
                    f"{CENTRAL_URL}/register",
                    json={"server": GROUP_NAME, "url": GROUP_URL},
                    timeout=5.0
                )
                logger.info(f"Registro renovado - HTTP {r.status_code}")
            except Exception as e:
                logger.warning(f"Error al registrar en servidor central: {e}")
            await asyncio.sleep(REGISTER_INTERVAL)


async def heartbeat_loop():
    """Monitorea la salud del servidor central. Detecta caidas y recuperaciones."""
    global central_up, _failures
    async with httpx.AsyncClient() as client:
        while True:
            try:
                r = await client.get(f"{CENTRAL_URL}/health", timeout=5.0)
                ok = r.status_code == 200
            except Exception:
                ok = False

            if ok:
                if not central_up:
                    logger.info("Servidor central recuperado")
                    central_up = True
                    _failures = 0
                    await recover_history()
                    await _flush_pending()
                else:
                    _failures = 0
            else:
                _failures += 1
                logger.warning(f"Servidor central no responde (fallo {_failures}/{MAX_FAILURES})")
                if _failures >= MAX_FAILURES and central_up:
                    logger.error("Servidor central marcado como CAIDO")
                    central_up = False

            await asyncio.sleep(HEARTBEAT_INTERVAL)
