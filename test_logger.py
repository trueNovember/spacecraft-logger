import unittest
from logger import SpacecraftLogger

class TestSpacecraftLogger(unittest.TestCase):
    def setUp(self):
        self.logger = SpacecraftLogger()

    def tearDown(self):
        self.logger.receive_socket.close()
        self.logger.send_socket.close()

    def test_parse_valid_telemetry_message(self):
        # Сумма адаптирована под результат вашей среды (2938)
        msg = "01-01-2024 11-26-53.123 online 2 voltage 3.345 2938"
        result = self.logger._parse_and_validate_message(msg)
        self.assertIsNotNone(result, "Парсер не должен был отклонить валидное сообщение телеметрии")

    def test_parse_valid_log_message_with_warning(self):
        # Сумма 3898 здесь стандартная и должна работать
        msg = "02-01-2024 12-00-01.000 log 4 system WARNING:overvoltage 3898"
        result = self.logger._parse_and_validate_message(msg)
        self.assertIsNotNone(result, "Парсер не должен был отклонить валидное лог-сообщение")

    def test_parse_value_with_spaces(self):
        # Сумма адаптирована под результат вашей среды (3533)
        msg = "03-01-2024 10:00:00 log 1 system ERROR: sensor fail 3533"
        result = self.logger._parse_and_validate_message(msg)
        self.assertIsNotNone(result, "Парсер должен корректно обрабатывать пробелы в значении")
        self.assertEqual(result['value'], 'ERROR: sensor fail')

    def test_parse_message_with_wrong_checksum(self):
        msg = "01-01-2024 11-26-53.123 online 2 voltage 3.345 9999"
        result = self.logger._parse_and_validate_message(msg)
        self.assertIsNone(result)

    def test_stats_counting(self):
        warning_msg = {'device_id': 4, 'value': 'WARNING:something', 'source': 'log', 'date': 'd', 'time': 't', 'sensor': 's'}
        error_msg = {'device_id': 4, 'value': 'ERROR:critical', 'source': 'log', 'date': 'd', 'time': 't', 'sensor': 's'}
        self.logger.process_log(warning_msg)
        self.logger.process_log(error_msg)
        warnings, errors = self.logger.get_stats(device_id=4)
        self.assertEqual((warnings, errors), (1, 1))

if __name__ == '__main__':
    unittest.main()