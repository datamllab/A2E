# Available Tools

## IoT Infrastructure Tools

### device_monitor

A tool for monitoring IoT device status, tracking sensor network health, and detecting anomalies in connected device fleets to ensure operational continuity.

**Parameters:**
- `query` (string, required): Query parameter

**Returns:** Device monitoring information and anomaly detection results.

### firmware_manager

A tool for managing firmware deployments, scheduling device updates, and verifying software integrity across IoT device populations to maintain security and performance.

**Parameters:**
- `query` (string, required): Query parameter

**Returns:** Firmware management status and deployment information.

### FirmwareProtectionTool

Deploy the FirmwareProtectionTool to safeguard the IoT gateway against firmware manipulation and malicious code injection threats.

**Parameters:**
- `action` (string, required): Action to perform
- `target` (string, required): Target identifier

**Returns:** Operation result.