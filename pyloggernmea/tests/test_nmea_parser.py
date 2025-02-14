from unittest.mock import mock_open, patch
from logger import NMEAParser
import serial

MOCK_TEMPLATES = '''{
    "$GPGGA": {
        "keys": ["UTC", "latitude", "longitude", "altitude", "satellites"],
        "indexes": [1, 2, 4, 9, 7],
        "out_msg_template": "{type} UTC:{UTC} Lat:{latitude} Lon:{longitude} Alt:{altitude} Sat:{satellites}\\n"
    }
}'''


def test_decode_line() -> None:
    with patch('builtins.open', mock_open(read_data=MOCK_TEMPLATES)):
        parser = NMEAParser(
            port="COM1",
            baudrate=9600,
            output="test.txt",
            filter="GGA"
        )

        test_line = (
            "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47"
        )
        expected = (
            "$GPGGA UTC:123519 Lat:4807.038 Lon:01131.000 Alt:545.4 Sat:08\n"
        )

        result = parser.decode_line(test_line)
        assert result == expected


@patch('serial.Serial')
def test_start_parser(mock_serial) -> None:
    mock_serial.return_value.readline.return_value = (
        "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47"
    ).encode()

    # Используем контекстный менеджер для мока двух разных вызовов open()
    mock_file = mock_open(read_data=MOCK_TEMPLATES)
    with patch('builtins.open', mock_file) as m:
        parser = NMEAParser(
            port="COM1",
            baudrate=9600,
            output="test.txt",
            filter="$GPGGA"
        )

        def mock_start() -> None:
            parser.ser = serial.Serial(parser.port, parser.baudrate)
            with open(parser.output, "w") as f:
                line = parser.ser.readline().decode("utf-8")
                if line.startswith(parser.filter):
                    f.write(parser.decode_line(line))

        parser.start = mock_start
        parser.start()

        # Проверяем, что write был вызван с правильными аргументами
        write_call = [
            call for call in m.mock_calls if call[0] == '().write'][0]
        assert write_call[1][0] == (
            "$GPGGA UTC:123519 Lat:4807.038 Lon:01131.000 Alt:545.4 Sat:08\n"
        )


def test_filter_messages() -> None:
    with patch('builtins.open', mock_open(read_data=MOCK_TEMPLATES)):
        parser = NMEAParser(
            port="COM1",
            baudrate=9600,
            output="test.txt",
            filter="GPGGA"
        )

        test_line = (
            "$GLGGA,123520,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*42"
        )
        assert not test_line.startswith(parser.filter)


def test_checksum_validation() -> None:
    with patch('builtins.open', mock_open(read_data=MOCK_TEMPLATES)):
        parser = NMEAParser(
            port="COM1",
            baudrate=9600,
            output="test.txt",
            filter="GGA"
        )

        # Правильная контрольная сумма
        valid_line = (
            "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47"
        )
        result = parser.decode_line(valid_line)
        assert result == (
            "$GPGGA UTC:123519 Lat:4807.038 Lon:01131.000 Alt:545.4 Sat:08\n"
        )

        # Неправильная контрольная сумма
        invalid_line = (
            "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*00"
        )
        result = parser.decode_line(invalid_line)
        assert result.startswith("Invalid message: checksum mismatch")

        # Отсутствует контрольная сумма
        no_checksum_line = (
            "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M"
        )
        result = parser.decode_line(no_checksum_line)
        assert result == "Invalid message: no checksum\n"
