from typing import Union


class LineParser:
    def __init__(self,data:str, line: str):
        self.data = data
        self.line = line

    def parse(self) -> str:
        data = self.__line_processing(self.data, self.line)
        return data

    def __line_processing(self, data: str, line: str) -> str:
        if '|' not in line:
            return data
        operations = line.split('|')
        for operation in operations:
            if 'split' in operation:
                if isinstance(data, list):
                    raise ValueError(
                        'template not valid two times split operation')
                sep = operation.split('/')[1]

                counts = -1 if operation.split(
                    '/')[2] == '' else int(operation.split('/')[2])

                data = self.__split(data, sep, counts)
            if 'truncate' in operation:
                truncate_value = 0 if operation.split('/')[1] == '' else int(
                    operation.split('/')[1])

                if isinstance(data, list):
                    data = [
                        self.__truncate(float(value), truncate_value)
                        if value.replace('.', '').isdigit() else value
                        for value in data
                    ]

                

                if isinstance(data, (float, int, str)):
                    data = self.__truncate(data, truncate_value)
            if 'join' in operation:
                sep = operation.split('/')[1]

                if isinstance(data, list):
                    data = self.__join(data, sep)
                else:
                    raise ValueError(
                        'template not valid join operation for not list')
            if 'slice' in operation:
                counts = None if operation.split('/')[1] == '' else int(
                    operation.split('/')[1])
                if counts is None:
                    return data
                length = (
                    len(str(data)) if operation.split('/')[2] == ''
                    else int(operation.split('/')[2]) * counts
                )

                data = self.__slice(str(data), length, counts)

        return data

    def __split(self, data: str, sep: str, counts: int) -> str:
        return data.split(sep, counts)

    def __truncate(self, data: Union[int, float], counts: Union[int, None]) -> str:
        # Преобразуем число в строку
        str_number = str(data)
        
        # Находим позицию десятичной точки
        if '.' in str_number:
            # Разделяем целую и дробную части
            integer_part, decimal_part = str_number.split('.')
            
            # Обрезаем дробную часть до n знаков
            truncated_decimal = decimal_part[:counts]
            
            # Соединяем целую и дробную части обратно
            return f"{integer_part}.{truncated_decimal}" if truncated_decimal else integer_part
        else:
            return str_number

    def __slice(self, data: str, length: int, counts: int) -> str:
        return [data[i:i+counts] for i in range(0, length, counts)]

    def __join(self, data: list, sep: str) -> str:
        data = [str(item) for item in data]

        return sep.join(data)


if __name__ == '__main__':

    parser = LineParser("054010.00", "~truncate/0/|slice/2/|join/:/|~") # 54:01:0 
    print(parser.parse())
    parser = LineParser("134731.361", "~truncate/0/|slice/2/|join/:/|~") # 13:47:31
    print(parser.parse())
    
