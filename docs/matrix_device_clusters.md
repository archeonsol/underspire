# Matrix Device Clusters

Device clusters are ephemeral 2-room structures created when accessing networked devices through the Matrix. They provide a standardized interface for device interaction with security (ICE) and functionality separated into distinct virtual spaces.

## Overview

Every networked device in the Matrix creates an ephemeral cluster consisting of:

1. **Checkpoint** - Entry point with ICE security
2. **Interface** - Functional space for device interaction

These rooms are created on-demand when first accessed and automatically cleaned up when empty.

## Cluster Structure

```
[Router/Spine Node]
        ↓ (route connect <device>)
[Checkpoint] ← Entry point, ICE spawns here
        ↓ (exit: "interface" - locked by ICE/ACL)
[Interface] ← Programs work here, device functions accessible
        ↓ (exit: "back" - returns to checkpoint)
[Checkpoint]
        ↓ (jack out or die)
[Back to meatspace/router]
```

## Room Types

### Checkpoint (ICE Room)

**Purpose:** Security checkpoint before accessing device functions

**Characteristics:**
- First room you enter when routing to a device
- ICE spawns here if you're not on device ACL (future implementation)
- Exit to interface is locked until ICE defeated or you're on ACL
- Ephemeral - deleted when cluster is cleaned up
- Items cannot be dropped here

**Attributes:**
```python
checkpoint.db.parent_object = device  # Reference to physical device
checkpoint.db.is_checkpoint = True
checkpoint.db.ephemeral = True
checkpoint.db.node_type = "device_checkpoint"
```

### Interface Room

**Purpose:** Functional space for interacting with device capabilities

**Characteristics:**
- Access device storage, controls, and commands
- Programs (exec, CRUD, etc.) work here
- Description varies by device type
- Ephemeral - deleted when cluster is cleaned up
- Items cannot be dropped here

**Device-Specific Behavior:**

**Hub Devices:**
- Customizable description via `patch cmd.exe describe <text>`
- Description saved to `device.db.hub_desc`
- Details saved to `device.db.hub_details`
- Acts as virtual apartment/hangout space
- Changes persist across cluster recreations

**Other Devices (cameras, terminals, locks):**
- Fixed description (default or builder-customized)
- Access via `patch cmd.exe <command> [args]`
- Storage access via CRUD.exe
- Template-based, not customizable by users

**Attributes:**
```python
interface.db.parent_object = device  # Reference to physical device
interface.db.is_interface = True
interface.db.ephemeral = True
interface.db.node_type = "device_interface"
```

## Navigation

### Routing to Devices

Use the `route` command from any spine node with a Router:

```
route                      # Show router status and usage
route list                 # List all connected cells (locations)
route list Downtown Alpha  # List devices in specific cell
route connect Hub #1247    # Connect to device checkpoint
```

### Within Clusters

Once in a cluster:
- `interface` - Exit from checkpoint to interface (if ICE defeated/on ACL)
- `back` or `checkpoint` - Return to checkpoint from interface
- `jack out` - Disconnect from Matrix

## Lifecycle

### Creation

Clusters are created lazily on first access:

1. User executes `route connect <device>` from router
2. System calls `device.get_or_create_cluster()`
3. If cluster exists and valid, return existing rooms
4. If not, create new checkpoint and interface rooms
5. Store references: `device.db.checkpoint_node`, `device.db.interface_node`
6. User is moved to checkpoint

### Persistence

**While Active:**
- Cluster exists as long as ANY avatar is in checkpoint OR interface
- Multiple users can access the same cluster simultaneously
- Rooms remain loaded in memory

**When Empty:**
- Cleanup script periodically checks ephemeral rooms
- If BOTH checkpoint AND interface are empty → delete cluster
- Device references (`checkpoint_node`, `interface_node`) are cleared
- Next access will create a fresh cluster

**Data Persistence:**
Even though rooms are ephemeral, device state persists:
- Hub descriptions/details saved to device
- Device storage (files) saved to device
- ACL saved to device
- When cluster is recreated, it restores from device state

### Cleanup

Automatic cleanup happens via periodic script (future implementation):

```python
# Pseudocode for cleanup script
for each ephemeral room:
    if room.db.is_checkpoint:
        interface = get matching interface room
        if no avatars in checkpoint AND no avatars in interface:
            delete checkpoint
            delete interface
            clear device.db.checkpoint_node
            clear device.db.interface_node
```

## Item Handling

### Drop Prevention

Items cannot be dropped in ephemeral device nodes:

```
> drop CRUD.exe
You cannot drop items in ephemeral device nodes.
Use programs like infil.exe to save data to device storage.
```

**Rationale:**
- Prevents accidental loss of valuable programs
- Dropped items would be deleted when cluster is cleaned up
- Forces intentional data storage via infil.exe

**Allowed:**
- Avatars can enter/move through rooms
- Items can be carried in inventory
- Programs can be executed normally

**Blocked:**
- Dropping items from inventory
- Placing items on the ground
- Any transfer of items to room contents

## Device Storage vs Inventory

Understanding where data lives:

**Device Storage** (`device.db.storage`):
- Files accessible via CRUD.exe
- Persists when cluster is deleted
- Shared across all users accessing the device
- Limited by device capabilities

**Avatar Inventory**:
- Programs and data chips you carry
- Moves with you between locations
- Private to your avatar
- Can be lost if you die in Matrix

**Workflow:**
1. Access device interface
2. Use CRUD.exe to view files in device storage
3. Use exfil.exe to extract file → creates data chip in inventory
4. Carry data chip to another device
5. Use infil.exe to upload data chip → writes to device storage

## Implementation Details

### Device Attributes

Devices track cluster state:

```python
device.db.checkpoint_node = checkpoint_dbref  # or None when cleaned up
device.db.interface_node = interface_dbref  # or None when cleaned up
device.db.device_type = "hub"  # or "camera", "terminal", etc.
device.db.security_level = 3  # 0-10
device.db.has_storage = True  # File storage capability
device.db.has_controls = True  # Controllable functions
device.db.acl = [char_dbref1, char_dbref2]  # Access control list

# Hub-specific
device.db.hub_desc = "A sleek virtual lounge..."
device.db.hub_details = {"bar": "A holographic bar...", ...}

# Storage
device.db.storage = [
    {"filename": "data.txt", "filetype": "text", "contents": "..."},
    ...
]
```

### Creating Clusters

Method on NetworkedMixin:

```python
cluster = device.get_or_create_cluster()
# Returns: {'checkpoint': MatrixNode, 'interface': MatrixNode}

checkpoint = cluster['checkpoint']
interface = cluster['interface']
```

### Room Creation Flow

1. Check if `device.db.checkpoint_node` and `interface_node` exist
2. Try to load existing rooms by dbref
3. If both valid, return existing cluster
4. If invalid/missing, delete any partial cluster
5. Create new checkpoint with standard description
6. Create new interface with device-type-specific description
7. For hubs, restore `hub_desc` and `hub_details` from device
8. Create exits: checkpoint → interface, interface → checkpoint
9. Store dbrefs on device
10. Return cluster dict

## Future Enhancements

### ICE System
- Spawn ICE in checkpoint based on device security level
- Lock interface exit until ICE defeated
- Check ACL to bypass ICE for authorized users

### Advanced Security
- Trace detection on unauthorized access
- Alert systems that notify device owner
- Temporary lockouts after failed access attempts
- Corporate security response escalation

### Multiple Rooms
- Some devices might have more complex structures
- Corporate servers with multiple data vaults
- Research facilities with multiple terminals
- Still ephemeral, just more rooms in cluster

### Customization
- Builder-defined checkpoint descriptions per device
- Custom ICE configurations
- Special room types for unique devices
- Event triggers on access/exit

### Optimization
- Cache linked_rooms on Router for faster lookups
- Index devices by router for efficient queries
- Preload frequently-accessed clusters
- Smarter cleanup timing based on activity patterns