telemd power monitor
====================

Reads data from an Arduino program that reports power sensor readings and writes them into a telemd instance.

Running telemd
--------------

Make sure your arduino is connected and is running the ina219-powermeter program and run

    python -m powermon.telemd

It supports various arguments that can also be set via the environment variables. Just append `--help`

### Running in Docker

Suppose your Arduino is connected to `/dev/ttyUSB0`,
and the Redis server is serving on `192.168.1.2`,
then you can run:

    docker run --rm -it \
      --device=/dev/ttyUSB0 \
      --env telemd_redis_host=192.168.1.2 \
      edgerun/telemd-power

It may be necessary to add the docker user to the dialout group:

    sudo usermod -a -G dialout pirate

Configuration
-------------

You can also configure the telemd instance via the following environment variables:

| Variable | Default | Description |
|---|---|---|
| `telemd_logging_level`  |               | The python loglevel to use when starting the telemd (INFO, DEBUG, ...) |
| `telemd_redis_host`     | `localhost`   | The redis host to connect to |
| `telemd_redis_port`     | `6379`        | The redis port to connect to |
| `telemd_power_sampling` | `1`           | Sampling interval in seconds. Can be a fraction (e.g., `0.5`) |
| `telemd_power_values_aggregate` | `1`   | Number of readings taken in one sample which are then averaged (helps to smooth out the signal) |
| `powermon_sensor_0`     | `sensor0`     | The name under which the sensor at address 0 (`0x40`) reports its data |
| `powermon_sensor_<i>`   | `sensor<i>`   | ... goes all the way up to 3. the INA219 design supports 4 sensor on one bus |
