import socket
import json
import threading
import time
from collections import deque

MODEM_IP = "127.0.0.1"
RECEIVE_PORT = 5001
SEND_PORT = 5002
LOG_FILE = "spacecraft_log.txt"
DEVICE_MAP = {0: "BlackBox", 1: "EmergencySystem", 2: "OxygenSystem", 3: "Climatic", 4: "RadiationShield",
              5: "PressureSystem", 6: "Lighting"}


class SpacecraftLogger:
    def __init__(self, host=MODEM_IP, receive_port=RECEIVE_PORT, send_port=SEND_PORT,display_callback=None):
        self.host = host
        self.receive_port = receive_port
        self.send_port = send_port
        self.receive_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.receive_socket.settimeout(1.0)
        self.is_running = False
        self.log_download_in_progress = False
        self.command_queue = deque()
        self._lock = threading.Lock()
        self.session_stats = {}
        self.listening_thread = None
        self.command_thread = None
        self.display_callback = display_callback

    def _parse_and_validate_message(self, message_str: str) -> dict | None:
        """
        Финальная, логически корректная версия парсера,
        которая работает в стандартной среде Python согласно заданию.
        """
        message_str = message_str.strip()
        last_space_index = message_str.rfind(' ')
        if last_space_index == -1: return None

        data_part_str = message_str[:last_space_index]
        checksum_str = message_str[last_space_index + 1:]

        parts = data_part_str.split()
        if len(parts) < 6: return None

        try:
            received_checksum = int(checksum_str)
            source = parts[2]
        except (ValueError, IndexError):
            return None

        calculated_checksum = 0
        if source == 'online':
            # Стандартный алгоритм для телеметрии (с пробелами)
            calculated_checksum = sum(b for b in data_part_str.encode('ascii'))
        elif source == 'log':
            # Стандартный алгоритм для логов (склейка полей + значение с пробелами)
            fixed_fields_part = "".join(parts[0:5])
            value_part = " ".join(parts[5:])
            string_for_checksum = fixed_fields_part + value_part
            calculated_checksum = sum(b for b in string_for_checksum.encode('ascii'))
        else:
            return None

        if calculated_checksum != received_checksum:
            return None

        try:
            value = " ".join(parts[5:])
            return {
                "date": parts[0], "time": parts[1], "source": source,
                "device_id": int(parts[3]), "sensor": parts[4], "value": value,
                "checksum": received_checksum
            }
        except (ValueError, IndexError):
            return None

    def process_telemetry(self, data: dict):
        device_name = DEVICE_MAP.get(data['device_id'], "UnknownDevice")
        output_display = {"device": device_name, "sensor": data['sensor'], "value": data['value']}
        if self.display_callback:
            self.display_callback(f"[TELEMETRY] {json.dumps(output_display)}")
        output_log = {"date": data['date'], "time": data['time'], "source": data['source'], "device": device_name,
                      "sensor": data['sensor'], "value": data['value']}
        self.log_to_file(output_log)

    def process_log(self, data: dict):
        device_id = data['device_id']
        device_name = DEVICE_MAP.get(device_id, "UnknownDevice")
        value_str = str(data['value'])
        log_entry = None
        if device_id == 0 and data['sensor'] == 'system':
            if value_str == 'log_start':
                self.log_download_in_progress = True
                if self.display_callback: self.display_callback("[SYSTEM] Начало выгрузки логов.")
                log_entry = {"system_message": "log_start", "time": data['time']}
            elif value_str == 'log_end':
                self.log_download_in_progress = False
                if self.display_callback: self.display_callback("[SYSTEM] Выгрузка логов завершена.")
                log_entry = {"system_message": "log_end", "time": data['time']}
        elif "WARNING" in value_str.upper() or "ERROR" in value_str.upper():
            with self._lock:
                self.session_stats.setdefault(device_id, {"warnings": 0, "errors": 0})
                if "WARNING" in value_str.upper(): self.session_stats[device_id]["warnings"] += 1
                if "ERROR" in value_str.upper(): self.session_stats[device_id]["errors"] += 1
            output_display = {"device": device_name, "sensor": data['sensor'], "failure": value_str}
            if self.display_callback: self.display_callback(f"[FAILURE] {json.dumps(output_display)}")
            log_entry = {"date": data['date'], "time": data['time'], "source": data['source'], "device": device_name,
                         "sensor": data['sensor'], "failure": value_str}
        else:
            log_entry = {"date": data['date'], "time": data['time'], "source": data['source'], "device": device_name,
                         "sensor": data['sensor'], "value": value_str}
        if log_entry: self.log_to_file(log_entry)

    def log_to_file(self, data_to_log: dict):
        with self._lock:
            try:
                with open(LOG_FILE, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(data_to_log, ensure_ascii=False) + '\n')
            except IOError as e:
                print(f"[ERROR] Не удалось записать в лог-файл: {e}")

    def receive_data(self):
        print(f"Начинаем прослушивание порта {self.receive_port}...")
        try:
            self.receive_socket.bind(('', self.receive_port))
        except Exception as e:
            print(f"[ERROR] Не удалось привязать сокет к порту {self.receive_port}: {e}")
            self.is_running = False;
            return
        while self.is_running:
            try:
                raw_data, addr = self.receive_socket.recvfrom(1024)
                data_packet = json.loads(raw_data.decode('utf-8'))
                message_text = data_packet.get("message")
                if not message_text: continue
                parsed_data = self._parse_and_validate_message(message_text)
                if parsed_data:
                    if parsed_data['source'] == 'online':
                        self.process_telemetry(parsed_data)
                    elif parsed_data['source'] == 'log':
                        self.process_log(parsed_data)
            except socket.timeout:
                continue
            except json.JSONDecodeError:
                print(f"[ERROR] Не удалось декодировать JSON.")
            except Exception as e:
                print(f"Неизвестная ошибка при приеме данных: {e}"); break
        print("Прослушивание остановлено.")

    def _process_command_queue(self):
        while self.is_running:
            if not self.log_download_in_progress and self.command_queue:
                command_data = self.command_queue.popleft()
                command_packet = {"command": "getlog", "interval": command_data["interval"],
                                  "device": command_data["device_id"], "sensor": command_data["sensor"]}
                try:
                    json_packet = json.dumps(command_packet).encode('utf-8')
                    self.send_socket.sendto(json_packet, (self.host, self.send_port))
                    print(f"[COMMAND SENT] Отправлена команда: {command_packet}")
                    self.log_to_file({"sent_command": command_packet})
                except Exception as e:
                    print(f"[ERROR] Не удалось отправить команду: {e}")
            time.sleep(0.5)

    def start(self):
        if not self.is_running:
            self.is_running = True
            self.listening_thread = threading.Thread(target=self.receive_data, daemon=True)
            self.listening_thread.start()
            self.command_thread = threading.Thread(target=self._process_command_queue, daemon=True)
            self.command_thread.start()
            print("Утилита запущена.")

    def stop(self):
        if self.is_running:
            print("Остановка утилиты...")
            self.is_running = False
            if self.listening_thread: self.listening_thread.join()
            if self.command_thread: self.command_thread.join()
            self.receive_socket.close();
            self.send_socket.close()
            print("Утилита остановлена.")

    def send_log_request(self, interval: int, device_id: int, sensor: str):
        command = {"interval": interval, "device_id": device_id, "sensor": sensor}
        self.command_queue.append(command)
        print(f"[COMMAND QUEUED] Команда добавлена в очередь: {command}")

    def get_stats(self, device_id: int) -> tuple[int, int]:
        with self._lock:
            stats = self.session_stats.get(device_id, {"warnings": 0, "errors": 0})
            return (stats["warnings"], stats["errors"])