import json
from typing import Union
from argparse import ArgumentParser, Namespace
import time

import serial

from line_parser import LineParser


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
        "-f",
        "--filter",
        type=str,
        default="",
        help="Filter",
    )

    parser.add_argument(
        "-t",
        "--timeout",
        type=int,
        default=0,
        help="Timeout in seconds for attempt to reconnect to the port",
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
        filter: str,
        input: Union[str, None] = None,
        template_path: Union[str, None] = None,
        timeout: int = 0,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.input = input
        self.output = output
        self.filter = filter
        self.template_path = template_path or "templates.json"
        self.message_parsers = self._load_templates()
        self.timeout = timeout

    def _load_templates(self) -> dict:
        with open(self.template_path, 'r') as f:
            templates = json.load(f)

        # Преобразуем строковые slice в объекты slice
        for message_type in templates:
            indexes = templates[message_type]['indexes']
            for i, idx in enumerate(indexes):
                if isinstance(idx, str) and ':' in idx and '~' not in idx:
                    start, end = map(int, idx.split(':'))
                    indexes[i] = slice(start, end)

        return templates

    def start(self) -> None:
        print(self.input)
        if self.input:
            self.output_lines = []
            with open(self.input, "r") as f:
                for line in f:
                    if line.startswith(self.filter):
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
                    print(f"Error: {e}. Port {self.port} is busy or not available. Waiting {self.timeout} seconds before retry...")
                    time.sleep(self.timeout)  # Ожидание перед повторной попыткой

            while True:
                try:
        
                    line = self.ser.readline().decode('utf-8').strip()
                    if not line:
                        print(
                            f"Нет данных в течение {self.timeout} секунд. "
                            f"Ожидание новых данных..."
                        )
                        time.sleep(self.timeout)  # Ожидание перед повторной попыткой
                        continue  # Продолжить цикл, чтобы снова проверить данные

                    with open(self.output, "a") as f:
                        if line.startswith(self.filter):
                            line = self.decode_line(line)
                            f.write(line)

                except serial.SerialException as e:
                    print(f"Error with serial port: {e}")
                    break
            
            # Проверяем, открыт ли порт перед его закрытием
            if self.ser.is_open:
                self.ser.close()
                print("Connection closed")

    def decode_line(self, line: str) -> str:
        # Проверяем наличие контрольной суммы
        if '*' not in line:
            return "Invalid message: no checksum\n"

        message, checksum = line.rsplit('*', 1)

        # Вычисляем контрольную сумму
        calculated_checksum = 0
        for char in message[1:]:  # Пропускаем начальный символ '$'
            calculated_checksum ^= ord(char)

        # Сравниваем с полученной контрольной суммой
        if format(calculated_checksum, '02X') != checksum.strip():
            return (
                f"Invalid message: checksum mismatch "
                f"(calculated: {format(calculated_checksum, '02X')}, "
                f"received: {checksum.strip()})\n"
            )

        data_list = message.split(",")
        data = {}
        message_type = data_list[0]

        if message_type in self.message_parsers:
            parser = self.message_parsers[message_type]
            for key, idx in zip(parser["keys"], parser["indexes"]):
                if isinstance(idx, slice):
                    data[key] = ",".join(data_list[idx])
                elif isinstance(idx, str) and '~' in idx:
                    idx, operation = int(idx.split('~')[0]), idx.split('~')[1]
                    data[key] = LineParser(data_list[idx], operation).parse()
                else:
                    data[key] = data_list[idx]
            data["type"] = message_type
            return parser["out_msg_template"].format(**data)

        return f"{message_type} Unsupported data\n"


def start_app() -> None:
    args = parse_args()
    print(f'Logger args: Port: {args.port}, Baudrate: {args.baudrate}, Output: {args.output}, Filter: {"All" if args.filter == "" else args.filter}, Input: {args.input}, Timeout: {args.timeout}')
    parser = NMEAParser(
        args.port,
        args.baudrate,
        args.output,
        args.filter,
        args.input,
        timeout=args.timeout
    )
    parser.start()


if __name__ == "__main__":
    print("Starting logger...", "Developer TG: @Rinapy", "GitHub: https://github.com/rinapy")
    try:
        start_app()
    except KeyboardInterrupt:
        print("Logger stopped with User interrupt")
