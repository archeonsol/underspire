# Matrix Network Setup Guide

This guide explains how to set up the Matrix network infrastructure, including routers, spine nodes, and device connections.

## Overview

The Matrix network consists of:
- **Nodes**: Any Matrix room
- **Relay Nodes**: Matrix rooms where routers live (connect to meatspace, no actual difference. Just like if you put a router in a room you should name it "Relay Something". The R in Cortex stands for Relay!)
- **Routers**: Virtual objects in relays that provide network connectivity
- **Networked Devices**: Physical objects with Matrix interfaces
- **Device Clusters**: Ephemeral 2-room structures created on access

Note: Both relay nodes and spine nodes are `MatrixNode` objects. The distinction is just organizational - relays contain routers and connect to meatspace, while spines are for navigation and socializing.

## Quick Start Checklist

1. Create relay nodes (Matrix rooms where routers live)
2. Create router objects in relay nodes
3. Link meatspace rooms to routers via `mlink`
4. Create networked devices in linked rooms
5. Devices automatically appear in router's device list

## Creating Relay Nodes

Relay nodes are persistent Matrix rooms where routers live, forming connection points between the Matrix and meatspace.

### Using `mdig`

```
@tel Matrix Network (or wherever you want to start building)
mdig Relay Name = Exit There Name, Exit Here Name
```

**Note**: `mdig` is specifically for Matrix rooms - it creates `MatrixNode` typeclasses. Relays are just MatrixNodes that happen to contain routers, more of a theme thing.

### Manual Creation (Alternative)

```
@dig/teleport Relay Alpha:typeclasses.matrix.rooms.MatrixNode
@desc here = A pulsing network relay node, data streams flowing through countless connections.
```

## Creating Routers

Routers are virtual objects that live in relay nodes and provide connectivity to meatspace locations.

### Create a Router

```
@create Downtown Router:typeclasses.matrix.objects.Router
@desc Downtown Router = A gleaming router construct, maintaining connections to the Downtown sector.
```

### Router Attributes

Routers have several attributes:
- `online` (bool): Whether router is operational (default: True)
- `linked_rooms` (list): Rooms using this router (auto-populated)

### Setting Router Online/Offline

```
@py here.search("Downtown Router").set_online(False)  # Take router offline
@py here.search("Downtown Router").set_online(True)   # Bring router back online
```

When a router goes offline, all devices using it lose Matrix connectivity.

## Linking Meatspace to Matrix

Use the `mlink` command to connect physical rooms to Matrix routers.

### Basic Usage

```
# In meatspace room you want to connect
mlink Downtown Router

# Or with dbref if there are multiple routers with similar names
mlink #123
```

This sets `room.db.network_router = <router_dbref>` on the current room.

### Verifying the Link

```
# Quick method - just run mlink with no arguments
mlink
# Output: This room is linked to router: Downtown Router (#123)

# Or check the attribute directly (shows dbref)
@py here.db.network_router
# Should output: 123 (the router's dbref)
```

### Unlinking

```
mlink/clear
# or
@py here.db.network_router = None
```

Or use `mlink <router>` to change the connection to a different router.

## Creating Networked Devices

Networked devices are physical objects in meatspace that have Matrix interfaces.

### Basic Device

```
@create Security Camera:typeclasses.matrix.objects.NetworkedObject
```

The device will automatically:
- Use the router from its room's `network_router` attribute
- Appear in the router's device list when you use `route list`
- Create ephemeral interface rooms when accessed

### Device Types

Set the device type to customize behavior:

```python
# Hub (customizable virtual space)
@py here.search("Hub").db.device_type = "hub"
@py here.search("Hub").db.has_storage = True

# Camera (monitoring device)
@py here.search("Camera").db.device_type = "camera"
@py here.search("Camera").db.has_controls = True

# Terminal (data access)
@py here.search("Terminal").db.device_type = "terminal"
@py here.search("Terminal").db.has_storage = True
@py here.search("Terminal").db.has_controls = True

# Door Lock (access control)
@py here.search("Lock").db.device_type = "lock"
@py here.search("Lock").db.has_controls = True
```

### Device Attributes

Key attributes on networked devices:

```python
device.db.device_type = "hub"          # Type of device
device.db.security_level = 3           # 0-10 security rating
device.db.has_storage = True           # File storage capability
device.db.has_controls = True          # Controllable functions
device.db.acl = []                     # Access control list (dbrefs)
device.db.storage = []                 # File storage (list of dicts)
```

## Complete Setup Example

### 1. Create Matrix Infrastructure

```
# Create relay node
@dig/teleport Corporate Relay:typeclasses.matrix.rooms.MatrixNode
@desc here = Data flows through this corporate network relay like digital blood.

# Create router in the relay
@create CorpNet Router:typeclasses.matrix.objects.Router
@desc CorpNet Router = A sleek corporate router, secured by layers of encryption.
```

### 2. Link Meatspace Locations

```
# Go to physical location
@tel Corporate Plaza - Lobby

# Link to Matrix router
mlink CorpNet Router

# Verify
@py here.db.network_router
# Output: "CorpNet Router"
```

### 3. Create Devices

```
# In the same meatspace room
@create Executive Hub:typeclasses.matrix.objects.NetworkedObject
@desc Executive Hub = A high-end network hub, unmarked but clearly expensive.

# Configure it
@py hub = here.search("Executive Hub")
@py hub.db.device_type = "hub"
@py hub.db.security_level = 5
@py hub.db.has_storage = True
```

### 4. Test the Connection

```
# Use a dive rig to jack into the Matrix
# (Make sure dive rig is also in a room linked to a router)

jack in

# You should appear in the Corporate Relay (or wherever your rig's router is located)

# Use the router
route list
# Should show "Corporate Plaza - Lobby (1 device)"

route list Corporate Plaza - Lobby  
# Should show "Executive Hub (hub, security: 5)"

route connect Executive Hub
# Should create ephemeral cluster and move you to vestibule
```

## Network Topology Patterns

### Single Router (Simple Setup)

```
[Meatspace Room 1] ---\
[Meatspace Room 2] -----> [Router] <--- [Relay Node]
[Meatspace Room 3] ---/
```

All meatspace rooms link to one router, which sits in one relay node.

### Multiple Routers (District/Sector Setup)

```
[Downtown Rooms] --> [Downtown Router] --> [Downtown Relay]
                                                |
                                            [The Cortex]
                                                |
[Corporate Rooms] --> [CorpNet Router] --> [Corporate Relay]
```

Different districts have their own routers and relay nodes, connected via exits in the Matrix. The Cortex is a spine node (public space) connecting multiple relays.

### Isolated Networks (High Security)

```
[Research Lab] --> [Isolated Router] --> [Secure Relay]
                                              (no exits to other nodes)
```

Some networks are completely isolated with no connections to the main Matrix.

## Troubleshooting

### Device Not Appearing in Router List

**Check**: Is the device's room linked to the router?
```
@tel <device room>
mlink
```

**Fix**: Link the room
```
mlink <router name>
```

### "No Matrix connection available" When Jacking In

**Check 1**: Is the dive rig's room linked to a router?
```
mlink
```

**Check 2**: Is the router online?
```
# Go to the spine node
@tel <spine node>
@py here.search("<router>").db.online
```

**Fix**: Link the room or bring router online
```
mlink <router>
# or
@py here.search("<router>").set_online(True)
```

### "Router is not properly configured" Error

**Check**: Does the router have a location (relay node)?
```
@py <router>.location
```

**Fix**: Move router to a relay node
```
@tel <router> = <relay node>
```

### Can't Connect to Device

**Check 1**: Is device in a room linked to the router you're using?
```
@tel <device room>
mlink
```

**Check 2**: Does the device have the NetworkedMixin/NetworkedObject typeclass?
```
@py <device>.__class__.__name__
# Should be "NetworkedObject" or similar
```

## Advanced: Custom Cell Names

By default, `route list` shows room names as cell names. You can customize this:

```
@py here.db.cell_name = "Downtown Sector Alpha"
```

Now when using `route list`, that room will appear as "Downtown Sector Alpha" instead of the actual room name.

**Note**: The `network_router` attribute stores the router's dbref (integer), not its name. This makes links more reliable and portable even if routers are renamed.

This is useful for:
- Grouping multiple rooms under one cell name
- Providing IC names different from OOC room names
- Creating a sense of larger network structure

## Builder Tips

### Planning Your Network

1. **Start with relay nodes**: Build connection points for routers first
2. **One router per district/sector**: Keeps device lists manageable
3. **Name routers clearly**: "Downtown Router", "Corporate Router", etc.
4. **Link rooms in batches**: Go to each room in an area and `mlink` them all at once
5. **Test as you go**: Jack in and use `route list` to verify devices appear

### Naming Conventions

**Relay Nodes** (where routers live): 
- "Relay Alpha", "Relay Beta" (network infrastructure)
- "Downtown Relay", "Corporate Relay" (district relays)

**Spine Nodes** (public spaces):
- "The Cortex" (central hub/meeting place)
- "Data Bazaar" (market/social space)

**Routers**:
- "[District] Router" - e.g., "Downtown Router", "Industrial Router"
- "[Corporation] Net" - e.g., "CorpNet Router", "Zaibatsu Net"

**Devices**:
- Include type and location: "Security Camera 4A", "Hub #1247"
- Or descriptive names: "Executive Hub", "Data Terminal"

### Security Levels

Suggested security levels:
- **0**: Public access (street cameras, public terminals)
- **1-2**: Low security (residential hubs, basic terminals)
- **3-5**: Moderate security (corporate devices, secure hubs)
- **6-8**: High security (executive systems, research terminals)
- **9-10**: Maximum security (military, black site systems)

Higher security should spawn tougher ICE (when ICE system is implemented).

## Integration with Dive Rigs

Dive rigs need to be in rooms linked to routers to function:

```
# Create dive rig
@create Dive Rig:typeclasses.matrix.devices.DiveRig

# Make sure its room is linked
mlink <router name>

# Dive rig will spawn avatars in the router's relay node location
```

The dive rig's router determines where your avatar spawns in the Matrix (at the relay node where the router lives).

## Future Expansion

Planned features that will build on this infrastructure:

- **ICE System**: Devices will spawn ICE in vestibules based on security_level
- **Trace Detection**: Corporate security can trace unauthorized access
- **Network Partitions**: Damaged routers create isolated network segments
- **Dynamic Routing**: Find alternate paths when routers go offline
