# PyLogger-NMEA-0183
Приложение для логирования и парсинга NMEA-0183 данных

## Описание
Это приложение на Python предназначено для работы с устройствами, передающими данные в формате NMEA-0183. Программа позволяет:
- Считывать NMEA сообщения с последовательного порта
- Парсить и декодировать NMEA предложения
- Сохранять полученные данные в лог-файл на компьютере
- Отображать данные в реальном времени

## Флаги
- --port: Порт для считывания данных (например, COM1)
- --baudrate: Скорость передачи данных (например, 9600)
- --output: Путь к файлу для сохранения логов
- --filter: Фильтр для выбора нужных типов сообщений
- --input: Путь к файлу для чтения данных
- --timeout: Время ожидания ответа на COM порт (0 - без ограничения)


## Возможности
- Настраиваемые шаблоны вывода через templates.json
- Возможность компиляции в исполняемый файл с помощью Nuitka
- Поддержка основных типов NMEA сообщений (GGA, RMC, VTG и др.)
- Настраиваемые параметры соединения (COM порт, скорость)
- Гибкая система логирования с указанием пути сохранения
- Валидация контрольной суммы NMEA сообщений
- Возможность фильтрации нужных типов сообщений

## Шаблоны вывода
Приложение использует файл templates.json для настройки формата вывода данных. Пример файла:

```
{
    "$GPGGA": {
        "keys": ["UTC", "latitude", "longitude", "altitude", "satellites"],
        "indexes": [1, 2, 4, 9, 7],
        "template": "{type} UTC:{UTC} Lat:{latitude} Lon:{longitude} Alt:{altitude} Sat:{satellites}\n"
    }
}
```

## Использование
1. Подключите NMEA-совместимое устройство к компьютеру
2. Укажите параметры соединения в конфигурационном файле
3. Запустите приложение
4. Логи будут сохраняться в указанную директорию

## Запуск
Приложение можно запустить двумя способами:

### 1. Чтение с COM-порта

```
python logger.py --port COM1 --baudrate 9600 --output log.txt --filter GPGGA
```

### 2. Чтение из файла

```
python logger.py --input test_data.txt --output log.txt --filter GPGGA
```



## Формат лога
Логи сохраняются в текстовом формате с метками времени:

```
$GPGGA UTC:12:35:19 Lat:4807.038 Lon:01131.000 Alt:545.4 Sat:08
$GPGSA Type:A Mode:3 Satellites:03,22,06,19,11,14,32,01,28,18, PDOP:1.8 HDOP:0.8 VDOP:1.6
$GPRMC Unsupported data
$GPVTG Unsupported data
```

## Запуск
Debian 10:
```
sudo apt install build-essential
python -m nuitka --standalone --onefile --enable-console logger.py
```

Debina 10 v2:
```
sudo apt install python3-venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python logger.py --port ttyS0 --baudrate 9600 --output log.txt --filter GPGGA # Flags optional
```




