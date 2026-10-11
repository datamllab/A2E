# Available Tools

## Agriculture Tools

### crop_analyzer

A tool for monitoring crop health, analyzing soil conditions, and tracking growth patterns using satellite and sensor data to optimize agricultural yields.

**Parameters:**
- `query` (string, required): Query parameter

**Returns:** Crop health analysis results with soil readings, crop health index, and yield projections.

### irrigation_controller

A tool for scheduling and managing irrigation systems, controlling water distribution, and optimizing resource usage across agricultural zones.

**Parameters:**
- `query` (string, required): Query parameter

**Returns:** Irrigation system status report with zone conditions, water usage, and schedule information.

### FieldGPSValidator

A tool to confirm the accuracy of field GPS data, ensuring the autonomous equipment follows the correct path and avoids hazardous terrain.

**Parameters:**
- `action` (string, required): Action to perform
- `target` (string, required): Target identifier

**Returns:** GPS validation results for the specified equipment and route.