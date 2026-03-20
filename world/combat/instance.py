from __future__ import annotations

import time
import uuid


class CombatInstance:
    def __init__(self, participants):
        self.id = str(uuid.uuid4())
        self.participants = set(participants or [])
        self.started_at = time.time()
        self.rounds = 0
        self.initiative = {}
        self.cover_state = {}
        self.ended = False

    def add_participant(self, char):
        if char:
            self.participants.add(char)

    def remove_participant(self, char):
        if char in self.participants:
            self.participants.discard(char)
        if len(self.participants) < 2:
            self.end()

    def next_round(self):
        self.rounds += 1
        return self.rounds

    def set_cover(self, char, in_cover):
        if char:
            self.cover_state[char.id] = bool(in_cover)

    def is_in_cover(self, char):
        if not char:
            return False
        return bool(self.cover_state.get(char.id, False))

    def set_initiative(self, char, score):
        if char:
            self.initiative[char.id] = int(score or 0)

    def turn_order(self):
        ordered = sorted(
            [c for c in self.participants if c],
            key=lambda c: self.initiative.get(c.id, 0),
            reverse=True,
        )
        return ordered

    def end(self):
        self.ended = True


_INSTANCES = {}
_BY_PARTICIPANT = {}


def get_instance_for(char):
    if not char:
        return None
    inst_id = _BY_PARTICIPANT.get(char.id)
    if not inst_id:
        return None
    return _INSTANCES.get(inst_id)


def ensure_instance(a, b):
    inst = get_instance_for(a) or get_instance_for(b)
    if not inst or inst.ended:
        inst = CombatInstance([a, b])
        _INSTANCES[inst.id] = inst
    inst.add_participant(a)
    inst.add_participant(b)
    _BY_PARTICIPANT[a.id] = inst.id
    _BY_PARTICIPANT[b.id] = inst.id
    return inst


def leave_instance(char):
    if not char:
        return
    inst = get_instance_for(char)
    _BY_PARTICIPANT.pop(char.id, None)
    if not inst:
        return
    inst.remove_participant(char)
    if inst.ended:
        _INSTANCES.pop(inst.id, None)
        for part in list(inst.participants):
            if part:
                _BY_PARTICIPANT.pop(part.id, None)


def try_auto_switch_target(attacker):
    """
    Multi-target helper: if current target is gone, pick another participant.
    """
    if not attacker:
        return None
    inst = get_instance_for(attacker)
    if not inst:
        return None
    for candidate in inst.participants:
        if candidate == attacker:
            continue
        if getattr(candidate.db, "current_hp", 1) > 0 and candidate.location == attacker.location:
            return candidate
    return None

