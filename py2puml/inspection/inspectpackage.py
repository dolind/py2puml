from importlib import import_module
from pkgutil import walk_packages
from types import ModuleType
from typing import Dict, List

from py2puml.domain.umlfunction import UmlFunction, UmlModule
from py2puml.domain.umlitem import UmlItem
from py2puml.domain.umlrelation import UmlRelation
from py2puml.inspection.inspectmodule import inspect_module


def remove_duplicate_relations_in_place(domain_relations):
    # Use a set to track unique relation tuples
    unique_relations_set = set()

    # Modify domain_relations in place
    i = 0
    while i < len(domain_relations):
        relation = domain_relations[i]
        # Create a tuple of the relation's essential properties
        relation_tuple = (relation.source_fqn, relation.target_fqn, relation.type)

        if relation_tuple in unique_relations_set:
            # If the relation is a duplicate, remove it
            domain_relations.pop(i)
        else:
            # Otherwise, add it to the set and move to the next item
            unique_relations_set.add(relation_tuple)
            i += 1
def inspect_package(
    domain_path: str, domain_module: str, domain_items_by_fqn: Dict[str, UmlItem], domain_relations: List[UmlRelation],
    modules_by_name: Dict[str, UmlModule]
):
    # inspects the package module first, then its children modules and subpackages
    item_module = import_module(domain_module)
    inspect_module(item_module, domain_module, domain_items_by_fqn, domain_relations, modules_by_name)

    for _, name, is_pkg in walk_packages([domain_path], f'{domain_module}.'):
        if not is_pkg:
            domain_item_module: ModuleType = import_module(name)
            inspect_module(domain_item_module, domain_module, domain_items_by_fqn, domain_relations, modules_by_name)

    for _, name, is_pkg in walk_packages([domain_path], f'{domain_module}.'):
        if not is_pkg:
            domain_item_module: ModuleType = import_module(name)
            inspect_module(domain_item_module, domain_module, domain_items_by_fqn, domain_relations, modules_by_name,firstPass=False)

    item_module = import_module(f'{domain_module}', f'{domain_module}.')
    inspect_module(item_module, domain_module, domain_items_by_fqn, domain_relations, modules_by_name)


    remove_duplicate_relations_in_place(domain_relations)







