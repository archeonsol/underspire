"""
Matrix Module

Typeclasses for The Frame - the city's virtual network infrastructure.

This module contains all Frame/cyberspace related typeclasses:
- rooms.py: Virtual locations (MatrixNode - spine nodes, device interfaces, etc.)
- devices/: Physical Matrix devices (DiveRig, Hub, Handset, etc.)
- avatars.py: Virtual presence objects (MatrixAvatar)
- items.py: Matrix items (NetworkedItem, MatrixItem, Program and subclasses)
- objects.py: Networked physical objects
- mixins/: Shared functionality (NetworkedMixin, MatrixIdMixin)

Programs are executable items that avatars carry and run via 'exec' command:
- SysInfoProgram: Device information utility
- CmdExeProgram: Command execution interface
- CRUDProgram: File operations (create/read/update/delete)
- ExfilProgram: Data exfiltration (extract files to portable data chips)
- InfilProgram: Data infiltration (upload data chips to device storage)
- SkeletonKeyProgram: ACL manipulation (illegal)
- ICEpickProgram: Combat utility against ICE
"""
