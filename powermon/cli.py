import argparse
import logging
import os
import signal

import redis

from powermon.monitor import PowerMonitor

logger = logging.getLogger(__name__)


def get_redis():
    return redis.Redis(
        host=os.getenv('telemd_redis_host', 'localhost'),
        port=int(os.getenv('telemd_redis_port', 6379)),
        decode_responses=True
    )


def read_sensor_names(args):
    return {
        0: args.sensor0,
        1: args.sensor1,
        2: args.sensor2,
        3: args.sensor3,
    }


def main():
    log_level = os.getenv('telemd_logging_level')
    if log_level:
        logging.basicConfig(level=logging._nameToLevel[log_level])

    parser = argparse.ArgumentParser()
    parser.add_argument('--interval', help='sampling interval', type=float,
                        default=os.getenv('powermon_sampling'))
    parser.add_argument('--aggregate', help='number of values to read and aggregate', type=int,
                        default=os.getenv('powermon_values_aggregate', 1))
    for i in range(4):
        parser.add_argument('--sensor%d' % i, help='name for sensor%d' % i, type=str,
                            default=os.getenv('powermon_sensor_%d' % i, 'sensor%i' % i))
    args = parser.parse_args()
    rds = get_redis()
    sensor_names = read_sensor_names(args)
    powmon = PowerMonitor(rds, interval=args.interval, aggregate=args.aggregate, sensor_names=sensor_names)

    def terminate(signum, frame):
        logger.info('signal received %s', signum)
        powmon.cancel()
        raise NotImplementedError

    signal.signal(signal.SIGINT, terminate)
    signal.signal(signal.SIGTERM, terminate)

    try:
        logging.info('starting power monitor')
        powmon.run()
    except KeyboardInterrupt:
        pass
    finally:
        logger.info('stopping power monitor...')
        powmon.cancel()


if __name__ == '__main__':
    main()
