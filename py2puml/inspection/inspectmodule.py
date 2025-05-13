import types
from dataclasses import is_dataclass
from enum import Enum
from inspect import getmembers, isclass, ismethod, isfunction, signature
from types import ModuleType
from typing import Dict, Iterable, List, Type, get_args, Union, get_origin

from py2puml.domain.umlclass import UmlMethod
from py2puml.domain.umlfunction import UmlFunction, UmlModule
from py2puml.domain.umlitem import UmlItem
from py2puml.domain.umlrelation import UmlRelation, RelType
from py2puml.inspection.inspectclass import inspect_class_type, inspect_dataclass_type, \
    handle_class_method_dependencies, resolve_type_fqn
from py2puml.inspection.inspectenum import inspect_enum_type
from py2puml.inspection.inspectnamedtuple import inspect_namedtuple_type


def filter_domain_definitions(module: ModuleType, root_module_name: str) -> Iterable[Type]:
    for definition_key in dir(module):
        definition_type = getattr(module, definition_key)
        if isclass(definition_type):
            definition_members = getmembers(definition_type)
            definition_module_member = next(
                (
                    member
                    for member in definition_members
                    # ensures that the type belongs to the module being parsed
                    if member[0] == '__module__' and member[1].startswith(root_module_name)
                ),
                None,
            )
            if definition_module_member is not None:
                yield definition_type
        if isfunction(definition_type) and definition_type.__module__.startswith(root_module_name):
            yield definition_type

def get_type_name(annotation):
    # Handle typing.Union (Python 3.7 - 3.9) and UnionType (Python 3.10+)
    if getattr(annotation, '__origin__', None) is Union or isinstance(annotation, types.UnionType):
        args = get_args(annotation)
        type_names = [get_type_name(arg) for arg in args]
        return ' | '.join(type_names)
    # Handle built-in generics like List[int], Dict[str, int], etc.
    elif hasattr(annotation, '__origin__') and hasattr(annotation, '__args__'):
        origin_name = get_type_name(annotation.__origin__)
        args = annotation.__args__
        args_names = ', '.join(get_type_name(arg) for arg in args)
        return f'{origin_name}[{args_names}]'
    # Handle simple types
    elif hasattr(annotation, '__name__'):
        return annotation.__name__
    # Handle typing types like List, Dict without parameters
    elif hasattr(annotation, '_name') and annotation._name is not None:
        return annotation._name
    elif isinstance(annotation, str):
        # For annotations as strings (from postponed evaluation of annotations)
        return annotation.split('.')[-1]
    else:
        # As a fallback, attempt to extract the class name from the string representation
        annotation_str = str(annotation)
        # Remove module paths and extraneous characters
        if 'typing.' in annotation_str:
            # Handle typing types
            annotation_str = annotation_str.replace('typing.', '')
        if '.' in annotation_str:
            return annotation_str.split('.')[-1]
        else:
            return annotation_str

def extract_types_from_annotation(annotation):
    types = []
    origin = get_origin(annotation)
    if origin is Union:
        # Handle Union types
        args = get_args(annotation)
        for arg in args:
            types.extend(extract_types_from_annotation(arg))
    elif origin is not None:
        # Handle generic types like List[Type], Dict[KeyType, ValueType]
        args = get_args(annotation)
        types.append(origin)
        for arg in args:
            types.extend(extract_types_from_annotation(arg))
    else:
        # Simple type
        types.append(annotation)
    return types

def add_dependency_relation(
    func: str,
    source_fqn: str,
    type_hint,
    root_module_name: str,
    domain_items_by_fqn: Dict[str, UmlItem],
    domain_relations: List[UmlRelation]
):
    # Resolve all types involved in the type hint
    # types = extract_types_from_annotation(type_hint)
    types =type_hint
    for return_type in types:
        if return_type:
            if isinstance(return_type, str):
                return_fqn = resolve_type_fqn(return_type, domain_items_by_fqn)
            elif isinstance(return_type, type):
                return_fqn = f'{return_type.__module__}.{return_type.__name__}'
            else:
                return_fqn = None  # Fallback if unable to resolve return type

            if return_fqn and return_fqn.startswith(root_module_name) and return_fqn in domain_items_by_fqn:
                source_for_function = f'{func.__module__}.Methods'
                domain_relations.append(UmlRelation(source_for_function, return_fqn, RelType.DEPENDENCY, func.__name__))

def inspect_function(
        func,
        root_module_name: str,
        domain_items_by_fqn: Dict[str, UmlItem],
        uml_module: UmlModule,
        domain_relations: List[UmlRelation],
        firstPass=True
):
    func_fqn = f'{func.__module__}.{func.__name__}'

    # Create UmlFunction instance
    uml_function = UmlFunction(fqn=func_fqn, name=func.__name__, module=func.__module__)
    domain_items_by_fqn[func_fqn] = uml_function
    if firstPass:
        uml_module.functions.append(uml_function)  # Add function to module

    # Parse function signature
    sig = signature(func)
    for param_name, param in sig.parameters.items():
        param_type = None
        if param.annotation != param.empty:
            param_type = extract_types_from_annotation(param.annotation)
            # Handle dependencies in parameters
            if not firstPass:
                add_dependency_relation(
                    func=func,
                    source_fqn=func_fqn,
                    type_hint=param_type,
                    root_module_name=root_module_name,
                    domain_items_by_fqn=domain_items_by_fqn,
                    domain_relations=domain_relations
                )
        uml_function.arguments[param_name] = param_type

    # Handle return type
    if sig.return_annotation != sig.empty:
        return_type = extract_types_from_annotation(sig.return_annotation)
        uml_function.return_type = return_type
        # Handle dependencies in return type
        if not firstPass:
            add_dependency_relation(
                func=func,
                source_fqn=func_fqn,
                type_hint=return_type,
                root_module_name=root_module_name,
                domain_items_by_fqn=domain_items_by_fqn,
                domain_relations=domain_relations
            )

def inspect_domain_definition(definition_type: Type, root_module_name: str, domain_items_by_fqn: Dict[str, UmlItem],
                              domain_relations: List[UmlRelation], uml_module: UmlModule, firstPass=True):
    definition_type_fqn = f'{definition_type.__module__}.{definition_type.__name__}'
    # First pass: Register all classes in domain_items_by_fqn
    if firstPass:
        if definition_type_fqn not in domain_items_by_fqn:
            if isfunction(definition_type):
                inspect_function(definition_type, root_module_name, domain_items_by_fqn, uml_module, domain_relations, firstPass)
            elif issubclass(definition_type, Enum):
                inspect_enum_type(definition_type, definition_type_fqn, domain_items_by_fqn)
            elif getattr(definition_type, '_fields', None) is not None:
                inspect_namedtuple_type(definition_type, definition_type_fqn, domain_items_by_fqn)
            elif is_dataclass(definition_type):
                inspect_dataclass_type(
                    definition_type, definition_type_fqn, root_module_name, domain_items_by_fqn, domain_relations
                )

            else:

                inspect_class_type(
                    definition_type, definition_type_fqn, root_module_name, domain_items_by_fqn, domain_relations
                )


    else:

        if isfunction(definition_type):
            inspect_function(definition_type, root_module_name, domain_items_by_fqn, uml_module, domain_relations, firstPass=False)
        elif issubclass(definition_type, Enum):
            pass
        elif getattr(definition_type, '_fields', None) is not None:
            pass
        elif is_dataclass(definition_type):
            pass
        else:

            handle_class_method_dependencies(
                definition_type, definition_type_fqn, root_module_name, domain_items_by_fqn, domain_relations
            )

def inspect_module(domain_item_module: ModuleType, root_module_name: str, domain_items_by_fqn: Dict[str, UmlItem],
                   domain_relations: List[UmlRelation],modules_by_name: Dict[str, UmlModule], firstPass=True):
    # processes only the definitions declared or imported within the given root module
    module_name = domain_item_module.__name__
    if module_name not in modules_by_name:
        modules_by_name[module_name] = UmlModule(name=module_name)
    uml_module = modules_by_name[module_name]

    for definition_type in filter_domain_definitions(domain_item_module, root_module_name):
        inspect_domain_definition(definition_type, root_module_name, domain_items_by_fqn, domain_relations,uml_module, firstPass)
