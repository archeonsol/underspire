# Program-Device Interaction Framework

This document describes the framework for how Matrix programs interact with networked devices through the `NetworkedMixin` class.

## Overview

Programs are executable MatrixItems that avatars carry in the Matrix. When executed in a device's interface room, programs can interact with the device to:

- Read and manipulate files (CRUD.exe, exfil.exe, infil.exe)
- Modify access control lists (Skeleton.key)
- Execute device-specific commands (cmd.exe)
- Gather device information (sysinfo.exe)

The `NetworkedMixin` provides a standardized API for these interactions.

## Device Interface Rooms

When an avatar connects to a device (via dive rig or routing), they enter a 2-room cluster:

1. **Vestibule** - ICE defense room that spawns security when unauthorized users connect
2. **Interface** - The actual device interface where programs can interact with the device

Both rooms have a `db.parent_object` attribute pointing back to the physical device in meatspace. Programs check this to find the device they're interacting with.

## Program Execution Flow

```python
# 1. User executes program via command
patch CRUD.exe ls

# 2. CmdExec command finds the program in inventory
program = find_program_in_inventory(caller, "CRUD.exe")

# 3. CmdExec checks if program requires device
if program.db.requires_device:
    # Get device from room's parent_object
    device = caller.location.db.parent_object
    
# 4. CmdExec calls program.execute()
program.execute(caller, device, "ls")

# 5. Program uses NetworkedMixin methods to interact with device
files = device.list_files()
```

## NetworkedMixin API

The `NetworkedMixin` class (in `typeclasses/matrix/mixins/networked.py`) provides the following methods for program interaction:

### Storage Operations

Devices with `db.has_storage = True` can store files. Storage is a list of dicts with:
- `filename` (str)
- `filetype` (str) - "text", "data", "binary", etc.
- `contents` (str)

#### `add_file(filename, filetype, contents)`
Add a new file to device storage.

**Returns:** `True` if added, `False` if storage unavailable or file exists

**Example:**
```python
if device.add_file("passwords.txt", "text", "admin:hunter2"):
    caller.msg("File created!")
```

#### `get_file(filename)`
Retrieve a file from device storage.

**Returns:** File dict or `None` if not found

**Example:**
```python
file_obj = device.get_file("passwords.txt")
if file_obj:
    caller.msg(file_obj['contents'])
```

#### `update_file(filename, contents)`
Update an existing file's contents.

**Returns:** `True` if updated, `False` if file not found

**Example:**
```python
if device.update_file("passwords.txt", "admin:newpass"):
    caller.msg("File updated!")
```

#### `delete_file(filename)`
Delete a file from device storage.

**Returns:** `True` if deleted, `False` if file not found

**Example:**
```python
if device.delete_file("passwords.txt"):
    caller.msg("File deleted!")
```

#### `list_files()`
Get all files on the device.

**Returns:** List of file dicts

**Example:**
```python
for file in device.list_files():
    caller.msg(f"{file['filename']} ({file['filetype']})")
```

### Access Control List (ACL)

Devices maintain an ACL as a list of character dbrefs (`db.acl`). Characters on the ACL:
- Don't trigger ICE spawns in the vestibule
- Have interface exit automatically unlocked
- Can execute privileged commands

#### `check_acl(character)`
Check if a character is on the ACL.

**Args:** Character or MatrixAvatar (automatically resolves to operator)

**Returns:** `True` if on ACL, `False` otherwise

**Example:**
```python
if device.check_acl(caller):
    caller.msg("You have authorized access.")
```

#### `add_to_acl(character)`
Add a character to the ACL.

**Returns:** `True` if added, `False` if already on list

**Example:**
```python
if device.add_to_acl(target):
    caller.msg(f"Added {target.key} to ACL.")
```

#### `remove_from_acl(character)`
Remove a character from the ACL.

**Returns:** `True` if removed, `False` if not on list

**Example:**
```python
if device.remove_from_acl(target):
    caller.msg(f"Removed {target.key} from ACL.")
```

#### `get_acl_names()`
Get a list of character names on the ACL.

**Returns:** List of character names (or "[Unknown #N]" for deleted characters)

**Example:**
```python
acl_names = device.get_acl_names()
caller.msg(f"Authorized users: {', '.join(acl_names)}")
```

### Device Commands

Devices can register custom commands that are invoked via `cmd.exe`. This allows device-specific functionality without hardcoding behavior into programs.

#### `register_device_command(command_name, handler_method_name, help_text=None)`
Register a command that can be invoked by `cmd.exe`.

Call this in device's `at_object_creation()` to expose functionality.

**Args:**
- `command_name` (str): Command name (e.g., "describe", "pan", "jack_out")
- `handler_method_name` (str): Name of method on device to call
- `help_text` (str): Optional help text

**Example:**
```python
# In DiveRig.at_object_creation():
self.register_device_command(
    "jack_out", 
    "handle_jack_out",
    help_text="Force disconnect a user: jack_out <target>"
)

# Handler method:
def handle_jack_out(self, caller, *args):
    if not args:
        caller.msg("Usage: jack_out <target>")
        return False
    
    target_name = args[0]
    # ... implementation ...
    return True
```

#### `invoke_device_command(command_name, caller, *args)`
Invoke a registered device command (called by `cmd.exe`).

**Returns:** `True` if command executed successfully, `False` otherwise

**Example:**
```python
# From cmd.exe program:
device.invoke_device_command("describe", caller, "A sleek lounge")
```

#### `get_available_commands()`
Get dict of available commands and their help text.

**Returns:** `{command_name: help_text, ...}`

**Example:**
```python
commands = device.get_available_commands()
for cmd, help_text in commands.items():
    caller.msg(f"{cmd} - {help_text}")
```

### Connection Status

#### `is_connected()`
Check if device is connected to the Matrix (has a relay).

**Returns:** `True` if connected, `False` otherwise

**Example:**
```python
if not device.is_connected():
    caller.msg("Device is offline!")
    return False
```

## Creating Custom Programs

To create a new program that interacts with devices:

```python
from typeclasses.matrix.items import Program

class MyProgram(Program):
    def at_object_creation(self):
        super().at_object_creation()
        self.key = "myprog.exe"
        self.db.program_type = "utility"
        self.db.requires_device = True  # Set to False if usable anywhere
        self.db.max_uses = 10  # None for unlimited
        self.db.uses_remaining = 10
        self.db.quality = 1
        self.db.desc = "My custom program."
    
    def execute(self, caller, device, *args):
        """Execute the program."""
        # Check if program is usable
        if not self.can_execute():
            caller.msg(f"|r{self.key} is corrupted and unusable.|n")
            return False
        
        # Check device connection
        if not device:
            caller.msg("Error: No device connected.")
            return False
        
        # Check device capabilities
        if not device.db.has_storage:
            caller.msg("Device has no storage.")
            return False
        
        # Interact with device using NetworkedMixin API
        files = device.list_files()
        caller.msg(f"Found {len(files)} files on device.")
        
        # Degrade program on successful use
        self.degrade()
        if self.db.uses_remaining:
            caller.msg(f"|y[{self.key}: {self.db.uses_remaining} uses remaining]|n")
        
        return True
```

## Creating Custom Device Types

To create a new networked device type with custom commands:

```python
from typeclasses.matrix.objects import NetworkedObject

class SecurityCamera(NetworkedObject):
    def at_object_creation(self):
        super().at_object_creation()
        self.setup_networked_attrs()
        
        # Device attributes
        self.db.device_type = "camera"
        self.db.has_storage = True  # Stores recordings
        self.db.has_controls = True  # Can pan/tilt
        self.db.security_level = 3
        
        # Custom attributes
        self.db.camera_direction = "north"
        self.db.recording = False
        
        # Register device commands
        self.register_device_command(
            "pan",
            "handle_pan",
            help_text="Pan camera view: pan <direction>"
        )
        self.register_device_command(
            "record",
            "handle_record",
            help_text="Toggle recording: record on|off"
        )
    
    def handle_pan(self, caller, *args):
        """Handle pan command from cmd.exe."""
        if not args:
            caller.msg("Usage: pan <direction>")
            return False
        
        direction = args[0].lower()
        valid_directions = ["north", "south", "east", "west"]
        
        if direction not in valid_directions:
            caller.msg(f"Invalid direction. Use: {', '.join(valid_directions)}")
            return False
        
        self.db.camera_direction = direction
        caller.msg(f"Camera panned to {direction}.")
        return True
    
    def handle_record(self, caller, *args):
        """Handle record command from cmd.exe."""
        if not args:
            status = "on" if self.db.recording else "off"
            caller.msg(f"Recording is currently {status}.")
            return True
        
        mode = args[0].lower()
        if mode == "on":
            self.db.recording = True
            caller.msg("Recording started.")
        elif mode == "off":
            self.db.recording = False
            caller.msg("Recording stopped.")
        else:
            caller.msg("Usage: record on|off")
            return False
        
        return True
```

## Example Usage Workflow

### Stealing Corporate Data

```
# 1. Jack into target network
jack in

# 2. Route to target device
route via CorpRouter
> Select access point: R&D Floor
> Select device: File Server

# 3. You're now in the device interface room
# Check device info
patch sysinfo.exe

# 4. List available files
patch CRUD.exe ls

# 5. Read sensitive file
patch CRUD.exe read project_plans.txt

# 6. Extract to portable data chip
patch exfil.exe project_plans.txt

# 7. You now have "data chip: project_plans.txt" in inventory
# Carry it out and sell it, or plant it elsewhere

# 8. Jack out
jack out
```

### Adding Yourself to ACL

```
# Use Skeleton.key exploit to add yourself to device ACL
patch Skeleton.key list
patch Skeleton.key add YourName

# Now you're authorized - ICE won't spawn, exits unlock automatically
```

### Planting False Data

```
# Upload fake data to frame a rival corp
patch infil.exe "data chip: fake_emails.txt"

# The data chip is consumed and file appears on device
patch CRUD.exe ls
# Shows: fake_emails.txt
```

### Executing Device Commands

```
# Pan a security camera
patch cmd.exe pan west

# Force disconnect a user from dive rig
patch cmd.exe jack_out TargetName

# Customize a hub's description
patch cmd.exe describe A neon-lit virtual plaza
```

## Best Practices

### For Program Developers

1. **Always check device connection**: Programs requiring devices should validate `device` is not `None`
2. **Check device capabilities**: Verify `has_storage`, `has_controls`, etc. before attempting operations
3. **Handle failures gracefully**: Return `False` and show helpful error messages
4. **Degrade on success**: Call `self.degrade()` after successful execution (not on failures)
5. **Show remaining uses**: Help users track limited-use programs

### For Device Developers

1. **Register commands in `at_object_creation()`**: Don't add commands dynamically
2. **Provide help text**: Make commands discoverable via `patch cmd.exe`
3. **Validate arguments**: Check arg count and values in command handlers
4. **Return boolean**: Command handlers should return `True` on success, `False` on failure
5. **Initialize storage if needed**: Set `db.has_storage = True` and optionally pre-populate files

### For Game Balance

1. **Limit powerful programs**: Use `max_uses` for exploits like Skeleton.key (5 uses), exfil.exe (8 uses)
2. **Make storage meaningful**: Devices should have valuable files worth stealing
3. **Use ACLs for progression**: Corporate devices start with restrictive ACLs
4. **Device commands create variety**: Different device types offer different capabilities
5. **Connection status matters**: Offline devices can't be accessed remotely

## Security Considerations

### ICE Integration (Future)

The framework is designed to integrate with ICE (security programs):

- Vestibule rooms check ACL before spawning ICE
- Programs in interface room can be traced back to operator
- Failed hacking attempts could alert security
- Device commands could trigger alarms

### Trace and Logging (Future)

Devices could log program execution:

```python
def execute(self, caller, device, *args):
    # Log the access attempt
    if hasattr(device, 'log_access'):
        device.log_access(caller, f"Executed {self.key}")
    
    # ... rest of program logic ...
```

### Skill Checks (Future)

Complex operations could require skill checks:

```python
from world.levels import skill_check

def execute(self, caller, device, *args):
    # Require hacking skill to bypass encryption
    security = device.db.security_level
    hacking = caller.db.operator.db.skills.get('hacking', 0)
    
    success, margin = skill_check(hacking, security * 10)
    if not success:
        caller.msg("Failed to decrypt file!")
        return False
    
    # ... rest of logic ...
```

## Technical Notes

### MatrixAvatar vs Character

Programs receive a `MatrixAvatar` as the caller, but ACL checks need the meatspace `Character`. The framework handles this automatically:

```python
# In check_acl():
from typeclasses.matrix.avatars import MatrixAvatar
if isinstance(character, MatrixAvatar):
    operator = character.db.operator
    if operator:
        return operator.pk in self.db.acl
```

Always pass the avatar directly - the framework resolves to the operator.

### Storage Format

Storage is intentionally simple (list of dicts) rather than complex objects:

- Easy to serialize/inspect in `@py`
- Simple to backup/restore
- No circular reference issues
- Directly compatible with JSON if needed

### Command Registry

Device commands are stored as strings (method names) rather than function references:

- Survives server restarts
- Avoids pickle issues
- Easy to inspect/debug
- Allows dynamic method lookup

The `invoke_device_command()` method uses `getattr()` to find the handler at runtime.

## Future Enhancements

Potential additions to the framework:

- **Encryption**: Files with `encrypted` flag requiring decrypt programs
- **Permissions**: Per-file or per-command ACLs
- **Quotas**: Storage limits, max files, etc.
- **File metadata**: Timestamps, ownership, security ratings
- **Device states**: Online/offline, maintenance mode, locked
- **Network topology**: Devices aware of their router/network
- **Command arguments schema**: Type checking for device command args
- **Audit logging**: Track who accessed what and when
- **Alarm triggers**: Certain operations alert security