"""Support for reading Current Cost data from a serial port."""
import json
import logging
import xmltodict

import serial_asyncio
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_DEVICES, EVENT_HOMEASSISTANT_STOP
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)


CONF_SERIAL_PORT = "serial_port"
CONF_BAUDRATE = "baudrate"
CONF_DEVICES = "devices"

DEFAULT_NAME = "Current Cost"
DEFAULT_BAUDRATE = 57600
DEFAULT_DEVICES = [0,1,2,3,4,5,6,7,8,9]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SERIAL_PORT): cv.string,
        vol.Optional(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): cv.positive_int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_DEVICES, default=DEFAULT_DEVICES): vol.All(cv.ensure_list, [vol.Range(min=0, max=9)]),
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Current Cost sensor platform."""
    name = config.get(CONF_NAME)
    port = config.get(CONF_SERIAL_PORT)
    baudrate = config.get(CONF_BAUDRATE)
    devices = config.get(CONF_DEVICES)
    _LOGGER.debug("devices: %s", config.get(CONF_DEVICES))
    #sensor = []
    sensor = CurrentCostSensor(name, port, baudrate, devices)
    #for variable in devices:
    #    sensor.append(CurrentCostSensor(f"{name}_appliance_{variable}", port, baudrate))
    #sensor.append(CurrentCostSensor(f"{name}_temperature", port, baudrate))

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, sensor.stop_serial_read())
    async_add_entities([sensor], True)


class CurrentCostSensor(Entity):
    """Representation of a Current Cost sensor."""

    def __init__(self, name, port, baudrate, devices):
        """Initialize the Current Cost sensor."""
        self._name = name
        self._unit = "W"
        self._icon = "mdi:flash-circle"
        self._device_class = "power"
        self._state = None
        self._port = port
        self._baudrate = baudrate
        self._serial_loop_task = None
        self._attributes = {"Temperature": None}
        for variable in devices:
            self._attributes[f"Appliance {variable}"] = None

    async def async_added_to_hass(self):
        """Handle when an entity is about to be added to Home Assistant."""
        self._serial_loop_task = self.hass.loop.create_task(
            self.serial_read(self._port, self._baudrate)
        )

    async def serial_read(self, device, rate, **kwargs):
        """Read the data from the port."""
        reader, _ = await serial_asyncio.open_serial_connection(
            url=device, baudrate=rate, **kwargs
        )
        while True:
            line = await reader.readline()
            line = line.decode("utf-8").strip()
            _LOGGER.debug("Line Received: %s", line)

            try:
                data = xmltodict.parse(line)
            except:
                _LOGGER.error("Error parsing data from serial port: %s", line)
                pass
            try:
                appliance = int(data['msg']['sensor'])
            except:
                appliance = None
                pass
            try:
                temperature = float(data['msg']['tmpr'])
            except:
                temperature = None
                pass
            try:
                imp = int(data['msg']['imp'])
                ipu = int(data['msg']['ipu'])
            except:
                imp = None
                ipu = None
                pass
            try:
                wattsch1 = int(data['msg']['ch1']['watts'])
            except:
                wattsch1 = 0
                pass
            try:
                wattsch2 = int(data['msg']['ch2']['watts'])
            except:
                wattsch2 = 0
                pass
            try:
                wattsch3 = int(data['msg']['ch3']['watts'])
            except:
                wattsch3 = 0
                pass
            total_watts = wattsch1 + wattsch2 + wattsch3
            if appliance == 0:
                self._state = total_watts
                self._attributes[f"Channel 1"] = f"{wattsch1} W"
                self._attributes[f"Channel 2"] = f"{wattsch2} W"
                self._attributes[f"Channel 3"] = f"{wattsch3} W"
            if appliance is not None:
                if imp is not None:
                    self._attributes[f"Impulses {appliance}"] = imp
                    self._attributes[f"Impulses/Unit {appliance}"] = ipu
                else:
                    self._attributes[f"Appliance {appliance}"] = f"{total_watts} W"
            if temperature is not None:
                self._attributes["Temperature"] = f"{temperature} ºC"
            self.async_schedule_update_ha_state()

    async def stop_serial_read(self):
        """Close resources."""
        if self._serial_loop_task:
            self._serial_loop_task.cancel()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_state_attributes(self):
        """Return the attributes of the entity (if any JSON present)."""
        return self._attributes

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return self._unit

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class
