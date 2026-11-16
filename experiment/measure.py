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
import httpx

# --- Parametros del experimento ---
SERVER          = "http://localhost:8000"
CONTAINER_NAME  = "proyecto-final-server-1"   # nombre del contenedor Docker
FROM_USER       = "experimento@g1"             # debe existir antes de correr
TOTAL_MESSAGES  = 30
SEND_INTERVAL   = 0.5    # segundos entre mensajes
DOWN_SECONDS    = 5      # cuanto tiempo permanece caido el servidor
REPETITIONS     = 3
RECOVERY_WAIT   = 15     # segundos para que el servidor se recupere al volver


def ensure_user():
    """Crea el usuario del experimento si no existe."""
    username = FROM_USER.split("@")[0]
    try:
        httpx.post(f"{SERVER}/users", json={"username": username}, timeout=5)
    except Exception:
        pass


def send_message(body: str) -> str | None:
    """Envia un mensaje y retorna el id asignado, o None si fallo."""
    try:
        r = httpx.post(
            f"{SERVER}/messages",
            json={"from_user": FROM_USER, "body": body},
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


def get_history_ids() -> set[str]:
    """Retorna el conjunto de ids de mensajes en el historial del servidor."""
    try:
        r = httpx.get(f"{SERVER}/messages", params={"since": 0}, timeout=10)
        if r.status_code == 200:
            return {m["id"] for m in r.json() if m.get("from_user") == FROM_USER}
    except Exception:
        pass
    return set()


def run_repetition(rep: int) -> dict:
    print(f"\n--- Repeticion {rep} ---")
    sent_ids = []
    kill_sent = False

    for i in range(TOTAL_MESSAGES):
        # A mitad del envio, mata el servidor
        if i == TOTAL_MESSAGES // 2 and not kill_sent:
            kill_server()
            time.sleep(DOWN_SECONDS)
            start_server()
            kill_sent = True

        msg_id = send_message(f"msg-{rep}-{i}")
        if msg_id:
            sent_ids.append(msg_id)
            print(f"  Enviado {i+1}/{TOTAL_MESSAGES}: {msg_id[:8]}...")
        else:
            print(f"  Enviado {i+1}/{TOTAL_MESSAGES}: FALLO (servidor caido)")

        time.sleep(SEND_INTERVAL)

    # Esperar a que el servidor procese todo
    time.sleep(5)

    received_ids = get_history_ids()
    sent_set     = set(sent_ids)
    perdidos     = sent_set - received_ids
    total_sent   = TOTAL_MESSAGES
    total_ok     = len(sent_ids)        # los que el servidor acepto (HTTP 202)
    total_recv   = len(sent_set & received_ids)
    total_lost   = len(perdidos)

    print(f"  Enviados: {total_sent} | Aceptados: {total_ok} | En historial: {total_recv} | Perdidos: {total_lost}")
    return {
        "repeticion": rep,
        "enviados": total_sent,
        "aceptados": total_ok,
        "en_historial": total_recv,
        "perdidos": total_lost,
    }


def main():
    print("=== Experimento: perdida de mensajes ante caida del servidor ===")
    print(f"Mensajes por repeticion: {TOTAL_MESSAGES} | Tasa: 1 cada {SEND_INTERVAL}s | Caida: {DOWN_SECONDS}s\n")

    ensure_user()
    resultados = []

    for rep in range(1, REPETITIONS + 1):
        r = run_repetition(rep)
        resultados.append(r)
        if rep < REPETITIONS:
            print(f"\nEsperando 10s antes de la siguiente repeticion...")
            time.sleep(10)

    print("\n=== RESULTADOS ===")
    print(f"{'Rep':>4} | {'Enviados':>8} | {'Aceptados':>9} | {'En historial':>12} | {'Perdidos':>8}")
    print("-" * 55)
    for r in resultados:
        print(f"{r['repeticion']:>4} | {r['enviados']:>8} | {r['aceptados']:>9} | {r['en_historial']:>12} | {r['perdidos']:>8}")

    total_perdidos = sum(r["perdidos"] for r in resultados)
    promedio = total_perdidos / len(resultados)
    print(f"\nPromedio de mensajes perdidos por repeticion: {promedio:.1f}")
    print(f"Total de mensajes perdidos en {REPETITIONS} repeticiones: {total_perdidos}")


if __name__ == "__main__":
    main()
