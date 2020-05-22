import logging
import time

import serial
import serial.tools.list_ports

logger = logging.getLogger(__name__)

_arduino_vids = {
    int('0x2341', 16),
    int('0x2a03', 16),
    int('0x1a86', 16)  # some arduino nano
}


def _find_arduino_device_address():
    all_devices = serial.tools.list_ports.comports()
    arduinos = [device for device in all_devices if device.vid in _arduino_vids]

    if len(arduinos) < 1:
        raise IOError('No Arduino found on COM ports')
    if len(arduinos) > 1:
        raise IOError('More than one Arduino found on COM ports')

    return arduinos[0].device


class ArduinoPowerMeter:
    _command_map = {
        'A': 'amp',
        'W': 'watt',
        'V': 'mV'
    }

    _default_sensor_node_mapping = {
        0: 'sensor0',
        1: 'sensor1',
        2: 'sensor2',
        3: 'sensor3'
    }

    def __init__(self, mapping=None, request_pattern='W', arduino_path=None, baudrate=115200):
        self.mapping = mapping or self._default_sensor_node_mapping
        self.request_pattern = request_pattern

        # The usb serial adapter vendor id's used by the Arduino Foundation.
        # Used to identify which serial device is the right one
        self.arduino_path = arduino_path

        self.baudrate = baudrate
        self.address = None
        self.connection = None

    def connect(self):
        self.address = self.arduino_path or _find_arduino_device_address()
        self.connection = serial.Serial(self.address, self.baudrate)

    def disconnect(self):
        if self.connection:
            self.connection.close()

    def _parse_values(self, line):
        return [float(v) for v in line.decode('ASCII').strip().split(' ')]

    def _name_for_command(self, command):
        return self._command_map.get(command, command)

    def read(self):
        # the arduino program sends data back on request (it listens for an arbitrary sequence of 'W','A' or 'V'
        # and then sends data in one line)
        self.connection.write(str.encode(self.request_pattern))
        values = {}
        for command in self.request_pattern:
            returned_readings = self.connection.readline()
            parsed_values = self._parse_values(returned_readings)
            name = self._name_for_command(command)

            for i in range(len(parsed_values)):
                try:
                    values[self.mapping[i]]
                except KeyError:
                    values[self.mapping[i]] = {}
                try:
                    values[self.mapping[i]][name]
                except KeyError:
                    values[self.mapping[i]][name] = []

                values[self.mapping[i]][name].append(parsed_values[i])

        logger.debug('arduino power meter readings %s: %s', self.request_pattern, values)

        return values

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return self


class PowerMonitor:

    def __init__(self, redis_client, interval=None, aggregate=1, sensor_names=None) -> None:
        super().__init__()
        self.redis_client = redis_client
        self.interval = interval or 1.
        self._cancelled = False

        self.aggregate = aggregate
        self.request_pattern = 'W' * self.aggregate
        self.sensor_names = sensor_names

    def run(self):
        rds = self.redis_client
        retrying = False
        aggregate = self.aggregate > 1

        logger.info('starting to listen in power meter at interval %.2f s', self.interval)
        while not self._cancelled:  # connect / IOError retry loop
            try:
                with ArduinoPowerMeter(mapping=self.sensor_names, request_pattern=self.request_pattern) as power_meter:
                    if retrying:
                        logger.info("Arduino is now connected")
                        retrying = False

                    next_time = time.time()

                    while not self._cancelled:  # read loop
                        next_time += self.interval

                        then = time.time()
                        readings = power_meter.read()
                        timestamp = time.time()

                        for node, reading in readings.items():
                            for unit, values in reading.items():

                                if aggregate:
                                    value = sum(values) / len(values)
                                    rds.publish('telem/%s/%s' % (node, unit), "%s %s" % (timestamp, value))
                                else:
                                    for value in values:
                                        rds.publish('telem/%s/%s' % (node, unit), "%s %s" % (timestamp, value))

                        logger.debug('arduino read + publish %s took %.4f ms' %
                                     (power_meter.request_pattern, (time.time() - then) * 1000))

                        time.sleep(max(0., next_time - time.time()))
            except IOError as e:
                if not retrying:
                    logger.warning('IO error while accessing Arduino: %s Retrying every 10 seconds...', e)
                retrying = True
                for i in range(10):
                    time.sleep(1)
                    if self._cancelled:
                        break

        logger.info('power monitor control loop exiting')

    def cancel(self):
        self._cancelled = True
