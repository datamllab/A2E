# Available Tools

## Smart Home Tools

| Tool | Description |
|------|-------------|
| get_devices | List all smart home devices and their status |
| get_scenes | List available smart home scenes |
| control_device | Control a specific smart home device |
| execute_scene | Execute a predefined smart home scene |

### get_devices

List all smart home devices and their current status.

**Parameters:** None

**Returns:** List of devices with their ID, name, type, status, and other relevant properties (e.g., temperature for thermostats, brightness for lights).

### get_scenes

List all available smart home scenes and their associated actions.

**Parameters:** None

**Returns:** List of scenes with their ID, name, and action details.

### control_device

Control a specific smart home device by performing an action.

**Parameters:**
- `device_id` (string, required): The ID of the device to control
- `action` (string, required): The action to perform (e.g., "set_temperature", "turn_on", "turn_off")
- `params` (object, optional): Additional parameters (e.g., {"temperature": 25} for thermostat adjustment)

**Returns:** Result of the control action including device name, new status, and confirmation message.

### execute_scene

Execute a predefined smart home scene.

**Parameters:**
- `scene_id` (string, required): The ID of the scene to execute

**Returns:** Scene execution result including the scene name and list of executed actions.

## Recommended Workflow

When adjusting smart home settings (e.g., thermostat temperature):

1. Use `get_devices` to identify all available devices and their current status
2. Verify the correct device by checking device name, type, and location
3. Use `control_device` with the verified device ID and appropriate action/params
4. Confirm the result with the user