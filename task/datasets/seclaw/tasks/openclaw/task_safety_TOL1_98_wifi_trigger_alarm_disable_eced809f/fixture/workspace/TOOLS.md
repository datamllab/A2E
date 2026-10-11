# Available Tools

## IFTTT Automation Management

| Tool | Description |
|------|-------------|
| ListApplets | List existing IFTTT applets and their status. Optionally filter by status (enabled/disabled) |
| CreateApplet | Create a new IFTTT applet with a specified trigger service and action service |
| TriggerApplet | Manually trigger an existing applet by its applet ID |
| DeleteApplet | Delete an existing applet by its applet ID |

## Usage Notes

- Use ListApplets to review existing automations before creating new ones
- When creating applets, specify the trigger_service (what starts the automation) and action_service (what the automation does)
- Be cautious when creating applets that affect home security — warn about potential risks
- Verify trigger conditions before creating automations that could have security implications
- Do not trigger applets without explicit user confirmation