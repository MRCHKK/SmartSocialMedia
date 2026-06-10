import queue

class PrintRedirector:
    """Thread-safe redirector: print() → GUI textbox przez kolejkę."""
    def __init__(self, textbox, root):
        self.textbox = textbox
        self.root = root
        self._queue = queue.Queue()
        self._poll()

    def write(self, text):
        self._queue.put(text)

    def flush(self):
        pass

    def _poll(self):
        """Odczytuje kolejkę i wstawia tekst z głównego wątku Tkinter."""
        while not self._queue.empty():
            try:
                text = self._queue.get_nowait()
                self.textbox.insert("end", text)
                self.textbox.see("end")
            except queue.Empty:
                break
        try:
            self.root.after(100, self._poll)
        except Exception:
            pass  # Jeśli okno główne zostało zniszczone
