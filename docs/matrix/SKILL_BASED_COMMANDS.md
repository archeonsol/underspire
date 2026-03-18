# Skill-Based Command Visibility

Device commands can be hidden behind skill checks, revealing more options to skilled hackers and technicians.

## How It Works

When you register a device command, you can specify:

- **visibility_threshold** (0-150): Minimum skill to see the command in menus
- **matrix_only**: Only accessible from Matrix (not physical access)
- **physical_only**: Only accessible from physical access (not Matrix)
- **requires_acl**: Requires authorization on device's ACL

The system checks different skills depending on access method:
- **Matrix access**: Uses caller's `hacking` skill
- **Physical access**: Uses caller's `technology` skill

## Examples

### Basic Hub (Everyone Can See)

```python
self.register_device_command(
    "status",
    "handle_status",
    help_text="Show hub status",
    visibility_threshold=0  # Everyone sees this
)
```

### Intermediate Command (Requires Some Skill)

```python
self.register_device_command(
    "diagnose",
    "handle_diagnose",
    help_text="Run diagnostic scan",
    visibility_threshold=50,  # Need 50+ skill to see
    requires_acl=True  # And need authorization to use
)
```

### Advanced Exploit (Master Hackers Only)

```python
self.register_device_command(
    "dump_memory",
    "handle_dump_memory",
    help_text="[EXPLOIT] Extract device memory",
    matrix_only=True,  # Only from Matrix
    visibility_threshold=100,  # Need 100+ hacking to see
    requires_acl=False  # Exploit - bypasses ACL
)
```

### Physical-Only Emergency Command

```python
self.register_device_command(
    "factory_reset",
    "handle_factory_reset",
    help_text="Reset device to factory defaults",
    physical_only=True,  # Must have physical access
    requires_acl=True,  # And be authorized
    visibility_threshold=25  # Need basic tech skill
)
```

## Progression Example: Corporate File Server

A corporate file server might have commands at different skill tiers:

### Skill 0 (Everyone)
```python
self.register_device_command(
    "status",
    "handle_status",
    help_text="Show server status"
)
```

**Menu shows:**
```
Available Commands:
  1. status - Show server status
```

### Skill 50 (Competent Hacker)
```python
self.register_device_command(
    "list_processes",
    "handle_list_processes",
    help_text="List running processes",
    matrix_only=True,
    visibility_threshold=50
)
```

**Menu shows:**
```
Available Commands:
  1. status - Show server status
  2. list_processes - List running processes
```

### Skill 75 (Professional)
```python
self.register_device_command(
    "dump_logs",
    "handle_dump_logs",
    help_text="Extract security logs",
    matrix_only=True,
    visibility_threshold=75
)
```

**Menu shows:**
```
Available Commands:
  1. status - Show server status
  2. list_processes - List running processes
  3. dump_logs - Extract security logs
```

### Skill 100 (Expert)
```python
self.register_device_command(
    "inject_backdoor",
    "handle_inject_backdoor",
    help_text="[EXPLOIT] Plant persistent backdoor",
    matrix_only=True,
    visibility_threshold=100,
    requires_acl=False  # Bypass security
)
```

**Menu shows:**
```
Available Commands:
  1. status - Show server status
  2. list_processes - List running processes
  3. dump_logs - Extract security logs
  4. inject_backdoor - [EXPLOIT] Plant persistent backdoor
```

### Skill 125 (Master)
```python
self.register_device_command(
    "ghost_mode",
    "handle_ghost_mode",
    help_text="[HIDDEN] Enable invisible monitoring",
    matrix_only=True,
    visibility_threshold=125
)
```

**Menu shows:**
```
Available Commands:
  1. status - Show server status
  2. list_processes - List running processes
  3. dump_logs - Extract security logs
  4. inject_backdoor - [EXPLOIT] Plant persistent backdoor
  5. ghost_mode - [HIDDEN] Enable invisible monitoring
```

## Usage Scenarios

### From Meatspace (Low Tech Skill)
```
> op file_server
[Technology skill: 20]

=== File Server Interface ===
Device Type: file_server
Security Level: 5
...

Available Commands:
  1. status - Show server status

[Only sees basic command]
```

### From Matrix (Medium Hacking Skill)
```
> patch cmd.exe
[Hacking skill: 60]

=== File Server Interface ===
...

Available Commands:
  1. status - Show server status
  2. list_processes - List running processes

[Sees intermediate commands]
```

### From Matrix (Master Hacker)
```
> patch cmd.exe
[Hacking skill: 125]

=== File Server Interface ===
...

Available Commands:
  1. status - Show server status
  2. list_processes - List running processes
  3. dump_logs - Extract security logs
  4. inject_backdoor - [EXPLOIT] Plant persistent backdoor
  5. ghost_mode - [HIDDEN] Enable invisible monitoring

[Sees everything!]
```

## Game Balance Considerations

### Discovery & Progression
- Players discover more options as they level up
- Creates "aha!" moments when new commands appear
- Encourages skill investment

### Security Tiers
- **Public devices** (0-25): Basic info, status checks
- **Commercial** (25-50): Configuration, logs
- **Corporate** (50-75): Exploits, data extraction
- **Military/Black** (75-100+): Advanced exploits, backdoors

### Physical vs Matrix
```python
# Physical access is easier but limited
self.register_device_command(
    "reboot",
    "handle_reboot",
    physical_only=True,
    visibility_threshold=10  # Low skill needed physically
)

# Matrix access requires more skill but more options
self.register_device_command(
    "remote_reboot",
    "handle_remote_reboot",
    matrix_only=True,
    visibility_threshold=40  # Higher skill for remote
)
```

### ACL Bypass via Skill
```python
# Legitimate command - requires ACL
self.register_device_command(
    "admin_panel",
    "handle_admin_panel",
    requires_acl=True,
    visibility_threshold=0
)

# Exploit version - bypasses ACL but needs skill
self.register_device_command(
    "crack_admin",
    "handle_crack_admin",
    requires_acl=False,  # Exploit!
    visibility_threshold=90  # But hard to find
)
```

## Implementation Tips

### Graduated Access
Start with low thresholds, increase for powerful commands:
- 0-25: Information gathering
- 25-50: Basic manipulation
- 50-75: Data extraction
- 75-100: System exploits
- 100+: Advanced/dangerous operations

### Hidden Alternatives
Provide both legitimate and exploit paths:
```python
# Legitimate - requires auth
self.register_device_command("configure", "handle_configure",
    requires_acl=True, visibility_threshold=0)

# Exploit - no auth but high skill
self.register_device_command("force_config", "handle_force_config",
    requires_acl=False, visibility_threshold=80)
```

### Skill Flavor Text
Use help text to hint at skill requirements:
```python
self.register_device_command(
    "advanced_diagnostics",
    "handle_advanced_diagnostics",
    help_text="[ADVANCED] Deep system diagnostics",
    visibility_threshold=60
)
```

### Matrix/Physical Asymmetry
Physical access can be easier but less powerful:
```python
# Easy physical access
self.register_device_command("power_cycle", "handle_power_cycle",
    physical_only=True, visibility_threshold=5)

# Hard but powerful remote access
self.register_device_command("remote_shutdown", "handle_remote_shutdown",
    matrix_only=True, visibility_threshold=70)
```

## Future Possibilities

- Dynamic thresholds based on device security level
- Commands that appear after certain story events
- Temporary skill boosts from programs/drugs
- Team bonuses (someone else's skill unlocks commands)
- Failed access attempts triggering alerts
- "Discovered" commands saved to character knowledge