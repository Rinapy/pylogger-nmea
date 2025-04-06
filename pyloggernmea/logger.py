import json
from typing import Union
from argparse import ArgumentParser, Namespace
import time
import os
if os.name != 'nt':
    import daemon
else:
    daemon = None

import serial


# Получить абсолютный путь к текущему скрипту
script_path = os.path.abspath(__file__)


def parse_args() -> Namespace:
    parser = ArgumentParser()

    parser.add_argument(
        "-i",
        "--input",
        type=str,
        default="",
        help="input file",
    )

    parser.add_argument(
        "-p",
        "--port",
        type=str,
        default="COM1",
        help="COM port",
    )
    parser.add_argument(
        "-b",
        "--baudrate",
        type=int,
        default=9600,
        help="Baud rate",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="logfile.log",
        help="Output file",
    )

    parser.add_argument(
        "-t",
        "--timeout",
        type=int,
        default=0,
        help="Timeout in seconds for attempt to reconnect to the port",
    )

    if daemon:
        parser.add_argument(
            "-d",
            "--daemon",
            action="store_true",
            help="Run as daemon",
        )

    return parser.parse_args()


ID_MAP = {
    "GP": "GPS",
    "GL": "GLONASS",
    "GA": "GALILEO",
    "BD": "BEIDOU",
    "GN": "NAVIC",
}

MODE_MAP = {
    "1": "No positioning",
    "2": "2D",
    "3": "3D",
}


class NMEAParser:

    def __init__(
        self,
        port: str,
        baudrate: int,
        output: str,
        input: Union[str, None] = None,
        timeout: int = 0,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.input = input
        self.output = output
        self.timeout = timeout
        # Буфер для хранения данных текущего цикла
        self.current_cycle = {
            "$GNGGA": None,  # время, широта, долгота
            "$GNGSA": None,  # спутники
            "$GPGSV": None,  # GPS спутники (запасной вариант)
            "$GLGSV": None,  # GLONASS спутники (запасной вариант)
            "$GNRMC": None,
            "$GNVTG": None,  # скорость

        }
        self.print_output = True

    def _convert_to_decimal(self, coord: str, direction: str) -> str:
        """Конвертирует координаты из формата NMEA в десятичные градусы."""
        try:
            if not coord or not direction:
                return 'n'

            # Для широты первые 2 цифры градусы, для долготы первые 3
            if len(coord.split('.')[0]) >= 5:  # долгота
                degrees = float(coord[:3])
                minutes = float(coord[3:])
            else:  # широта
                degrees = float(coord[:2])
                minutes = float(coord[2:])

            # 5544.82475, 03739.73181
            decimal = degrees + (minutes/60)
            # Отрицательные значения для W и S
            if direction in ['W', 'S']:
                decimal = -decimal
            return f"{decimal:.6f}"
        except:
            return 'n'

    def _process_gnrmc(self, data_list: list) -> dict:
        try:
            date = data_list[9] if len(data_list) > 1 else ''
            if date:
                date = [date[i:i+2] for i in range(0, len(date), 2)]
                date = '.'.join(time)
        except Exception:
            return {'date': "n"}
        return {"date": date}

    def _process_gngga(self, data_list: list) -> dict:
        """Обработка GNGGA сообщений."""
        try:
            time = data_list[1] if len(data_list) > 1 else ''
            latitude = data_list[2] if len(data_list) > 2 else ''
            lat_dir = data_list[3] if len(data_list) > 3 else ''
            longitude = data_list[4] if len(data_list) > 4 else ''
            lon_dir = data_list[5] if len(data_list) > 5 else ''
            hdop = data_list[8] if len(data_list) > 8 else ''

            # Форматируем время в формат ЧЧ:ММ:СС
            if time:
                time = time.split('.')[0]
                time = [time[i:i+2] for i in range(0, len(time), 2)]
                time = ':'.join(time)

            return {
                "time": time if time else 'n',
                "latitude": self._convert_to_decimal(latitude, lat_dir),
                "longitude": self._convert_to_decimal(longitude, lon_dir),
                "hdop": hdop if hdop else 'n'
            }
        except Exception:
            return {"time": "n", "latitude": "n", "longitude": "n", "hdop": "n"}

    def _process_gngsa(self, data_list: list) -> dict:
        """Обработка GNGSA сообщений."""
        try:
            satellites = data_list[3:15]
            has_gps = any(1 <= int(sat) <= 32 for sat in satellites if sat)
            has_glonass = any(65 <= int(sat) <=
                              96 for sat in satellites if sat)

            if has_gps and has_glonass:
                return {"system": "GPS+GLONASS"}
            elif has_gps:
                return {"system": "GPS"}
            elif has_glonass:
                return {"system": "GLONASS"}
            return {"system": "n"}
        except Exception as e:
            return {"system": "n"}

    def _process_gsv(self, message_type: str) -> dict:
        """Обработка GSV сообщений."""
        if message_type == "$GPGSV":
            return {"system": "GPS"}
        elif message_type == "$GLGSV":
            return {"system": "GLONASS"}
        return {"system": "n"}

    def _process_gnvtg(self, data_list: list) -> dict:
        """Обработка GNVTG сообщений."""
        try:
            speed_kmh = data_list[7] if len(data_list) > 7 else ''
            return {"speed": speed_kmh if speed_kmh else 'n'}
        except Exception as e:
            return {"speed": "n"}

    def _format_output_line(self) -> str:
        """Форматирует строку вывода из собранных данных."""
        gga_data = self.current_cycle["$GNGGA"] or {
            "time": "n", "latitude": "n", "longitude": "n", "hdop": "n"}

        # Приоритет систем: GNGSA > GPGSV/GLGSV
        system = "n"
        if self.current_cycle["$GNGSA"] and self.current_cycle["$GNGSA"]["system"] != "n":
            system = self.current_cycle["$GNGSA"]["system"]
        elif self.current_cycle["$GPGSV"] and self.current_cycle["$GLGSV"]:
            system = "GPS+GLONASS"
        elif self.current_cycle["$GPGSV"]:
            system = "GPS"
        elif self.current_cycle["$GLGSV"]:
            system = "GLONASS"

        date = self.current_cycle["$GNRMC"] or {"date": "n"}
        speed_data = self.current_cycle["$GNVTG"] or {"speed": "n"}

        return f"{date['date']}\t{gga_data['time']}\t{gga_data['latitude']}\t{gga_data['longitude']}\t{gga_data['hdop']}\t{system}\t{speed_data['speed']}\n"

    def _check_cycle_complete(self) -> bool:
        """Проверяет, завершен ли текущий цикл сбора данных."""
        required_messages = ["$GNGGA", "$GNVTG"]
        # Проверяем наличие обязательных сообщений
        if not all(self.current_cycle[msg] for msg in required_messages):
            return False
        # Проверяем наличие информации о спутниках
        has_satellites = (
            (self.current_cycle["$GNGSA"] and self.current_cycle["$GNGSA"]["system"] != "n") or
            self.current_cycle["$GPGSV"] or
            self.current_cycle["$GLGSV"]
        )
        return has_satellites

    def _process_message(self, message_type: str, data_list: list) -> None:
        """Обрабатывает сообщение и добавляет его в текущий цикл."""
        processors = {
            "$GNGGA": self._process_gngga,
            "$GNGSA": self._process_gngsa,
            "$GNVTG": self._process_gnvtg,
            "$GNRMC": self._process_gnrmc,
        }

        if message_type in processors:
            self.current_cycle[message_type] = processors[message_type](
                data_list)
        elif message_type in ["$GPGSV", "$GLGSV"]:
            self.current_cycle[message_type] = self._process_gsv(message_type)

    def _reset_cycle(self) -> None:
        """Сбрасывает текущий цикл."""
        self.current_cycle = {key: None for key in self.current_cycle}

    def start(self) -> None:
        if self.input:
            self.output_lines = []
            with open(self.input, "r") as f:

                for line in f:
                    self.output_lines.append(self.decode_line(line))
            with open(self.output, "w") as f:
                for line in self.output_lines:
                    f.write(line)
        else:
            while True:  # Бесконечный цикл для повторных попыток подключения
                try:
                    self.ser = serial.Serial(
                        port=self.port,
                        baudrate=self.baudrate,
                        timeout=self.timeout
                    )
                    break  # Если подключение успешно, выходим из цикла
                except serial.SerialException as e:
                    if self.print_output:
                        print(
                            f"Error: {e}. Port {self.port} is busy or not available. Waiting {self.timeout} seconds before retry...")
                    # Ожидание перед повторной попыткой
                    time.sleep(self.timeout)

            with open(self.output, "a") as f:
                while True:
                    try:

                        line = self.ser.readline().decode('utf-8').strip()
                        if not line:
                            if self.print_output:
                                print(
                                    f"Нет данных в течение {self.timeout} секунд. "
                                    f"Ожидание новых данных..."
                                )
                            # Ожидание перед повторной попыткой
                            time.sleep(self.timeout)
                            continue  # Продолжить цикл, чтобы снова проверить данные

                        line = self.decode_line(line)
                        f.write(line)
                        if self.print_output and line != "":
                            print(line)

                    except serial.SerialException as e:
                        print(f"Error with serial port: {e}")
                        break

            # Проверяем, открыт ли порт перед его закрытием
            if self.ser.is_open:
                self.ser.close()
                if self.print_output:
                    print("Connection closed")

    def decode_line(self, line: str) -> str:
        """Декодирует строку NMEA и возвращает форматированный результат."""
        if '*' not in line:
            return ""

        message, checksum = line.rsplit('*', 1)

        # Вычисляем контрольную сумму
        calculated_checksum = 0
        for char in message[1:]:
            calculated_checksum ^= ord(char)

        if format(calculated_checksum, '02X') != checksum.strip():
            return ""

        data_list = message.split(",")
        message_type = data_list[0]

        # Обрабатываем сообщение
        self._process_message(message_type, data_list)

        # Если цикл завершен, форматируем вывод и сбрасываем цикл
        if self._check_cycle_complete():
            output_line = self._format_output_line()
            self._reset_cycle()
            return output_line

        return ""

    def _check_satellites(self, satellites: list) -> str:
        satellite_ids = [int(sat_id) for sat_id in satellites if sat_id]
        has_gps = any(1 <= sat_id <= 32 for sat_id in satellite_ids)
        has_glonass = any(65 <= sat_id <= 96 for sat_id in satellite_ids)

        # Возвращаем результат
        if has_gps and has_glonass:
            return "GPS+GLONASS"
        elif has_gps:
            return "GPS"
        elif has_glonass:
            return "GLOANASS"
        else:
            return "n"


def start_app() -> None:
    args = parse_args()
    print(
        f'Logger args:\n - Port: {args.port}\n - Baudrate: {args.baudrate}\n - Output: {args.output}\n - Input: {args.input}\n - Timeout: {args.timeout}\n')

    if daemon and args.daemon:
        with daemon.DaemonContext():
            args.print_output = False
            # Запускаем в контексте дамона
            parser = NMEAParser(
                args.port,
                args.baudrate,
                args.output,
                args.input,
                args.timeout,
            )
            parser.start()
    else:
        parser = NMEAParser(
            args.port,
            args.baudrate,
            args.output,
            args.input,
            args.timeout,
        )
        parser.start()


def main():
    print("Starting logger...", "Developer TG: @Rinapy",
          "GitHub: https://github.com/rinapy")
    try:
        start_app()
    except KeyboardInterrupt:
        print("Logger stopped with User interrupt")


if __name__ == "__main__":
    main()
