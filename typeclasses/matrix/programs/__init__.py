"""
Matrix Programs Package

Executable programs that avatars carry and use in the Matrix.
"""

from typeclasses.matrix.programs.base import Program
from typeclasses.matrix.programs.utility import (
    SysInfoProgram,
    CmdExeProgram,
    CRUDProgram,
)
from typeclasses.matrix.programs.exploits import (
    SkeletonKeyProgram,
    ExfilProgram,
    InfilProgram,
    ICEpickProgram,
)

__all__ = [
    "Program",
    "SysInfoProgram",
    "CmdExeProgram",
    "CRUDProgram",
    "SkeletonKeyProgram",
    "ExfilProgram",
    "InfilProgram",
    "ICEpickProgram",
]
