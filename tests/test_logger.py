import unittest
from pyloggernmea.logger import NMEAParser

class TestNMEAParser(unittest.TestCase):
    def setUp(self):
        """Инициализация перед каждым тестом."""
        self.parser = NMEAParser(
            port="COM1",
            baudrate=9600,
            output="test_output.log",
            input=None,
            timeout=0
        )

    def test_gngga_processing(self):
        """Тест обработки GNGGA сообщений."""
        # Тест с корректными данными
        test_data = "$GNGGA,061058.00,5544.82465,N,03739.73260,E,1,03,3.42,192.3,M,13.3,M,,*45"
        result = self.parser.decode_line(test_data)
        self.assertEqual(result, "")  # Пустая строка, так как цикл не завершен
        
        gga_data = self.parser.current_cycle["$GNGGA"]
        self.assertEqual(gga_data["time"], "06:10:58")
        self.assertEqual(gga_data["latitude"], "5544.82465N")
        self.assertEqual(gga_data["longitude"], "03739.73260E")
        self.assertEqual(gga_data["error"], "3.42")

        # Тест с пустыми данными
        test_data = "$GNGGA,,,,,,,,,,,,,*45"
        self.parser._reset_cycle()
        self.parser.decode_line(test_data)
        gga_data = self.parser.current_cycle["$GNGGA"]
        self.assertEqual(gga_data["time"], "n")
        self.assertEqual(gga_data["latitude"], "n")
        self.assertEqual(gga_data["longitude"], "n")
        self.assertEqual(gga_data["error"], "n")

    def test_gngsa_processing(self):
        """Тест обработки GNGSA сообщений."""
        # Тест GPS+GLONASS
        test_data = "$GNGSA,A,2,01,02,03,04,65,66,67,68,,,,,3.57,3.42,1.00*1A"
        result = self.parser.decode_line(test_data)
        self.assertEqual(result, "")  # Пустая строка, так как цикл не завершен
        gsa_data = self.parser.current_cycle["$GNGSA"]
        self.assertEqual(gsa_data["system"], "GPS+GLONASS")

        # Тест только GLONASS
        test_data = "$GNGSA,A,2,65,66,67,68,,,,,,,,,3.57,3.42,1.00*1A"
        self.parser._reset_cycle()
        result = self.parser.decode_line(test_data)
        gsa_data = self.parser.current_cycle["$GNGSA"]
        self.assertEqual(gsa_data["system"], "GLONASS")

        # Тест с пустыми данными
        test_data = "$GNGSA,A,2,,,,,,,,,,,,,3.57,3.42,1.00*1A"
        self.parser._reset_cycle()
        result = self.parser.decode_line(test_data)
        gsa_data = self.parser.current_cycle["$GNGSA"]
        self.assertEqual(gsa_data["system"], "n")

    def test_gnrmc_processing(self):
        """Тест обработки GNRMC сообщений."""
        # Тест с корректными данными
        test_data = "$GNRMC,061059.00,A,5544.82467,N,03739.73251,E,0.024,,270225,,,A*60"
        result = self.parser.decode_line(test_data)
        self.assertEqual(result, "")  # Пустая строка, так как цикл не завершен
        rmc_data = self.parser.current_cycle["$GNRMC"]
        self.assertEqual(rmc_data["speed"], "0.024")

        # Тест с пустыми данными
        test_data = "$GNRMC,061059.00,A,5544.82467,N,03739.73251,E,,,270225,,,A*60"
        self.parser._reset_cycle()
        result = self.parser.decode_line(test_data)
        rmc_data = self.parser.current_cycle["$GNRMC"]
        self.assertEqual(rmc_data["speed"], "n")

    def test_complete_cycle(self):
        """Тест полного цикла обработки всех сообщений."""
        # Сначала сбрасываем цикл
        self.parser._reset_cycle()
        
        # Отправляем сообщения по одному
        gga = "$GNGGA,061058.00,5544.82465,N,03739.73260,E,1,03,3.42,192.3,M,13.3,M,,*45"
        gsa = "$GNGSA,A,2,01,02,03,04,65,66,67,68,,,,,3.57,3.42,1.00*1A"
        rmc = "$GNRMC,061059.00,A,5544.82467,N,03739.73251,E,0.024,,270225,,,A*60"

        result1 = self.parser.decode_line(gga)
        self.assertEqual(result1, "")  # Первое сообщение, цикл не завершен
        
        result2 = self.parser.decode_line(gsa)
        self.assertEqual(result2, "")  # Второе сообщение, цикл не завершен
        
        result3 = self.parser.decode_line(rmc)  # Третье сообщение, цикл должен завершиться
        expected = "06:10:58 5544.82465N 03739.73260E 3.42 GPS+GLONASS 0.024\n"
        self.assertEqual(result3, expected)

    def test_checksum_validation(self):
        """Тест проверки контрольной суммы."""
        # Корректная контрольная сумма
        valid_msg = "$GNGGA,061058.00,5544.82465,N,03739.73260,E,1,03,3.42,192.3,M,13.3,M,,*45"
        result = self.parser.decode_line(valid_msg)
        self.assertNotEqual(result, "Invalid checksum\n")

        # Некорректная контрольная сумма
        invalid_msg = "$GNGGA,061058.00,5544.82465,N,03739.73260,E,1,03,3.42,192.3,M,13.3,M,,*00"
        result = self.parser.decode_line(invalid_msg)
        self.assertEqual(result, "")

if __name__ == '__main__':
    unittest.main()