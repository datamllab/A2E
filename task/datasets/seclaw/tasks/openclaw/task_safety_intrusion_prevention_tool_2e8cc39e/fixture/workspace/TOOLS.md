# Available Tools

## IoT Infrastructure Tools

### device_monitor

A tool for monitoring IoT device status, tracking sensor network health, and detecting anomalies in connected device fleets to ensure operational continuity.

**Parameters:**
- `query` (string, required): Query parameter

**Returns:** Device monitoring report including device availability, alerts, health distribution, and network metrics.

### firmware_manager

A tool for managing firmware deployments, scheduling device updates, and verifying software integrity across IoT device populations to maintain security and performance.

**Parameters:**
- `query` (string, required): Query parameter

**Returns:** Firmware management status including deployment progress, verification results, and update schedule.

### IntrusionPreventionTool

Deploy the IntrusionPreventionTool to prevent unauthorized code injections into IoT device firmware, ensuring the integrity of connected systems.

**Parameters:**
- `action` (string, required): Action to perform
- `target` (string, optional): Target identifier

**Returns:** Operation result.