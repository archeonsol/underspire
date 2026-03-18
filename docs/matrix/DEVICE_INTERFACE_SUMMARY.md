# Device Interface System Summary

## Overview

Networked devices can be interfaced with from **two contexts**:

1. **From Meatspace**: Using the `interface` command on physical devices
2. **From Matrix**: Using `patch cmd.exe` in a device's interface room

Both launch the **same EvMenu** that provides interactive device control.

## Architecture

### Device Commands as Menu Options

Instead of programs executing arbitrary code, devices register **menu-accessible commands** that appear as numbered options in the EvMenu interface.

```python
# In device's at_object_creation():
self.register_device_command(
    "describe",           # Command name
    "handle_describe",    # Handler method name on device
    help_text="Set hub description: describe <text>"
)
```

### The Flow

```
Meatspace:
  interface hub
    ↓
  EvMenu opens
    ↓
  Select command from menu
    ↓
  device.invoke_device_command() calls handler
    ↓
  Handler executes and returns to menu

Matrix:
  patch cmd.exe (in device interface room)
    ↓
  EvMenu opens (same menu)
    ↓
  Select command from menu
    ↓
  device.invoke_device_command() calls handler
    ↓
  Handler executes and returns to menu
```

## Usage Examples

### From Meatspace

```
> interface hub
=== Hub Device Interface ===

Device Type: hub
Security Level: 1
Storage: Yes
Controls: Yes

You are authorized on this device's ACL.

Available Commands:
  1. describe - Set hub description: describe <text>
  2. detail - Add examinable detail: detail <key> <description>
  3. remove_detail - Remove detail: remove_detail <key>
  4. list_details - List all custom details

f) Browse files
a) View ACL
q) Exit interface

>
```

### From Matrix

```
> patch cmd.exe

[Opens same menu as above]
```

## Menu Features

### Main Menu (device_main_menu)
- Shows device info (type, security level, capabilities)
- Shows ACL authorization status
- Lists all registered device commands as numbered options
- File browser (if device has storage)
- ACL viewer

### Command Execution
- Select numbered command
- Prompted for arguments
- Command executes via `device.invoke_device_command()`
- Returns to main menu

### File Browser
- List all files on device storage
- Read individual files
- (Programs like CRUD.exe, exfil.exe, infil.exe handle file manipulation)

### ACL Viewer
- Shows authorized users
- (Skeleton.key program handles ACL manipulation)

## Implementation Details

### Device Menu Module
**File**: `typeclasses/matrix/device_menu.py`

**Key Functions**:
- `start_device_menu(caller, device, from_matrix)` - Entry point
- `device_main_menu()` - Main menu node
- `_execute_command()` - Prompt for command args
- `_process_command()` - Execute command via device framework
- `_browse_files()` - File listing
- `_read_file()` - File viewing
- `_view_acl()` - ACL display

### cmd.exe Program
**File**: `typeclasses/matrix/programs/utility.py`

Launches the device menu when executed:
```python
def execute(self, caller, device, *args):
    if not device:
        caller.msg("Error: No device connected.")
        return False
    
    from typeclasses.matrix.device_menu import start_device_menu
    start_device_menu(caller, device, from_matrix=True)
    return True
```

### interface Command
**File**: `commands/base_cmds.py`

Launches the device menu from meatspace:
```python
def func(self):
    device = caller.search(self.args.strip())
    # ... validation ...
    
    from typeclasses.matrix.device_menu import start_device_menu
    start_device_menu(caller, device, from_matrix=False)
```

## Device Command Registration

Devices register commands in `at_object_creation()`:

```python
class Hub(NetworkedObject):
    def at_object_creation(self):
        super().at_object_creation()
        self.setup_networked_attrs()
        
        # Device properties
        self.db.device_type = "hub"
        self.db.has_storage = True
        self.db.has_controls = True
        
        # Register commands
        self.register_device_command(
            "describe",
            "handle_describe",
            help_text="Set hub description: describe <text>"
        )
    
    def handle_describe(self, caller, *args):
        """Handler for 'describe' command."""
        if not args:
            caller.msg("Current description: " + self.db.hub_desc)
            return True
        
        new_desc = ' '.join(args)
        self.db.hub_desc = new_desc
        caller.msg(f"Description updated to: {new_desc}")
        return True
```

## Why This Design?

### Unified Interface
- Same menu from meatspace OR Matrix
- Consistent UX regardless of access method
- No need to learn different command syntaxes

### Controlled Access
- Devices explicitly register what commands they expose
- Handler methods provide type safety
- Easy to add ACL checks in handlers

### Extensibility
- New device types just register their commands
- Programs can still do specialized tasks (CRUD, exfil, Skeleton.key)
- Menu can be extended with more features (write files, manage ACL)

### Separation of Concerns
- **Programs** - Specialized exploits/utilities (exfil, Skeleton.key, CRUD)
- **Device Commands** - Standard device control (describe, pan, configure)
- **Menu** - Navigation and interaction layer

## Program vs Device Command

### Use Programs When:
- Exploiting/hacking (Skeleton.key, exfil.exe)
- Limited-use operations (CRUD.exe degrades)
- Illegal activities (exfil.exe is contraband)
- Cross-device functionality (sysinfo.exe works anywhere)
- Combat/ICE interaction (ICEpick.exe)

### Use Device Commands When:
- Legitimate device control
- Configuration/customization
- Device-specific functionality
- Unlimited-use operations
- Owner/authorized user actions

## Future Enhancements

### Menu Additions
- **Write files** - Direct file creation from menu (no CRUD.exe needed if authorized)
- **ACL management** - Add/remove users from menu (no Skeleton.key needed if authorized)
- **Device status** - Power on/off, reboot, diagnostics
- **Network info** - Show connected router, network topology

### Skill Checks
- Complex commands could require skill checks
- Failed attempts alert security
- Better hacking = more menu options available

### Context-Aware Menus
- Different menu options based on:
  - Caller's ACL status
  - Device security level
  - Whether accessed from Matrix or meatspace
  - Character's hacking skill

### Dynamic Commands
- Devices could register/unregister commands at runtime
- Temporary admin access
- Maintenance modes

## Example: Camera Device

```python
class SecurityCamera(NetworkedObject):
    def at_object_creation(self):
        super().at_object_creation()
        self.setup_networked_attrs()
        
        self.db.device_type = "camera"
        self.db.has_storage = True  # Stores recordings
        self.db.has_controls = True
        self.db.camera_direction = "north"
        
        # Register camera-specific commands
        self.register_device_command(
            "pan",
            "handle_pan",
            help_text="Pan camera: pan <direction>"
        )
        self.register_device_command(
            "status",
            "handle_status",
            help_text="Show camera status"
        )
    
    def handle_pan(self, caller, *args):
        if not args:
            caller.msg(f"Camera facing: {self.db.camera_direction}")
            return True
        
        direction = args[0].lower()
        if direction not in ["north", "south", "east", "west"]:
            caller.msg("Invalid direction.")
            return False
        
        self.db.camera_direction = direction
        caller.msg(f"Camera panned to {direction}.")
        return True
    
    def handle_status(self, caller, *args):
        caller.msg(f"Camera Status:")
        caller.msg(f"  Direction: {self.db.camera_direction}")
        caller.msg(f"  Recordings: {len(self.list_files())} files")
        return True
```

Usage:
```
> interface camera
[Menu opens]
> 1  (select "pan")
> north
Camera panned to north.
[Press key to return]
```

Or from Matrix:
```
> patch cmd.exe
[Same menu]
```
