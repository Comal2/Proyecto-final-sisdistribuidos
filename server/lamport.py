import threading

class LamportClock:
    def __init__(self):
        self._time = 0
        self._lock = threading.Lock()

    def tick(self) -> int:
        """Incrementa antes de enviar un evento. Retorna el nuevo valor."""
        with self._lock:
            self._time += 1
            return self._time

    def update(self, received: int) -> int:
        """Actualiza al recibir un mensaje: max(local, recibido) + 1."""
        with self._lock:
            self._time = max(self._time, received) + 1
            return self._time

    @property
    def value(self) -> int:
        with self._lock:
            return self._time

clock = LamportClock()
