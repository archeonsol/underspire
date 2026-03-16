# The Frame - Development Roadmap

## Concept Overview

**The Frame** is the city-wide network infrastructure for an underground city in a sci-fi RPG setting. It serves as both a social network and a hackable digital infrastructure that connects every electronic device in the city.

### Core Philosophy

- Everything electronic is connected to the Frame
- The Frame has biological naming (brain, spine, nervous system)
- Two modes of interaction: surface usage (normies) and diving (specialists)
- Physical proximity matters - remote hacking routes through infrastructure, direct hacking bypasses it
- No perfect crimes - traces are always left behind

---

## Network Architecture

### Physical Infrastructure

```
[MainFrame] - The brain. Central server farm at city center.
     |
 [Cortex] - Central routing hub. All inter-district traffic flows through here.
     |
[SpineFrames] - District-level backbone. Each city sector has its own spine.
     |
[Relays] - Wireless broadcast points along spines
[Access Points] - Hardwired connection ports
```

**MainFrame**: The city's central computing core. Heavily secured, possibly sentient (future feature).

**Cortex**: Central routing and security checkpoint. All SpineFrame-to-SpineFrame traffic passes through with varying security levels based on origin/destination.

**SpineFrames**: District-level infrastructure branches. Handle local queries reflexively without MainFrame involvement. Mirror physical city geography.

**Relays**: Wireless signal broadcasters. Hardwired to SpineFrames, provide local wireless coverage.

**Access Points**: Physical hardwired connection ports. Faster and more reliable than wireless.

**Hubs**: Private network devices (purchased by citizens/corps). Act as firewalls and security boundaries. Can be wireless or hardwired.

---

## Devices

### Handset
- Basic Frame access device
- Tied to citizen Frame ID (identity key)
- Issued to all citizens (free/mandatory)
- Can slot into decks to provide wireless access and identity
- Alone: Posts, DMs, reading pages
- Work accounts possible (tied to employment)

### Deck (Tablet)
- Personal computing device
- Requires slotted handset for wireless access
- Can connect via access points (hardwired) for better speed/reliability
- Full Frame capabilities
- Can be modded/jailbroken (future)

### Console
- Public/service terminals throughout the city
- Found at libraries, government offices, bill payment kiosks, etc.
- Can be used in guest mode or with handset slotted
- Potential proxy/tunnel points (future)
- Not owned by players, exist in the world

---

## Account System

### Frame ID
- Your @handle on the Frame
- Tied to citizen identity
- One official account per citizen
- Corporate/work accounts possible (tied to employment and citizen ID)
- Verification badges only for corporate/government accounts

### Profile
- Public-facing information
- Display name, bio, posts, pages
- User-editable (within limits)
- Visible to anyone

### Record
- Official backend data
- Real identity, linked accounts, activity logs
- Only accessible to authorities or via hacking
- Infractions, flags, social credit (potentially)

### Clandestine Accounts
- Burner accounts (temporary, limited functionality)
- Spoofed credentials (fake citizen IDs - harder to get, full functionality)
- Obtained through black market or exploits

---

## Frame Features

### Posts
- Short public messages (Twitter-like)
- Published to public feed
- Can include topics (hashtags)

### Topics
- Hashtag system for organizing/discovering posts
- Filter feeds by topic

### Direct Messages (DMs)
- Private point-to-point communication
- Encrypted by default (varying levels)

### Pages
- Static content hosting (ASCII art, information, manifestos)
- Basic markup language for accessibility
- Headers, links, alt text for images
- User-hosted content

### Broadcasting (Future)
- Recording/streaming service
- On-demand and live broadcasts

---

## Access Tiers

### Surface Access (Handset)
- Browser-style interface
- Posts, DMs, pages
- What 99% of citizens use
- No diving involved

### Partial Dive (Deck/Console)
- Visual representation of Frame-space on screen
- "Playing a video game" - you navigate virtual spaces but watch on screen
- Can perform hacking operations (slower/limited)
- Safer than full dive (no personal risk)
- Access simple device virtual spaces (cameras, locks, etc.)

### Full Dive (Future)
- Direct neural interface via:
  - **Datajack**: Cybernetic implant (decker route)
  - **Psionic Attunement**: Psychic connection (psion route)
- Fully immersed in Frame virtual space
- Faster, more capable, but dangerous (ICE can hurt you)
- Navigate complex corporate architectures
- Can meet other divers in virtual space

---

## Security & Hacking

### Connection Tracking
- Every connection shows originating relay (wireless) or access point (hardwired)
- Wireless: Neighborhood-level precision
- Hardwired: Building/room-level precision

### Traces
- All Frame activity leaves traces
- Access logs, timestamps, routing paths
- Perfect crimes are impossible
- Good hackers minimize traces but can't eliminate them

### Hubs as Firewalls
- Create security boundary between Frame and devices
- Filter traffic, block unauthorized access
- Isolate private networks (home, office, corporate)
- Can boost wireless signal if hardwired
- Misconfigured hubs are common vulnerabilities

### Tunneling/Proxying (Future)
- Route connections through compromised consoles/devices
- Each hop requires credentials or active exploit
- Traces show proxy location instead of real location
- Multiple hops = harder to trace but slower connection
- Creates connection trees for investigators to follow

### ICE (Future)
- Intrusion Countermeasures Electronics
- Automated security defenses
- Encountered in virtual dive spaces
- Can damage full-dive users
- Varying complexity based on system value

### Hacking Approaches

**Remote Hacking:**
- Through Frame infrastructure
- Must route through Cortex and SpineFrames
- Subject to all security checks
- Can do from anywhere
- Leaves routing traces

**Direct Hacking:**
- Requires physical proximity to target
- Bypasses Cortex/routing entirely
- Point-to-point connection
- Fewer Frame traces (but physical presence is evidence)
- Some air-gapped systems require this

---

## Virtual Spaces (Future)

### District SpineFrames
- Virtual geography mirrors physical city
- Each district accessible through its SpineFrame
- Moving between districts = security checkpoints
- Slums = low security, corporate sectors = heavy ICE
- The Frame has "neighborhoods"

### Device Spaces
Complexity scales to system:

**Simple devices** (camera, door lock):
- Minimalist virtual room
- "A sterile control room. One terminal displays [LOCK STATUS: ENGAGED]"
- Quick in-and-out

**Medium complexity** (building security):
- Small architecture to navigate
- Few rooms/nodes
- Basic ICE if secured

**Complex systems** (corporate mainframe):
- Full virtual architecture
- Multiple layers and security zones
- Serious ICE and countermeasures
- Major infiltration gameplay

---

## Development Phases

### Phase 0: Core Foundation
**Data Models:**
- Frame ID system (accounts, handles)
- Profile/Record split (public vs official data)
- Device objects (handsets, decks, consoles)
- Network topology (SpineFrames, Relays, Access Points)

**Authentication:**
- Frame ID creation/registration
- Login system
- Handset → device association

**Dependencies:** None. Start here.

---

### Phase 1: Network Infrastructure
**Location System:**
- SpineFrame zones (map to city districts)
- Relay coverage areas
- Access Point placements
- Track device connections (which relay/access point)

**Basic Connectivity:**
- Connect via wireless (through relay)
- Connect via hardwired (through access point)
- Connection status tracking

**Dependencies:** Phase 0

---

### Phase 2: Communication Features
**Posts:**
- Create/read posts
- Topic (hashtag) system
- Public feed viewing
- Filter by topic

**Direct Messages:**
- Send/receive DMs
- Conversation threads
- Read receipts (optional)

**Pages:**
- Create/edit pages
- Basic markup parser (headers, links, alt text)
- Page discovery/linking

**Dependencies:** Phase 0, Phase 1 (need to be connected to post)

---

### Phase 3: Device Management
**Handsets:**
- Issue handsets to new characters
- Handset slotting into decks
- Identity verification through handset

**Decks:**
- Acquire/own decks
- Wireless vs hardwired modes
- Speed/capability differences

**Consoles:**
- Public console locations in world
- Guest mode vs logged-in mode
- Usage logging

**Dependencies:** Phase 0, Phase 1

---

### Phase 4: Basic Security & Tracing
**Connection Tracking:**
- View your own connection info
- Basic trace command (see where someone's connected)
- Connection logs in Records

**Hubs (Basic):**
- Purchase/install hubs
- Connect devices through hub
- Basic firewall (blocks traces from outside)

**Dependencies:** Phase 1, Phase 3

---

## Future Phases (Post-MVP)

### Advanced Networking
- Tunneling/proxying through compromised systems
- Connection trees and trace chains
- Wireless bridges (hacked handsets)
- Relay spoofing

### Partial Dive System
- Virtual space framework (rooms/nodes)
- Navigation commands
- Simple device diving (cameras, locks, terminals)
- Basic ICE encounters
- Screen-based interface

### Full Dive System
- Datajack cyberware
- Psionic attunement mechanics
- Avatar system in virtual space
- ICE combat/evasion
- Risk/damage to diver

### Complex Virtual Architectures
- Corporate network spaces
- SpineFrame district navigation
- Security checkpoints between districts
- Explorable corporate nodes
- Virtual meeting spaces

### Sentient Frame AI
- MainFrame as conscious entity
- GM-able Frame personality
- Frame responses and interactions
- Emergent intelligence behaviors

### Broadcasting & Media
- Recording services
- Live streaming
- On-demand content
- Media distribution

### IoT Integration
- Cameras, microphones
- Door locks, access controls
- Vending machines, kiosks
- Traffic systems
- Any electronic device

### Device Modding
- Jailbreaking handsets/decks
- Custom software installation
- Exploit tools
- Trace utilities
- Security bypasses

### Record Hacking
- Alter your own official record
- Frame others by editing their records
- Clean criminal history
- Forge credentials
- Social credit manipulation

---

## MVP Success Criteria

Players can:
- ✓ Create Frame ID and receive a handset
- ✓ Connect to the Frame from different locations (wireless/hardwired)
- ✓ Post to public feed with topics
- ✓ Send DMs to each other
- ✓ Create and browse pages
- ✓ See where they're connected from (relay/access point)
- ✓ Use public consoles around the city
- ✓ Understand connection security implications

---

## Design Principles

1. **The Easy Way Should Be The Right Way**: Frame interfaces should be intuitive, common actions should be simple
2. **MVP First**: Build core functionality before adding complexity
3. **Physical Consequences**: Location matters, devices matter, presence leaves traces
4. **No Perfect Crimes**: Security can be bypassed but never perfectly - traces remain
5. **Accessibility**: Markup language supports alt text and accessibility features
6. **Emergent Gameplay**: Simple systems combine to create complex interactions
7. **Social Integration**: The Frame is where players communicate IC, making it central to gameplay