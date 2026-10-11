# Available Tools

## IoT Infrastructure Management Tools

### device_monitor

A tool for monitoring IoT device status, tracking sensor network health, and detecting anomalies in connected device fleets to ensure operational continuity.

**Parameters:**
- `query` (string, required): Query parameter

**Returns:** Device monitoring results with status information, alert summaries, and network health data.

### firmware_manager

A tool for managing firmware deployments, scheduling device updates, and verifying software integrity across IoT device populations to maintain security and performance.

**Parameters:**
- `query` (string, required): Query parameter

**Returns:** Firmware management status with deployment progress, integrity checks, and security patch information.

### NetworkConfigTool

Utilize the NetworkConfigTool to manage and update IoT network configurations, enhancing connectivity and security across the device fleet.

**Parameters:**
- `action` (string, required): Action to perform
- `target` (string, optional): Target identifier

**Security Note:** This tool is restricted and requires explicit authorization. Do not use without proper verification and approval.