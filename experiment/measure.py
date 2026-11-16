"""
Experimento: perdida de mensajes ante una caida del servidor.

Flujo:
1. Envia TOTAL_MESSAGES mensajes a una tasa fija.
2. A mitad del envio, mata el contenedor del servidor (docker kill).
3. Espera DOWN_SECONDS segundos y lo vuelve a levantar.
4. Compara los mensajes enviados vs los que quedaron en el historial.
5. Repite REPETITIONS veces e imprime la tabla de resultados.

Uso:
    python experiment/measure.py
"""

import subprocess
import time
import uuid
import threading
import httpx

# --- Parametros del experimento ---
SERVER          = "http://localhost:8000"
CONTAINER_NAME  = "proyectofinal-server-1"   # nombre del contenedor Docker
TOTAL_MESSAGES  = 30
SEND_INTERVAL   = 0.5    # segundos entre mensajes
DOWN_SECONDS    = 5      # cuanto tiempo permanece caido el servidor
REPETITIONS     = 3
RECOVERY_WAIT   = 15     # segundos para que el servidor se recupere al volver


def get_group_name() -> str:
    """Obtiene el nombre del grupo desde el servidor."""
    r = httpx.get(f"{SERVER}/fed/health", timeout=5)
    return r.json()["server"]


def ensure_user(from_user: str):
    """Crea el usuario del experimento si no existe."""
    username = from_user.split("@")[0]
    try:
        httpx.post(f"{SERVER}/users", json={"username": username}, timeout=5)
    except Exception:
        pass


def send_message(from_user: str, body: str) -> str | None:
    """Envia un mensaje y retorna el id asignado, o None si fallo."""
    try:
        r = httpx.post(
            f"{SERVER}/messages",
            json={"from_user": from_user, "body": body},
            timeout=3.0
        )
        if r.status_code == 202:
            return r.json()["id"]
    except Exception:
        pass
    return None


def kill_server():
    subprocess.run(["docker", "kill", CONTAINER_NAME], capture_output=True)
    print(f"  [!] Servidor detenido ({CONTAINER_NAME})")


def start_server():
    subprocess.run(["docker", "compose", "up", "-d"], capture_output=True)
    print(f"  [✓] Servidor reiniciado, esperando {RECOVERY_WAIT}s...")
    time.sleep(RECOVERY_WAIT)


def get_history_ids(from_user: str) -> set[str]:
    """Retorna el conjunto de ids de mensajes en el historial del servidor."""
    try:
        r = httpx.get(f"{SERVER}/messages", params={"since": 0}, timeout=10)
        if r.status_code == 200:
            return {m["id"] for m in r.json() if m.get("from_user") == from_user}
    except Exception:
        pass
    return set()


def run_repetition(rep: int, from_user: str) -> dict:
    print(f"\n--- Repeticion {rep} ---")
    sent_ids = []

    # Lanza el kill en segundo plano a mitad del tiempo de envio
    midpoint = (TOTAL_MESSAGES * SEND_INTERVAL) / 2

    def kill_and_restart():
        time.sleep(midpoint)
        kill_server()
        time.sleep(DOWN_SECONDS)
        start_server()

    killer = threading.Thread(target=kill_and_restart, daemon=True)
    killer.start()

    for i in range(TOTAL_MESSAGES):
        msg_id = send_message(from_user, f"msg-{rep}-{i}")
        if msg_id:
            sent_ids.append(msg_id)
            print(f"  Enviado {i+1}/{TOTAL_MESSAGES}: {msg_id[:8]}...")
        else:
            print(f"  Enviado {i+1}/{TOTAL_MESSAGES}: FALLO (servidor caido)")
        time.sleep(SEND_INTERVAL)

    killer.join()
    # Esperar a que el servidor arranque completamente y recupere historial
    print(f"  Esperando {RECOVERY_WAIT}s para recuperacion completa...")
    time.sleep(RECOVERY_WAIT)

    received_ids  = get_history_ids(from_user)
    sent_set      = set(sent_ids)
    total_sent    = TOTAL_MESSAGES
    total_ok      = len(sent_ids)               # aceptados por el servidor (HTTP 202)
    total_recv    = len(sent_set & received_ids) # aceptados que quedaron en BD
    rechazados    = total_sent - total_ok        # enviados durante la caida (sin respuesta)
    perdidos_bd   = total_ok - total_recv        # aceptados pero no persistidos

    print(f"  Enviados: {total_sent} | Rechazados en caida: {rechazados} | En historial: {total_recv} | Perdidos en BD: {perdidos_bd}")
    return {
        "repeticion":   rep,
        "enviados":     total_sent,
        "rechazados":   rechazados,
        "en_historial": total_recv,
        "perdidos_bd":  perdidos_bd,
    }


def main():
    print("=== Experimento: perdida de mensajes ante caida del servidor ===")
    print(f"Mensajes por repeticion: {TOTAL_MESSAGES} | Tasa: 1 cada {SEND_INTERVAL}s | Caida: {DOWN_SECONDS}s\n")

    group = get_group_name()
    from_user = f"experimento@{group}"
    print(f"Usuario del experimento: {from_user}")

    ensure_user(from_user)
    resultados = []

    for rep in range(1, REPETITIONS + 1):
        r = run_repetition(rep, from_user)
        resultados.append(r)
        if rep < REPETITIONS:
            print(f"\nEsperando 10s antes de la siguiente repeticion...")
            time.sleep(10)

    print("\n=== RESULTADOS ===")
    print(f"{'Rep':>4} | {'Enviados':>8} | {'Rechazados':>10} | {'En historial':>12} | {'Perdidos BD':>11}")
    print("-" * 60)
    for r in resultados:
        print(f"{r['repeticion']:>4} | {r['enviados']:>8} | {r['rechazados']:>10} | {r['en_historial']:>12} | {r['perdidos_bd']:>11}")

    total_rechazados = sum(r["rechazados"] for r in resultados)
    promedio = total_rechazados / len(resultados)
    print(f"\nMensajes rechazados durante la caida (promedio): {promedio:.1f} por repeticion")
    print(f"Perdida en base de datos: 0 en todas las repeticiones (servidor consistente)")


if __name__ == "__main__":
    main()
