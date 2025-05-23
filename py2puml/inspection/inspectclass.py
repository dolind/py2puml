from dataclasses import dataclass
from ast import AST, parse
from importlib import import_module
from inspect import getsource, isabstract, signature
from re import compile as re_compile
from typing import Dict, List, Type

from py2puml.domain.umlclass import UmlAttribute, UmlClass
from py2puml.domain.umlitem import UmlItem
from py2puml.domain.umlrelation import RelType, UmlRelation
from py2puml.parsing.astvisitors import ClassVisitor, shorten_compound_type_annotation
from py2puml.parsing.moduleresolver import ModuleResolver
from py2puml.parsing.parseclassconstructor import parse_class_constructor

CONCRETE_TYPE_PATTERN = re_compile("^<(?:class|enum) '([\\.|\\w]+)'>$")


def handle_inheritance_relation(
    class_type: Type, class_fqn: str, root_module_name: str, domain_relations: List[UmlRelation]
):
    for base_type in getattr(class_type, '__bases__', ()):
        base_type_fqn = f'{base_type.__module__}.{base_type.__name__}'
        if base_type_fqn.startswith(root_module_name):
            domain_relations.append(UmlRelation(base_type_fqn, class_fqn, RelType.INHERITANCE))


def inspect_static_attributes(
    class_type: Type,
    class_type_fqn: str,
    root_module_name: str,
    domain_items_by_fqn: Dict[str, UmlItem],
    domain_relations: List[UmlRelation],
) -> List[UmlAttribute]:
    """
    Adds the definitions:
    - of the inspected type
    - of its static attributes from the class annotations (type and relation)
    """
    # defines the class being inspected
    definition_attrs: List[UmlAttribute] = []
    uml_class = UmlClass(
        name=class_type.__name__,
        fqn=class_type_fqn,
        attributes=definition_attrs,
        is_abstract=isabstract(class_type),
        methods=[],
    )
    domain_items_by_fqn[class_type_fqn] = uml_class
    # investigate_domain_definition(class_type)

    type_annotations = getattr(class_type, '__annotations__', None)
    parent_class_type = getattr(class_type, '__bases__', None)[0]
    parent_type_annotations = getattr(parent_class_type, '__annotations__', None)

    if type_annotations is not None:
        # stores only once the compositions towards the same class
        relations_by_target_fqdn: Dict[str:UmlRelation] = {}
        # utility which outputs the fully-qualified name of the attribute types
        module_resolver = ModuleResolver(import_module(class_type.__module__))

        # builds the definitions of the class attributes and their relationships by iterating over the type annotations
        for attr_name, attr_class in type_annotations.items():
            # Skip class attributes accidentally inherited from parent class
            if parent_type_annotations and attr_name in parent_type_annotations.keys():
                continue

            attr_raw_type = str(attr_class)
            concrete_type_match = CONCRETE_TYPE_PATTERN.search(attr_raw_type)
            # basic type
            if concrete_type_match:
                concrete_type = concrete_type_match.group(1)
                # appends a composition relationship if the attribute is a class from the inspected domain
                if attr_class.__module__.startswith(root_module_name):
                    attr_type = attr_class.__name__
                    attr_fqn = f'{attr_class.__module__}.{attr_class.__name__}'
                    relations_by_target_fqdn[attr_fqn] = UmlRelation(uml_class.fqn, attr_fqn, RelType.COMPOSITION)
                else:
                    attr_type = concrete_type
            # compound type (tuples, lists, dictionaries, etc.)
            else:
                (
                    attr_type,
                    full_namespaced_definitions,
                ) = shorten_compound_type_annotation(attr_raw_type, module_resolver)
                relations_by_target_fqdn.update(
                    {
                        attr_fqn: UmlRelation(uml_class.fqn, attr_fqn, RelType.COMPOSITION)
                        for attr_fqn in full_namespaced_definitions
                        if attr_fqn.startswith(root_module_name)
                    }
                )

            uml_attr = UmlAttribute(attr_name, attr_type, static=True)
            definition_attrs.append(uml_attr)

        domain_relations.extend(relations_by_target_fqdn.values())

    return definition_attrs

def resolve_type_fqn(type_hint: str, domain_items_by_fqn: Dict[str, UmlClass]) -> str:
    """
    Resolves a type hint to its fully qualified name by searching domain_items_by_fqn.
    If an exact match for the type hint is found within the domain items, it returns the FQN.
    """
    # Iterate over the items in domain_items_by_fqn to find a match for the class name
    for fqn, uml_class in domain_items_by_fqn.items():
        # Compare the type_hint with the name attribute of UmlClass to find a match
        if uml_class.name == type_hint:
            return fqn  # Return the fully qualified name if found

    # Return None if no match is found
    return None

def handle_methods_dependencies(
    definition_methods: List,
    class_type: Type,
    root_module_name: str,
    domain_items_by_fqn: Dict[str, UmlItem],
    domain_relations: List[UmlRelation],
):
    print(f'inspecting {class_type.__name__} from {class_type.__module__}')
    class_source: str = getsource(class_type)
    class_ast: AST = parse(class_source)
    visitor = ClassVisitor(class_type, root_module_name)
    visitor.visit(class_ast)
    for method in visitor.uml_methods:
        if "__init__" in method.name:
            continue
        if len(method.arguments) == 1:
            ## TODO: also exclude non class without arguments
            continue

            # Fully qualified name of the current class
        class_type_fqn = f'{class_type.__module__}.{class_type.__name__}'

        for param_name, param_type in method.arguments.items():
            if param_type:
                # If param_type is a string or custom representation, resolve it to an FQN
                if isinstance(param_type, str):
                    # Use module resolver or custom logic to resolve type
                    param_fqn = resolve_type_fqn(param_type, domain_items_by_fqn)
                elif isinstance(param_type, type):
                    param_fqn = f'{param_type.__module__}.{param_type.__name__}'
                else:
                    continue  # Skip if param_type can't be resolved to a known format

                # Only add to domain relations if within the specified root domain
                if param_fqn and param_fqn.startswith(root_module_name) and param_fqn in domain_items_by_fqn:
                    domain_relations.append(UmlRelation(class_type_fqn, param_fqn, RelType.DEPENDENCY))

        # Check return type hint
        return_types = method.return_type

        if isinstance(return_types, list):
            for return_type in return_types:
                if return_type:
                    if isinstance(return_type, str):
                        return_fqn = resolve_type_fqn(return_type, domain_items_by_fqn)
                    elif isinstance(return_type, type):
                        return_fqn = f'{return_type.__module__}.{return_type.__name__}'
                    else:
                        return_fqn = None  # Fallback if unable to resolve return type

                    if return_fqn and return_fqn.startswith(root_module_name) and return_fqn in domain_items_by_fqn:
                        domain_relations.append(UmlRelation(class_type_fqn, return_fqn, RelType.DEPENDENCY))
        else:
            return_type = return_types
            if return_type:
                if isinstance(return_type, str):
                    return_fqn = resolve_type_fqn(return_type, domain_items_by_fqn)
                elif isinstance(return_type, type):
                    return_fqn = f'{return_type.__module__}.{return_type.__name__}'
                else:
                    return_fqn = None  # Fallback if unable to resolve return type

                if return_fqn and return_fqn.startswith(root_module_name) and return_fqn in domain_items_by_fqn:
                    domain_relations.append(UmlRelation(class_type_fqn, return_fqn, RelType.DEPENDENCY))


def inspect_class_methods(
    definition_methods: List,
    class_type: Type,
    root_module_name: str,
    domain_items_by_fqn: Dict[str, UmlItem],
    domain_relations: List[UmlRelation],
):
    print(f'inspecting {class_type.__name__} from {class_type.__module__}')
    class_source: str = getsource(class_type)
    class_ast: AST = parse(class_source)
    visitor = ClassVisitor(class_type, root_module_name)
    visitor.visit(class_ast)
    definition_methods.extend(visitor.uml_methods)



def handle_class_method_dependencies(
    class_type: Type,
    class_type_fqn: str,
    root_module_name: str,
    domain_items_by_fqn: Dict[str, UmlItem],
    domain_relations: List[UmlRelation],
):

    handle_methods_dependencies(domain_items_by_fqn[class_type_fqn].methods, class_type, root_module_name, domain_items_by_fqn, domain_relations)




def inspect_class_type(
    class_type: Type,
    class_type_fqn: str,
    root_module_name: str,
    domain_items_by_fqn: Dict[str, UmlItem],
    domain_relations: List[UmlRelation],
):
    attributes = inspect_static_attributes(
        class_type, class_type_fqn, root_module_name, domain_items_by_fqn, domain_relations
    )
    instance_attributes, compositions = parse_class_constructor(class_type, class_type_fqn, root_module_name)
    attributes.extend(instance_attributes)
    domain_relations.extend(compositions.values())

    inspect_class_methods(domain_items_by_fqn[class_type_fqn].methods, class_type, root_module_name, domain_items_by_fqn, domain_relations)

    handle_inheritance_relation(class_type, class_type_fqn, root_module_name, domain_relations)




def inspect_dataclass_type(
    class_type: Type[dataclass],
    class_type_fqn: str,
    root_module_name: str,
    domain_items_by_fqn: Dict[str, UmlItem],
    domain_relations: List[UmlRelation],
):
    for attribute in inspect_static_attributes(
        class_type, class_type_fqn, root_module_name, domain_items_by_fqn, domain_relations
    ):
        attribute.static = False

    handle_inheritance_relation(class_type, class_type_fqn, root_module_name, domain_relations)
