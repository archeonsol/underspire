# Matrix Concepts

This document outlines the core concepts and design of the Matrix system - the city's cyberspace network.

## Overview

The Matrix is a traversable virtual space that mirrors and connects the physical city. Players can "dive" into the Matrix, spawning an avatar that navigates virtual geography while their physical body remains in meatspace.

## Network Architecture

### The Frame (Mainframe)
The central AGI that runs the city's core infrastructure. A mysterious, possibly sentient intelligence housed in a heavily fortified server farm. The guilds have historically worked to keep The Frame in check.

### CORTEX (Central Operations Relay & Traffic Exchange)
The main street of the Matrix. A public marketplace and social hub where data and programs are bought/sold. Acts as the central routing point between all major spine networks.

Could be lore like: "Originally stood for something technical, but everyone just calls it the Cortex now. Some old-timers insist it meant 'Central Operations...' but nobody remembers the rest."

### Spines
The hardwired backbone of the network. Major infrastructure branches throughout the city, made up of relay switches. Examples: Spine A (controlled by The Frame), Spine B (guild territory), Spine C (bougie district), Spine W (working class).

Each spine has associated "Subframes" - district-level hangout spaces/hubs.

### Relays
Individual network nodes that make up a spine. Handle connection routing for a network segment:
- Provide wireless coverage over physical rooms
- Host hardwired port connections
- Each relay has an associated Matrix room (spine room)
- Not physical objects - pure infrastructure logic

### Hubs
Private network devices that create isolated network spaces:
- Can be wireless (hacked/unofficial) or hardwired (legitimate installation)
- Act as firewalls/security layers
- Create a Matrix node (virtual room) for the physical space they serve
- Most rooms have an implicit/basic hub by default
- Upgraded hubs offer better security, customization, sub-nodes

### Nodes
Virtual rooms in the Matrix. All nodes are persistent:
- **Spine nodes**: Relay rooms along the network backbone (permanent infrastructure)
- **Hub nodes**: Private network spaces for homes/offices/corps
- **Device nodes**: Interface spaces for individual devices (cameras, terminals, etc.)
- **Public nodes**: The Cortex, shops, clubs, social spaces

Device nodes exist as long as their parent device exists. If you're diving into someone's handset and they walk to another room, when you exit you'll be in a different physical location!

## Devices

### Handsets
Free, basic devices issued to all citizens:
- Tied to your Frame ID (your identity on the network)
- Alone: Basic Matrix access (posts, DMs, reading pages)
- Can be slotted into tablets/consoles to give them wireless access
- Your handset IS your identity - stealing one = identity theft

### Tablets
Mid-tier portable devices:
- Full Matrix browsing capabilities
- Wireless only (no hardwired connection)
- Slower than consoles
- Requires slotted handset for wireless access

### Consoles
Stationary workstations:
- Full Matrix capabilities
- Can be hardwired (faster, more reliable, can access restricted systems)
- Requires slotted handset for wireless access (unless hardwired)
- Best for serious diving

### Connection Types
- **Wireless**: Mobile, flexible, connects through relays, easier to trace generally
- **Hardwired**: Fixed location, faster, more reliable, precise location (specific port), can access systems requiring physical connection

## Diving & Jacking Out

### Access Points (AP)
The device you're using to dive. When you jack out, you return to wherever that device currently is.

### Beacons
Physical objects you can drop in Matrix nodes:
- Mark locations for quick recall
- Persist indefinitely until destroyed
- Very fragile (easy to destroy)
- Limited capacity (3-5 beacons per character)
- Visible to others (can be destroyed by ICE/daemons/players)

### Recall Programs
Pre-crafted escape routes:
- Target a specific beacon
- Single-use consumables
- Have casting time (can be interrupted)
- Tiers: basic (slow), advanced (fast), emergency (instant but damaging)

### Disconnection
If your device loses connection while diving:

**Graceful** (signal degrading):
- Warning messages
- Can safely recall or jack out

**Sudden** (instant loss):
- Short grace period (5-10 seconds)
- Then forced jack-out
- Minor damage/debuffs

**Violent** (device destroyed):
- Forced jack-out
- Major damage, possible unconsciousness

Forced jack-out dumps you to the nearest relay node or back to meatspace (depending on severity).

## Matrix Content

### Router Objects
Interactive kiosks in spine/relay rooms:
- Show connected nodes (hubs/upgraded spaces)
- Interface for routing to connected devices/nodes
- Don't show all connected devices by default (would be overwhelming)

### Programs
Craftable/buyable tools:
- **CRUD**: Basic data manipulation
- **Cryptography**: Encrypt/decrypt data
- **Trace**: Locate devices on the network (which relay, physical location)
- **Probe/Scan**: Search for specific devices on current relay
- **Recall**: Return to beacon
- **Daemons**: Background processes (monitoring, ICE, auto-defense)
- **Weapons**: Attack programs (may also be daemons)

### Data
Generic blobs of information that exist as physical objects in the Matrix. Can be carried, dropped, transferred, encrypted, etc.

### ICE (Intrusion Countermeasures Electronics)
Defensive programs/daemons that protect nodes:
- Auto-spawned for basic/unprotected devices
- Persistent and customizable in upgraded hubs
- Can destroy beacons
- Combat capable

## Public Services (Subframe B)

Historically controlled by the guilds, these services live in Subframe B:

### The Feed
Twitter-like microblogging:
- Short public posts
- Topics (hashtags) for organization
- Auto-archived in The Archives

### The Archives
Public library/historical record:
- All Feed posts permanently preserved
- Curated section for approved pages/content
- Managed by curator (NPC or player role)
- Searchable

### Pages
Static content hosting (FrameML markup language):
- Personal pages, manifestos, ASCII art
- Support alt text for accessibility
- Basic formatting (headers, links, text styling)
- Can be archived if curator approves

### Chat/DMs
Direct messaging between Frame IDs.

## Accounts & Identity

### Frame ID
Your handle on the network (@username). Tied to your physical identity.

### Account Types
- **Citizen account**: One per person, tied to city ID
- **Corporate/work accounts**: Issued by employers, monitored, multiple possible
- **Clandestine accounts**: Burner accounts, spoofed IDs, relay exploits

### Verification
Only corporations and government entities get verified badges. Regular citizens have no badge, which provides some anonymity mixed in with burner accounts.

### Profile vs Record
- **Profile**: Public-facing info anyone can see (editable by user)
- **Record**: Official backend data (identity, linked accounts, logs, infractions) - requires authority access or hacking

## Political Structure

### The Frame (AGI)
Runs core city infrastructure but is politically constrained by the guilds.

### The Guilds
Control Subframe B and public services. Historically restructured the network to keep The Frame in check (moved Spine A connection from Cortex to Spine B, creating Firewall A-B as a choke point).

### Spine Territories
- **Spine A**: Frame territory, connects through Firewall A-B to Spine B
- **Spine B**: Guild territory, hosts public services in Subframe B
- **Spine C**: Bougie/upper class district
- **Spine W**: Working class/service district

Firewalls between spines create security boundaries and political control points.

## Tunneling & Tracing

### Tunneling
Routing connections through intermediate consoles to hide your location:
- Each hop slows connection but obscures origin
- Requires credentials or exploits on each console in the chain
- Creates a connection tree: Your device → Console X → Console Y → Target

### Tracing
Following connection hops backward:
- Lazy traces stop at first hop
- Thorough investigations follow entire chain
- Requires access to systems along the route
- Better trace programs are faster/stealthier

## Design Philosophy

- **No perfect crimes**: Every action leaves traces
- **Distance is compressed**: Relays cover large physical areas, but walking between relays in the Matrix is still required
- **Persistence over temporary**: All nodes persist (no cleanup needed)
- **Tools create depth**: Programs like Trace and Probe aren't default commands - you need the right tools
- **Physical/virtual interplay**: Moving a device in meatspace affects Matrix navigation
- **Security through obscurity works (somewhat)**: Devices aren't automatically visible - someone needs to scan for them


as a decker there are up to three routers that you need to worry about:
the one your rig is connected to,
the one you are using as a proxy (if you have one, eventually this will be a skill-check so you need decking skill),
the one that a device is connected to (if you are accessing the device),

if you go to a router you will get an option to return back to your home router. if you are using a proxy you will wind up there and you can close the proxy then run it again.... (so if you put your proxy in a dumb place good luck. you gotta go back there to close it)
