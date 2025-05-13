from dataclasses import dataclass, field
from typing import Dict, List, Union

from py2puml.domain.umlitem import UmlItem


def get_class_name_from_abcmeta(data):
    if hasattr(data, '__name__'):
        return data.__name__
    # Convert to string and split by '.'
    full_name = str(data)

    # Extract the last part after splitting by '.'
    # First remove the "<class '" prefix and "'>" suffix
    if full_name.startswith("[<class '") and full_name.endswith("'>]"):
        return full_name[len("<class '"):-len("'>")].split('.')[-1]

    # Return the last part of the name
    return full_name

@dataclass
class UmlFunction(UmlItem):
    name: str
    module: str
    arguments: Dict[str, Union[str, List[str]]] = field(default_factory=dict)
    return_type: Union[str, List[str], None] = None


    def represent_as_puml(self):
        items = []
        # Handle return type
        if self.return_type:
            if isinstance(self.return_type, list):
                items.append(" | ".join(get_class_name_from_abcmeta(item) for item in self.return_type[1:]))
            else:
                items.append(self.return_type)
        # Construct function signature from arguments
        signature = ", ".join(f"{name}: {get_class_name_from_abcmeta(type_)}" for name, type_ in self.arguments.items())
        items.append(f'{self.name}({signature})')
        return ' '.join(items)


@dataclass
class UmlModule:
    name: str
    functions: List[UmlFunction] = field(default_factory=list)

    def represent_as_puml(self):
        if len(self.functions) > 0:
            lines = [f'annotation {self.name}.Methods {{']
            for func in self.functions:
                lines.append(f'  {func.represent_as_puml()}')
            lines.append('}\n')
            return '\n'.join(lines)
        else:
            return ''