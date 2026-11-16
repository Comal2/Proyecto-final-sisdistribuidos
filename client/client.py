import sys
import time
import httpx

SERVER = "http://localhost:8000"
POLL_INTERVAL = 2  # segundos entre actualizaciones


def register_user(username: str) -> str:
    r = httpx.post(f"{SERVER}/users", json={"username": username})
    if r.status_code == 201:
        full = r.json()["username"]
        print(f"[✓] Usuario creado: {full}")
        return full
    elif r.status_code == 409:
        print(f"[i] Usuario ya existe, continuando como {username}@...")
        return None
    else:
        print(f"[!] Error al crear usuario: {r.status_code} {r.text}")
        sys.exit(1)


def send(from_user: str, body: str):
    r = httpx.post(f"{SERVER}/messages", json={"from_user": from_user, "body": body})
    if r.status_code != 202:
        print(f"[!] Error al enviar: {r.status_code} {r.text}")


def fetch_history(since: int) -> list[dict]:
    r = httpx.get(f"{SERVER}/messages", params={"since": since})
    if r.status_code == 200:
        return r.json()
    return []


def print_message(msg: dict):
    origen = msg["origin"]
    if "@" in msg["from_user"]:
        grupo = msg["from_user"].split("@")[1]
    else:
        grupo = origen
    color = "\033[96m" if grupo != origen else "\033[92m"
    reset = "\033[0m"
    print(f"{color}[{msg['lamport']}] {msg['from_user']}: {msg['body']}{reset}")


def main():
    if len(sys.argv) < 2:
        print("Uso: python client.py <nombre_usuario>")
        sys.exit(1)

    username = sys.argv[1]
    result = register_user(username)

    # Determinar el nombre completo del usuario
    r = httpx.get(f"{SERVER}/messages", params={"since": 0})
    # El nombre completo lo devuelve register; si ya existia, construirlo
    # consultando el servidor para obtener el GROUP_NAME
    health = httpx.get(f"{SERVER}/fed/health").json()
    group = health["server"]
    from_user = f"{username}@{group}"

    print(f"\n=== Chat #general | conectado como {from_user} ===")
    print("Escribe un mensaje y presiona Enter. Ctrl+C para salir.\n")

    last_lamport = 0
    # Cargar historial inicial
    for msg in fetch_history(0):
        print_message(msg)
        last_lamport = max(last_lamport, msg["lamport"])

    import threading

    def poll():
        nonlocal last_lamport
        while True:
            time.sleep(POLL_INTERVAL)
            nuevos = fetch_history(last_lamport)
            for msg in nuevos:
                print_message(msg)
                last_lamport = max(last_lamport, msg["lamport"])

    t = threading.Thread(target=poll, daemon=True)
    t.start()

    try:
        while True:
            body = input()
            if body.strip():
                send(from_user, body.strip())
    except KeyboardInterrupt:
        print("\n[i] Saliendo.")


if __name__ == "__main__":
    main()
