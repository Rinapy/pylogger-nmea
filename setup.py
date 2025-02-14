from setuptools import setup, find_packages

setup(
    name='pyloggernmea',
    version='0.0.1',
    packages=find_packages(),
    install_requires=[
        'pyserial',
        'pytest',
        'python-daemon',
    ],
    entry_points={
        'console_scripts': [
            'pyloggernmea = pyloggernmea.logger:main',
        ],
    },
    description='Utility for logging and decoding NMEA messages.',
    author='Rinapy',
    author_email='roma.minaev0@gmail.com',
    url='https://github.com/rinapy/pyloggernmea',
)