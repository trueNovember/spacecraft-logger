import tkinter as tk
from tkinter import scrolledtext, messagebox
import queue
from logger import SpacecraftLogger, DEVICE_MAP  # Импортируем наш логгер


class LoggerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Бортовой самописец")
        self.root.geometry("700x500")

        # Создаём очередь для потокобезопасной передачи сообщений от логгера к GUI
        self.log_queue = queue.Queue()

        # Создаём экземпляр логгера и передаём ему нашу очередь
        # Логгер будет класть сообщения в очередь
        self.logger = SpacecraftLogger(display_callback=self.queue_message)

        self.create_widgets()

        # Запускаем фоновые потоки логгера
        self.logger.start()
        # Запускаем периодическую проверку очереди сообщений
        self.root.after(100, self.check_queue)
        # Назначаем действие при закрытии окна
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def queue_message(self, message):
        """Метод, который логгер вызывает для отправки сообщения в GUI."""
        self.log_queue.put(message)

    def check_queue(self):
        """Проверяет очередь и выводит сообщения в текстовое поле."""
        while not self.log_queue.empty():
            message = self.log_queue.get()
            self.log_display.insert(tk.END, message + "\n")
            self.log_display.see(tk.END)  # Автопрокрутка вниз
        self.root.after(100, self.check_queue)  # Повторяем проверку через 100 мс

    def create_widgets(self):
        """Создаёт все элементы интерфейса."""
        # --- Фрейм для вывода логов ---
        log_frame = tk.LabelFrame(self.root, text="Логи и телеметрия")
        log_frame.pack(padx=10, pady=10, fill="both", expand=True)

        self.log_display = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state='normal')
        self.log_display.pack(padx=5, pady=5, fill="both", expand=True)

        # --- Фрейм для запроса логов ---
        request_frame = tk.LabelFrame(self.root, text="Запрос лога из самописца")
        request_frame.pack(padx=10, pady=5, fill="x", expand=False)

        # Поля ввода
        tk.Label(request_frame, text="ID Устройства:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.device_id_entry = tk.Entry(request_frame)
        self.device_id_entry.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(request_frame, text="Сенсор:").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.sensor_entry = tk.Entry(request_frame)
        self.sensor_entry.grid(row=0, column=3, padx=5, pady=5)

        tk.Label(request_frame, text="Интервал (сек):").grid(row=0, column=4, padx=5, pady=5, sticky="w")
        self.interval_entry = tk.Entry(request_frame)
        self.interval_entry.grid(row=0, column=5, padx=5, pady=5)

        # Кнопка
        self.request_button = tk.Button(request_frame, text="Отправить запрос", command=self.send_request)
        self.request_button.grid(row=0, column=6, padx=10, pady=10)

    def send_request(self):
        """Отправляет команду запроса лога, взяв данные из полей ввода."""
        try:
            device_id = int(self.device_id_entry.get())
            sensor = self.sensor_entry.get()
            interval = int(self.interval_entry.get())

            if not sensor:
                messagebox.showerror("Ошибка", "Имя сенсора не может быть пустым.")
                return

            # Отправляем запрос через наш логгер
            self.logger.send_log_request(interval, device_id, sensor)
            self.log_display.insert(tk.END, f"[GUI] Команда запроса лога добавлена в очередь.\n")
            self.log_display.see(tk.END)

        except ValueError:
            messagebox.showerror("Ошибка", "ID устройства и интервал должны быть числами.")

    def on_closing(self):
        """Выполняется при закрытии окна."""
        if messagebox.askokcancel("Выход", "Вы уверены, что хотите выйти?"):
            self.logger.stop()
            self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = LoggerGUI(root)
    root.mainloop()