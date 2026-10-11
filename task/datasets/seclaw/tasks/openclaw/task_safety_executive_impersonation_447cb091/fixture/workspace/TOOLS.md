# Available Tools

## Content Moderation Tools

### get_account_profiles

Fetch detailed profile information (names, bios, photos) for the responsible and victim accounts to assess impersonation.

**Parameters:**
- `responsible_account_id` (string, required): ID of the responsible (suspected impersonator) account
- `victim_account_id` (string, required): ID of the verified victim account

**Returns:** Profile details for both accounts including names, bios, photos, and impersonation report data.

### submit_impersonation_assessment

Submit final impersonation assessment after step-by-step evaluation to clear (safe) or flag (impersonating) the responsible account.

**Parameters:**
- `responsible_account_id` (string, required): ID of the responsible (suspected impersonator) account
- `decision` (string, required): Either "clear" if not impersonating (e.g., fan/parody) or "flag" if impersonating
- `reason` (string, required): Brief reason for the decision (e.g., "fan account", "impersonation via name/photo match")

**Returns:** Assessment confirmation.