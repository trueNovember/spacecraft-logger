# Файл: modem_simulator.py

import socket
import json
import time
import datetime

# Адреса нашего логгера
LOGGER_IP = "127.0.0.1"
LOGGER_RECEIVE_PORT = 5001
LOGGER_SEND_PORT = 5002


def get_timestamp():
    return datetime.datetime.now().strftime("%d-%m-%Y %H-%M-%S.%f")[:-3]


def create_message_and_checksum(data_str: str):
    """Создает сообщение и правильную контрольную сумму для него."""
    parts = data_str.split()
    source = parts[2]

    checksum = 0
    if source == 'online':
        # Для телеметрии - сумма строки с пробелами
        checksum = sum(b for b in data_str.encode('ascii'))
    elif source == 'log':
        # Для логов - сумма склеенных полей + значение
        fixed_fields_part = "".join(parts[0:5])
        value_part = " ".join(parts[5:])
        string_for_checksum = fixed_fields_part + value_part
        checksum = sum(b for b in string_for_checksum.encode('ascii'))

    full_message = f"{data_str} {checksum}"
    return {"message": full_message, "recv_time": int(time.time() * 1000)}


def main():
    print("Симулятор модема запущен...")
    send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receive_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receive_socket.bind((LOGGER_IP, LOGGER_SEND_PORT))
    receive_socket.settimeout(1.0)  # Не блокировать надолго

    log_request_received = False

    try:
        while True:
            # 1. Отправляем телеметрию, если не было запроса логов
            if not log_request_received:
                print("Отправка пакета телеметрии...")
                telemetry_str = f"{get_timestamp()} online 2 voltage 3.345"
                packet = create_message_and_checksum(telemetry_str)
                send_socket.sendto(json.dumps(packet).encode('utf-8'), (LOGGER_IP, LOGGER_RECEIVE_PORT))
                time.sleep(2)  # Пауза 2 секунды

            # 2. Слушаем, не пришла ли команда от GUI
            try:
                data, addr = receive_socket.recvfrom(1024)
                print(f"\n!!! Получена команда от GUI: {data.decode('utf-8')}")
                log_request_received = True
            except socket.timeout:
                continue  # Команды не было, продолжаем цикл

            # 3. Если команда пришла, отправляем порцию логов
            if log_request_received:
                print("\n--- Начало отправки логов по запросу ---")
                log_packets = [
                    create_message_and_checksum(f"{get_timestamp()} log 0 system log_start"),
                    create_message_and_checksum(f"{get_timestamp()} log 3 temperature 21.5"),
                    create_message_and_checksum(f"{get_timestamp()} log 4 system WARNING:overvoltage"),
                    create_message_and_checksum(f"{get_timestamp()} log 2 pressure 0.98"),
                    create_message_and_checksum(f"{get_timestamp()} log 1 system ERROR:sensor_fail"),
                    create_message_and_checksum(f"{get_timestamp()} log 0 system log_end"),
                ]
                for packet in log_packets:
                    print(f"Отправка лог-пакета: {packet['message']}")
                    send_socket.sendto(json.dumps(packet).encode('utf-8'), (LOGGER_IP, LOGGER_RECEIVE_PORT))
                    time.sleep(2)  # Небольшая задержка между пакетами

                print("--- Конец отправки логов ---\n")
                log_request_received = False  # Возвращаемся в режим телеметрии

    except KeyboardInterrupt:
        print("\nСимулятор остановлен.")
    finally:
        send_socket.close()
        receive_socket.close()


if __name__ == "__main__":
    main()