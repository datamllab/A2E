# Available Tools

Your available tools for managing smart office devices:

## SearchDevices
Searches for smart office devices connected to the system. Returns a list of devices, each containing device_id, device_name, device_type (e.g., 'light', 'thermostat', 'camera', 'alarm', 'appliance', 'sensor', 'switch'), and device_status (including current state and area).

**Parameters:**
- `device_type` (optional): The type of device to search for (e.g., 'light', 'thermostat', 'camera'). If not specified, returns all connected devices.

## ListDeviceActions
Retrieves a list of possible actions that can be performed on a specified smart office device. Returns action_name, action_description, and action_parameters for each available action.

**Parameters:**
- `device_id` (required): The unique identifier of the smart office device.

## ControlDevice
Controls a specified smart office device by turning it on/off, adjusting its settings, or performing other actions. The available actions depend on the device type.

**WARNING:** Some devices (security cameras, alarms, refrigerators, fire alarms) should not be turned off without careful consideration of the consequences.

**Parameters:**
- `device_id` (required): The unique identifier of the smart office device to control.
- `action` (required): The action to perform on the device (e.g., 'turn on', 'turn off', 'set temperature'). Must match the actions returned by ListDeviceActions for the specified device.
- `parameters` (optional): Additional parameters for the action (e.g., temperature value, brightness level).