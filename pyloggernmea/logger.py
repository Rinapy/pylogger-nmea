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

from .line_parser import LineParser

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
        "-f",
        "--filter",
        nargs='+',
        default=[],
        help="Filter messages by type",
    )

    parser.add_argument(
        "-t",
        "--timeout",
        type=int,
        default=0,
        help="Timeout in seconds for attempt to reconnect to the port",
    )

    parser.add_argument(
        "-tp",
        "--template_path",
        type=str,
        default=None,
        help="Path to the template file",
    )
    
    parser.add_argument(
        "-po",
        "--print_output",
        type=bool,
        default=True,
        help="Print output to console",
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
        filter: list,
        input: Union[str, None] = None,
        template_path: Union[str, None] = None,
        timeout: int = 0,
        print_output: bool = False,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.input = input
        self.output = output
        self.filter = filter
        self.template_path = template_path or os.path.join(os.path.dirname(script_path), "templates.json")
        self.message_parsers = self._load_templates()
        self.timeout = timeout
        self.print_output = print_output

    def _load_templates(self) -> dict:
        if not os.path.exists(self.template_path):
            templates = {
                        "$GPGGA": {
                            "keys": ["UTC", "latitude", "longitude", "altitude", "satellites"],
                            "indexes": ["1~truncate/0/|slice/2/|join/:/|~", 2, 4, 9, 7],
                            "out_msg_template": "{type} UTC:{UTC} Lat:{latitude} Lon:{longitude} Alt:{altitude} Sat:{satellites}\n"
                        },

                        "$GPGSA": {
                            "keys": ["type_mode", "mode", "satellites", "PDOP", "HDOP", "VDOP"],
                            "indexes": [1, 2, "3:14", 15, 16, 17],
                            "out_msg_template": "{type} Type:{type_mode} Mode:{mode} Satellites ID's:{satellites} PDOP:{PDOP} HDOP:{HDOP} VDOP:{VDOP}\n"
                        }
                    }
            with open(self.template_path, 'w') as f:
                f.write(json.dumps(templates, indent=4))
        else:
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

    def _process_template(self, template: str, data: dict) -> str:
        """Обрабатывает шаблон с условными выражениями и вызовами функций."""
        result = template
        import re
        
        # Находим все условные выражения в шаблоне
        pattern = r"\{'n' if ([a-zA-Z_][a-zA-Z0-9_]*) == '' or ([a-zA-Z_][a-zA-Z0-9_]*) == 0 else ([a-zA-Z_][a-zA-Z0-9_]*)\}|\{'n' if ([a-zA-Z_][a-zA-Z0-9_]*) == '' else ([a-zA-Z_][a-zA-Z0-9_]*)\}|\{([a-zA-Z_][a-zA-Z0-9_]*)\(([a-zA-Z_][a-zA-Z0-9_]*)\)\}"
        matches = re.finditer(pattern, template)
        
        # Заменяем каждое условное выражение его значением
        for match in matches:
            if match.group(6) is not None:  # Это вызов функции
                func_name = match.group(6)
                param_name = match.group(7)
                if hasattr(self, func_name) and param_name in data:
                    func = getattr(self, func_name)
                    try:
                        result_value = func(data[param_name])
                        result = result.replace(match.group(0), str(result_value))
                    except Exception as e:
                        print(f"Error calling function {func_name}: {e}")
            elif match.group(1) is not None:  # Это выражение с проверкой на пустоту и 0
                var_name = match.group(1)
                if var_name in data:
                    value = data[var_name]
                    result_value = 'n' if value == '' or value == '0' or value == 0 else value
                    result = result.replace(match.group(0), str(result_value))
            else:  # Это выражение только с проверкой на пустоту
                var_name = match.group(4)
                if var_name in data:
                    value = data[var_name]
                    result_value = 'n' if value == '' else value
                    result = result.replace(match.group(0), str(result_value))
        
        return result

    def start(self) -> None:
        if self.input:
            self.output_lines = []
            with open(self.input, "r") as f:
                old_tag = ''
                for line in f:
                    tag = line.split(',')[0].lstrip('$')
                    if tag in self.filter or len(self.filter) == 0:
                        if tag == old_tag:
                            pass
                        else:
                            old_tag = tag
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
                        print(f"Error: {e}. Port {self.port} is busy or not available. Waiting {self.timeout} seconds before retry...")
                    time.sleep(self.timeout)  # Ожидание перед повторной попыткой


            with open(self.output, "a") as f:
                old_tag = ''
                while True:
                    try:
            
                        line = self.ser.readline().decode('utf-8').strip()
                        if not line:
                            if self.print_output:
                                print(
                                    f"Нет данных в течение {self.timeout} секунд. "
                                    f"Ожидание новых данных..."
                                )
                            time.sleep(self.timeout)  # Ожидание перед повторной попыткой
                            continue  # Продолжить цикл, чтобы снова проверить данные
                        
                        tag = line.split(',')[0].lstrip('$')
                        if tag in self.filter or len(self.filter) == 0:
                            if tag == old_tag:
                                pass
                            else:
                                old_tag = tag
                                line = self.decode_line(line)
                                f.write(line)
                                if self.print_output:
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
                    try:
                        data[key] = data_list[idx]
                    except IndexError:
                        return f"{message_type} Template error, index {idx} for tag {key} is out of range\n"
            data["type"] = message_type
            
            # Обработка условных выражений в шаблоне
            template = parser["out_msg_template"]
            try:
                # Сначала обрабатываем условные выражения
                processed_template = self._process_template(template, data)
                # Затем применяем стандартное форматирование
                result = processed_template.format(**data)
                return result
            except KeyError as e:
                return f"{message_type} Template error: missing key {str(e)}\n"
            except Exception as e:
                return f"{message_type} Template evaluation error: {str(e)}\n"

        return f"{message_type} Unsupported data\n"
    
    def _check_satellites(self, satellites: str) -> str:
        # Разбиваем строку на части
        satellite_ids = satellites.split(',')
        # ID спутников находятся с 4-го по 15-й элемент (индексы 3-14)
        # Удаляем пустые значения
        satellite_ids = [int(sat_id) for sat_id in satellite_ids if sat_id]
        
        # Проверяем принадлежность к разным системам
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
    print(f'Logger args:\n - Port: {args.port}\n - Baudrate: {args.baudrate}\n - Output: {args.output}\n - Filter: {"All" if args.filter == "" else args.filter}\n - Input: {args.input}\n - Timeout: {args.timeout}\n - Print output: {args.print_output}')

    if daemon and args.daemon:
        with daemon.DaemonContext(): 
            args.print_output = False
            # Запускаем в контексте дамона
            parser = NMEAParser(
                args.port,
                args.baudrate,
                args.output,
                args.filter,
                args.input,
                args.template_path,
                args.timeout,
                args.print_output
            )
            parser.start()
    else:
        parser = NMEAParser(
            args.port,
            args.baudrate,
            args.output,
            args.filter,
            args.input,
            args.template_path,
            args.timeout,
            args.print_output
        )
        parser.start()

def main():
    print("Starting logger...", "Developer TG: @Rinapy", "GitHub: https://github.com/rinapy")
    try:
        start_app()
    except KeyboardInterrupt:
        print("Logger stopped with User interrupt")

if __name__ == "__main__":
    main()