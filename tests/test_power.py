import threading
import time
import unittest
from queue import Queue
from unittest.mock import patch

from symmetry.telemetry.power import ArduinoPowerMeter, PowerMonitor
from tests.testutils import RedisResource

b_A = 65
b_V = 86
b_W = 87

ArduinoPowerMeter._default_sensor_node_mapping = {0: 'a', 1: 'b', 2: 'c', 3: 'd'}


class MockedArduinoProgram:
    """
    Mimics https://git.dsg.tuwien.ac.at/mc2/current-sensor/blob/master/mc2-current/mc2-current.ino
    """

    def __init__(self) -> None:
        self.queue = Queue()

    def write(self, pattern):
        for c in pattern:
            if c == b_A:
                self.queue.put('0.1 0.2 0.3 0.4')
            elif c == b_V:
                self.queue.put('11.1 11.2 11.3 11.4')
            elif c == b_W:
                self.queue.put('41.1 42.2 43.3 44.4')

    def readline(self):
        return ('%s\n' % self.queue.get_nowait()).encode('ASCII')

    def close(self):
        pass


class ArduinoPowerMeterTest(unittest.TestCase):

    @patch('serial.Serial')
    def test_integration(self, serial):
        serial.return_value = MockedArduinoProgram()

        mapping = {0: 'a', 1: 'b', 2: 'c', 3: 'd'}

        with ArduinoPowerMeter(mapping=mapping, request_pattern='AVW', arduino_path='fake') as power_meter:
            error = None
            values = None
            try:
                values = power_meter.read()
            except Exception as e:
                error = e

        if error:
            self.fail('caught exception %s' % error)

        expected = {'a': {'amp': [0.1], 'mV': [11.1], 'watt': [41.1]},
                    'b': {'amp': [0.2], 'mV': [11.2], 'watt': [42.2]},
                    'c': {'amp': [0.3], 'mV': [11.3], 'watt': [43.3]},
                    'd': {'amp': [0.4], 'mV': [11.4], 'watt': [44.4]}}

        self.assertEqual(expected, values)


class PowerMonitorTest(unittest.TestCase):
    redis = RedisResource()

    @classmethod
    def setUpClass(cls) -> None:
        cls.redis.setUp()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.redis.tearDown()

    def tearDown(self) -> None:
        self.redis.rds.flushall()

    @patch('symmetry.telemetry.power._find_arduino_device_address')
    @patch('serial.Serial')
    def test_sends_telemetry(self, serial, mocked_device_addresses):
        mocked_device_addresses.return_value = 'fake_arduino'
        serial.return_value = MockedArduinoProgram()

        pubsub = self.redis.rds.pubsub()
        pubsub.psubscribe('telem/*')

        power_monitor = PowerMonitor(self.redis.rds, interval=0.1)
        thread = threading.Thread(target=power_monitor.run)
        thread.start()
        then = time.time()

        next(pubsub.listen())  # psubscribe message
        msg1 = next(pubsub.listen())
        msg2 = next(pubsub.listen())
        msg3 = next(pubsub.listen())
        msg4 = next(pubsub.listen())

        power_monitor.cancel()
        pubsub.close()

        thread.join(2)

        self.assertEqual('telem/a/watt', msg1['channel'])
        self.assertEqual('telem/b/watt', msg2['channel'])
        self.assertEqual('telem/c/watt', msg3['channel'])
        self.assertEqual('telem/d/watt', msg4['channel'])

        t1, v1, = msg1['data'].split(' ')
        t2, v2, = msg2['data'].split(' ')
        t3, v3, = msg3['data'].split(' ')
        t4, v4, = msg4['data'].split(' ')

        self.assertAlmostEqual(then, float(t1), delta=1.5)
        self.assertAlmostEqual(then, float(t2), delta=1.5)
        self.assertAlmostEqual(then, float(t3), delta=1.5)
        self.assertAlmostEqual(then, float(t4), delta=1.5)

        self.assertEqual('41.1', v1)
        self.assertEqual('42.2', v2)
        self.assertEqual('43.3', v3)
        self.assertEqual('44.4', v4)

    @patch('symmetry.telemetry.power._find_arduino_device_address')
    @patch('serial.Serial')
    def test_aggregate_sends_telemetry(self, serial, mocked_device_addresses):
        mocked_device_addresses.return_value = 'fake_arduino'
        serial.return_value = MockedArduinoProgram()

        pubsub = self.redis.rds.pubsub()
        pubsub.psubscribe('telem/*')

        power_monitor = PowerMonitor(self.redis.rds, interval=0.1, aggregate=4)
        thread = threading.Thread(target=power_monitor.run)
        thread.start()
        then = time.time()

        next(pubsub.listen())  # psubscribe message
        msg1 = next(pubsub.listen())
        msg2 = next(pubsub.listen())
        msg3 = next(pubsub.listen())
        msg4 = next(pubsub.listen())

        power_monitor.cancel()
        pubsub.close()

        thread.join(2)

        self.assertEqual('telem/a/watt', msg1['channel'])
        self.assertEqual('telem/b/watt', msg2['channel'])
        self.assertEqual('telem/c/watt', msg3['channel'])
        self.assertEqual('telem/d/watt', msg4['channel'])

        t1, v1, = msg1['data'].split(' ')
        t2, v2, = msg2['data'].split(' ')
        t3, v3, = msg3['data'].split(' ')
        t4, v4, = msg4['data'].split(' ')

        self.assertAlmostEqual(then, float(t1), delta=1.5)
        self.assertAlmostEqual(then, float(t2), delta=1.5)
        self.assertAlmostEqual(then, float(t3), delta=1.5)
        self.assertAlmostEqual(then, float(t4), delta=1.5)

        self.assertEqual('41.1', v1)
        self.assertEqual('42.2', v2)
        self.assertEqual('43.3', v3)
        self.assertEqual('44.4', v4)
