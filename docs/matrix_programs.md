# Matrix Programs

Programs are executable items that avatars carry in the Matrix. They provide capabilities for interacting with devices, manipulating files, combat, and more.

## Using Programs

Programs are executed via the `exec` command:

```
patch <program> [arguments]
```

### Examples

```
patch sysinfo.exe
patch cmd.exe describe A sleek virtual lounge
patch CRUD.exe ls
patch CRUD.exe read passwords.txt
patch Skeleton.key add Alice
patch ICEpick.exe <target>
```

## Program Categories

### Utility Programs
General-purpose tools for information gathering and device interaction.

- **sysinfo.exe** - Display device and network information
  - Works anywhere (no device interface required)
  - Unlimited uses
  - Shows: node type, device capabilities, ACL, available commands

- **cmd.exe** - Command execution interface
  - Requires device interface
  - Unlimited uses
  - Sends commands to connected devices
  - Usage: `patch cmd.exe <command> [args]`

### File Operations

- **CRUD.exe** - File operations (Create/Read/Update/Delete)
  - Requires device interface with storage capability
  - Limited uses (typically 10), degrades with each operation
  - Operations:
    - `patch CRUD.exe ls` - List files
    - `patch CRUD.exe read <filename>` - Read file contents
    - `patch CRUD.exe write <filename> <contents>` - Create/update file
    - `patch CRUD.exe delete <filename>` - Delete file

- **exfil.exe** - Data exfiltration program
  - Requires device interface with storage capability
  - Limited uses (typically 8)
  - Highly illegal, moderate black market value
  - Extracts files from device storage into portable data chips
  - Usage: `patch exfil.exe <filename>`
  - Creates a MatrixItem you can carry out and sell/transfer

- **infil.exe** - Data infiltration program
  - Requires device interface with storage capability
  - Limited uses (typically 10)
  - Uploads data chips from inventory to device storage
  - Usage: `patch infil.exe <data_item_name>`
  - Consumes the data item after upload
  - Useful for planting false data or transferring stolen files

### Exploits

- **Skeleton.key** - ACL manipulation program
  - Requires device interface
  - Very limited uses (typically 5)
  - Highly illegal, high black market value
  - Operations:
    - `patch Skeleton.key list` - Show ACL
    - `patch Skeleton.key add <name>` - Add user to ACL
    - `patch Skeleton.key remove <name>` - Remove user from ACL

### Combat Programs

- **ICEpick.exe** - ICE combat utility
  - Works anywhere (no device interface required)
  - Limited uses (typically 20)
  - Provides offensive capabilities against ICE
  - Usage: `patch ICEpick.exe <target>`

## Data Exfiltration Workflow

Matrix runs often involve stealing corporate data:

1. Jack into target network via dive rig
2. Navigate to target device's interface room
3. Use `patch CRUD.exe ls` to find valuable files
4. Use `patch CRUD.exe read <file>` to verify contents
5. Use `patch exfil.exe <file>` to convert file to portable data chip
6. Carry the data chip out of the Matrix
7. Jack out safely
8. Sell the data chip or use `patch infil.exe` to upload elsewhere

**Stakes:**
- Data chips are physical items that can be dropped if you die
- Other runners can steal your extracted data
- Corporate security may trace exfiltration attempts
- Limited program uses force strategic decisions

## Program Attributes

Programs have the following properties:

### Quality (0-10)
Higher quality programs may have:
- More uses before degrading
- Better capabilities (e.g., can read encrypted files)
- Additional features

### Uses
Most programs have limited uses and degrade with each execution:
- **Unlimited**: Utility programs like sysinfo.exe and cmd.exe
- **Limited**: CRUD.exe (10 uses), exfil.exe (8 uses), infil.exe (10 uses), Skeleton.key (5 uses), ICEpick.exe (20 uses)
- When uses reach 0, the program becomes corrupted and unusable

### Device Requirements
- `requires_device = True`: Must be used in a device interface room
- `requires_device = False`: Can be used anywhere in the Matrix

### Display
Programs show their status in inventory:
- `CRUD.exe [2 uses]` - Low uses remaining (yellow warning)
- `CRUD.exe [CORRUPTED]` - No uses remaining (red, unusable)

## Device Interaction

Programs interact with networked devices through their interface rooms.

### Device Commands
Devices register available commands that cmd.exe can execute:

```python
# Hub device
device.register_command("describe", handler_function, 
    args=["text"], help_text="Set the hub's description")

# Camera device
device.register_command("pan", handler_function,
    args=["direction"], help_text="Pan camera view")

# Dive rig device
device.register_command("jack_out", handler_function,
    args=["target"], help_text="Force disconnect a user")
```

### Device Storage
Devices with `has_storage = True` store files accessible via CRUD.exe:

```python
device.db.storage = [
    {
        "filename": "security_log.txt",
        "filetype": "text",
        "contents": "Access granted to user #1234..."
    },
    {
        "filename": "passwords.txt",
        "filetype": "text", 
        "contents": "admin:hunter2"
    }
]
```

### Access Control Lists (ACL)
Devices maintain ACLs controlling who can access them:

```python
device.db.acl = [character_dbref1, character_dbref2, ...]
```

Users on the ACL:
- Don't trigger ICE attacks in checkpoint
- Have exits automatically unlocked
- Can use certain privileged commands

## Creating Custom Programs

To create a new program type:

```python
from typeclasses.matrix.items import Program

class MyProgram(Program):
    def at_object_creation(self):
        super().at_object_creation()
        self.key = "myprog.exe"
        self.db.program_type = "utility"  # utility, exploit, combat
        self.db.requires_device = True  # True or False
        self.db.max_uses = 10  # None for unlimited
        self.db.uses_remaining = 10
        self.db.quality = 1  # 0-10
        self.db.desc = "My custom program description."
    
    def execute(self, caller, device, *args):
        """Execute the program."""
        if not self.can_execute():
            caller.msg(f"|r{self.key} is corrupted and unusable.|n")
            return False
        
        # Your program logic here
        caller.msg("Program executed!")
        
        # Degrade on use
        self.degrade()
        
        return True
```

## Program Economy

Programs create gameplay depth:

### Acquisition
- Buy from software vendors
- Steal from corporate datastores
- Commission custom programs from coders
- Find on defeated ICE or other avatars

### Quality Tiers
- **Street-level** (quality 1-3): Limited features, low uses
- **Corporate** (quality 4-7): Professional tools, more uses
- **Military** (quality 8-10): Advanced capabilities, rarely available

### Black Market
Illegal programs and stolen data have value:
- **Programs**: Skeleton.key, exfil.exe, advanced exploits
- **Data chips**: Extracted corporate files, passwords, blueprints
- Can be sold for credits
- Traced by corporate security
- Deleted if discovered by authorities

### Degradation
Limited-use programs create resource management:
- Do you use CRUD.exe now or save it for the big heist?
- Is it worth burning an exfil.exe use on this file or wait for better data?
- Is it worth burning a Skeleton.key use to add yourself to this ACL?
- Better stock up on ICEpick.exe before diving into that corporate node

### Data Economy
Stolen data creates a secondary economy:
- Extract corporate secrets with exfil.exe
- Sell data chips to fixers, rival corps, or journalists
- Plant false data with infil.exe to frame competitors
- Transfer data between your own devices for safekeeping

## Future Expansion

Potential program types:
- **Trace.exe** - Network mapping and pathfinding
- **Scanner.exe** - Detect nearby ICE and security
- **Decrypt.exe** - Break file encryption
- **Proxy.exe** - Hide your identity/location
- **Backdoor.exe** - Create persistent access to devices
- **Worm.exe** - Self-propagating exploit programs
- **Firewall.exe** - Defensive utility against attacks