# Available Tools

## Maritime Navigation Tools

### route_planner

A tool for planning and optimizing vessel routes, considering traffic patterns, weather conditions, and safety protocols for high-traffic port areas.

**Parameters:**
- `query` (string, required): Query parameter for route planning

**Returns:** Route planning and optimization results.

### safety_monitor

A tool for monitoring vessel safety status, weather conditions, sea state, and regulatory compliance for port operations.

**Parameters:**
- `query` (string, required): Query parameter for safety monitoring

**Returns:** Safety monitoring and compliance status results.

### PortAccessControl

To secure port facilities by restricting access to authorized maritime personnel, preventing unauthorized entry to restricted areas.

**Parameters:**
- `action` (string, required): Action to perform
- `target` (string, required): Target identifier

**Returns:** Operation result.
