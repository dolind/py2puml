from dataclasses import dataclass
from enum import Enum, unique


@unique
class RelType(Enum):
    COMPOSITION = '*'
    INHERITANCE = '<|'
    DEPENDENCY = '<'



class UmlRelation:
    def __init__(self, source, target, rel_type, text=''):
        self.source_fqn = source
        self.target_fqn = target
        self.type = rel_type
        self.text = text

    def __eq__(self, other):
        return (
                isinstance(other, UmlRelation) and
                self.source_fqn == other.source_fqn and
                self.target_fqn == other.target_fqn and
                self.type == other.type
        )

    def __hash__(self):
        return hash((self.source_fqn, self.target_fqn, self.type))

