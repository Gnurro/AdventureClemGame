import json
import os
from copy import deepcopy
from typing import List, Set, Union

import lark
from lark import Lark, Transformer
import jinja2

from adv_util import fact_str_to_tuple, fact_tuple_to_str

# PDDL ACTIONS

with open("resources/pddl_actions.lark") as grammar_file:
    action_grammar = grammar_file.read()

# print(action_grammar)

action_parser = Lark(action_grammar, start="action")

# test_pddl_action = "test_pddl_actions.txt"
test_pddl_action = "test_pddl_actions_take.txt"

with open(test_pddl_action) as action_file:
    action_raw = action_file.read()


parsed_action = action_parser.parse(action_raw)

# print(parsed_action)


class PDDLActionTransformer(Transformer):
    """PDDL action definition transformer to convert Lark parse to python dict for further use.
    Method names must match grammar rule names, thus some rules have an added -p to distinguish their name from a python
    constant/type/default term string.
    """
    def action(self, content):
        # print("action cont:", content)

        # action_def_dict = {'action_name': content[1].value, 'content': content[3:]}
        action_def_dict = {'action_name': content[1].value.lower()}

        for cont in content:
            # print(type(cont))
            if type(cont) == lark.Token:
                # print(cont.type, cont.value)
                pass
            else:
                # print("non-Token", cont)
                if 'parameters' in cont:
                    action_def_dict['parameters'] = cont['parameters']
                elif 'precondition' in cont:
                    action_def_dict['precondition'] = cont['precondition']
                elif 'effect' in cont:
                    action_def_dict['effect'] = cont['effect']


        # action: lark.Tree = content[0]
        # action_type = action.data  # main grammar rule the input was parsed as
        # action_content = action.children  # all parsed arguments of the action 'VP'

        # print("action returns:", action_def_dict)
        return action_def_dict
        # return content
        # pass

    def parameters(self, content):
        parameter_list = None
        if type(content[0]) == lark.Token and content[0].type == "WS":
            parameter_list = content[1]
        # print("parameters:", parameter_list)

        return {'parameters': parameter_list}

    def precondition(self, content):
        # print("precond cont:", content)
        # print("precond cont:", content[1][1:])
        return {'precondition': content[1:-1]}

    def effect(self, content):
        # print("effect cont:", content)
        effect_dict = {'effect': content[1:-1]}
        # print("effect returns:", effect_dict)
        return effect_dict

    def forall(self, content):
        # print("forall cont:", content)
        iterated_object = content[2]
        # print("iterated object:", iterated_object)
        forall_body = content[4:]
        # print("forall body:", forall_body)

        forall_dict = {'forall': iterated_object, 'body': forall_body}
        # print("forall returns:", forall_dict)
        return forall_dict

    def when(self, content):
        # print("when cont:", content)
        when_items = list()
        for when_item in content:
            # ignore delimiters and whitespace:
            if type(when_item) == lark.Token and when_item.type in ["WHENL", "WS"]:
                pass
            else:
                when_items.append(when_item)
        when_dict = {'when': when_items}
        # print("when returns:", when_dict)
        return when_dict

    def andp(self, content):
        # print("andp cont:", content)
        and_items = list()
        for and_item in content:
            # ignore delimiters and whitespace:
            if type(and_item) == lark.Token and and_item.type in ["ANDL", "WS"]:
                pass
            else:
                and_items.append(and_item)
        and_dict = {'and': and_items}
        # print("andp returns:", and_dict, "\n")
        return and_dict

    def orp(self, content):
        # print("orp cont:", content)
        or_items = list()
        for or_item in content:
            # ignore delimiters and whitespace:
            if type(or_item) == lark.Token and or_item.type in ["ORL", "WS"]:
                pass
            else:
                or_items.append(or_item)
        or_dict = {'or': or_items}
        # print("orp returns:", or_dict, "\n")
        return or_dict

    def notp(self, content):
        # print("notp cont:", content)
        # (not X) always wraps only one item, hence:
        return {'not': content[2]}

    def type_list(self, content):
        # print(content)
        return {'type_list': content}

    def type_list_element(self, content):
        # print("type_list_item cont:", content)
        type_list_items = list()
        for item_element in content:
            if 'variable' in item_element:
                type_list_items.append(item_element)
            elif type(item_element) == lark.Token:
                if item_element.type == "WORDP":
                    type_list_items.append(item_element.value)
                elif item_element.type == "DASH":
                    break

        if content[-1].type == "WS":
            cat_name = content[-2].value
        else:
            cat_name = content[-1].value

        return {'type_list_element': cat_name, 'items': type_list_items}

    def equal(self, content):
        # print("equal cont:", content)
        # the (= X Y) can only ever take two arguments, thus directly accessing them:
        equal_dict = {'equal': [content[2], content[4]]}
        # print("equal returns:", equal_dict)
        return equal_dict

    def pred(self, content):
        # print("pred content:", content)
        if type(content[0]) == lark.Token:
            pred_type = content[0].value
        else:
            pred_type = content[0]
        # valence up to three, using None assignments to avoid downstream checks
        pred_arg1 = None
        pred_arg2 = None
        pred_arg3 = None

        if len(content) >= 3:
            # print('pred arg 1:', content[2])
            if type(content[2]) == lark.Token:
                pred_arg1 = content[2].value
            else:
                pred_arg1 = content[2]
        if len(content) >= 5:
            if type(content[4]) == lark.Token:
                pred_arg2 = content[4].value
            else:
                pred_arg2 = content[4]
        if len(content) >= 7:
            if type(content[6]) == lark.Token:
                pred_arg3 = content[6].value
            else:
                pred_arg3 = content[6]

        pred_dict = {'predicate': pred_type, 'arg1': pred_arg1, 'arg2': pred_arg2, 'arg3': pred_arg3}
        # print(pred_dict, "\n")

        return pred_dict

    def var(self, content):
        # print(content[0])
        return {'variable': content[0].value}


action_def_transformer = PDDLActionTransformer()

action_def = action_def_transformer.transform(parsed_action)

# print(action_def)

def pretty_action(action: dict):
    for key, value in action.items():
        print(key, value)

# pretty_action(action_def)

# PDDL DOMAIN
# Partially using domain to make type inheritance work (for now)

with open("pddl_domain.lark") as grammar_file:
    domain_grammar = grammar_file.read()

# print(domain_grammar)

domain_parser = Lark(domain_grammar, start="define")

test_pddl_domain = "test_pddl_domain.txt"

with open(test_pddl_domain) as domain_file:
    domain_raw = domain_file.read()


parsed_domain = domain_parser.parse(domain_raw)

# print(parsed_domain)


class PDDLDomainTransformer(Transformer):
    """PDDL domain definition transformer to convert Lark parse to python dict for further use.
    Method names must match grammar rule names, thus some rules have an added -p to distinguish their name from a python
    constant/type/default term string.
    """
    def define(self, content):
        # print("define cont:", content)

        # domain_def_dict = {'domain_name': content[1].value.lower()}
        domain_def_dict = dict()

        for cont in content:
            # print(type(cont))
            if type(cont) == lark.Token:
                # print("lark token:", cont.type, cont.value)
                pass
            else:
                # print("non-Token", cont)
                if 'domain_id' in cont:
                    domain_def_dict['domain_id'] = cont['domain_id']
                if 'types' in cont:
                    domain_def_dict['types'] = cont['types']

        # action: lark.Tree = content[0]
        # action_type = action.data  # main grammar rule the input was parsed as
        # action_content = action.children  # all parsed arguments of the action 'VP'

        # print("define returns:", domain_def_dict)
        return domain_def_dict
        # return content
        # pass

    def domain_id(self, content):
        # print("domain_id cont:", content)
        # print("domain_id return:", {'domain_id': content[-1].value})
        return {'domain_id': content[-1].value}

    def types(self, content):
        # print("types cont:", content)
        types_list = list()
        for cont in content:
            if 'type_list_element' in cont:
                types_list.append(cont)
        types_dict = dict()
        for type_list in types_list:
            # print(type_list)
            types_dict[f'{type_list["type_list_element"]}'] = type_list['items']
        # print("types return:", {'types': types_list})
        return {'types': types_dict}

    def type_list(self, content):
        # print(content)
        return {'type_list': content}

    def type_list_element(self, content):
        # print("type_list_item cont:", content)
        type_list_items = list()
        for item_element in content:
            if 'variable' in item_element:
                type_list_items.append(item_element)
            elif type(item_element) == lark.Token:
                if item_element.type == "WORDP":
                    type_list_items.append(item_element.value)
                elif item_element.type == "DASH":
                    break

        if content[-1].type == "WS":
            cat_name = content[-2].value
        else:
            cat_name = content[-1].value
        # print("type_list_item return:", {'type_list_item': cat_name, 'items': type_list_items})
        return {'type_list_element': cat_name, 'items': type_list_items}


    def parameters(self, content):
        parameter_list = None
        if type(content[0]) == lark.Token and content[0].type == "WS":
            parameter_list = content[1]
        # print("parameters:", parameter_list)

        return {'parameters': parameter_list}

    def precondition(self, content):
        # print("precond cont:", content)
        # print("precond cont:", content[1][1:])
        return {'precondition': content[1:-1]}

    def effect(self, content):
        # print("effect cont:", content)
        effect_dict = {'effect': content[1:-1]}
        # print("effect returns:", effect_dict)
        return effect_dict

    def forall(self, content):
        # print("forall cont:", content)
        iterated_object = content[2]
        # print("iterated object:", iterated_object)
        forall_body = content[4:]
        # print("forall body:", forall_body)

        forall_dict = {'forall': iterated_object, 'body': forall_body}
        # print("forall returns:", forall_dict)
        return forall_dict

    def when(self, content):
        # print("when cont:", content)
        when_items = list()
        for when_item in content:
            # ignore delimiters and whitespace:
            if type(when_item) == lark.Token and when_item.type in ["WHENL", "WS"]:
                pass
            else:
                when_items.append(when_item)
        when_dict = {'when': when_items}
        # print("when returns:", when_dict)
        return when_dict

    def andp(self, content):
        # print("andp cont:", content)
        and_items = list()
        for and_item in content:
            # ignore delimiters and whitespace:
            if type(and_item) == lark.Token and and_item.type in ["ANDL", "WS"]:
                pass
            else:
                and_items.append(and_item)
        and_dict = {'and': and_items}
        # print("andp returns:", and_dict, "\n")
        return and_dict

    def orp(self, content):
        # print("orp cont:", content)
        or_items = list()
        for or_item in content:
            # ignore delimiters and whitespace:
            if type(or_item) == lark.Token and or_item.type in ["ORL", "WS"]:
                pass
            else:
                or_items.append(or_item)
        or_dict = {'or': or_items}
        # print("orp returns:", or_dict, "\n")
        return or_dict

    def notp(self, content):
        # print("notp cont:", content)
        # (not X) always wraps only one item, hence:
        return {'not': content[2]}



    def equal(self, content):
        # print("equal cont:", content)
        # the (= X Y) can only ever take two arguments, thus directly accessing them:
        equal_dict = {'equal': [content[2], content[4]]}
        # print("equal returns:", equal_dict)
        return equal_dict

    def pred(self, content):
        # print("pred content:", content)
        if type(content[0]) == lark.Token:
            pred_type = content[0].value
        else:
            pred_type = content[0]
        # valence up to three, using None assignments to avoid downstream checks
        pred_arg1 = None
        pred_arg2 = None
        pred_arg3 = None

        if len(content) >= 3:
            # print('pred arg 1:', content[2])
            if type(content[2]) == lark.Token:
                pred_arg1 = content[2].value
            else:
                pred_arg1 = content[2]
        if len(content) >= 5:
            if type(content[4]) == lark.Token:
                pred_arg2 = content[4].value
            else:
                pred_arg2 = content[4]
        if len(content) >= 7:
            if type(content[6]) == lark.Token:
                pred_arg3 = content[6].value
            else:
                pred_arg3 = content[6]

        pred_dict = {'predicate': pred_type, 'arg1': pred_arg1, 'arg2': pred_arg2, 'arg3': pred_arg3}
        # print(pred_dict, "\n")

        return pred_dict

    def var(self, content):
        # print(content[0])
        return {'variable': content[0].value}


domain_def_transformer = PDDLDomainTransformer()

domain_def = domain_def_transformer.transform(parsed_domain)

# print("domain_def:", domain_def)




# PROCESSING

# action_def_source = "resources/definitions/basic_actions_v2.json"

class TestIF:
    def __init__(self, game_instance: dict):
        # game instance is the instance data as passed by the GameMaster class
        self.game_instance: dict = game_instance
        # surface strings (repr_str here) to spaceless internal identifiers:
        self.repr_str_to_type_dict: dict = dict()

        self.entity_types = dict()
        self.initialize_entity_types()

        self.room_types = dict()
        self.initialize_room_types()

        self.action_types = dict()
        self.initialize_action_types()

        # print(self.action_types)

        self.domain = dict()
        self.initialize_domain()
        # print("initialized domain:", self.domain)

        self.world_state: set = set()
        self.world_state_history: list = list()
        self.goal_state: set = set()
        self.goals_achieved: set = set()
        self.initialize_states_from_strings()

        # self.initialize_action_parsing(print_lark_grammar=verbose)

        # first prototype
        """
        self.action_types = dict()

        self.action_parser = Lark(action_grammar, start="action")
        parsed_action = self.action_parser.parse(action_raw)

        self.action_transformer = PDDLActionTransformer()
        action_def = self.action_transformer.transform(parsed_action)

        self.action_types[action_def['action_name'].lower()] = dict()
        for action_attribute in action_def:
            if not action_attribute == 'action_name':
                self.action_types[action_def['action_name'].lower()][action_attribute] = action_def[action_attribute]

        # print(self.action_types)
        """

    def load_json(self, json_file_path):
        with open(f"{json_file_path}.json", 'r', encoding='utf-8') as json_file:
            json_content = json.load(json_file)
        return json_content

    def initialize_entity_types(self):
        """
        Load and process entity types in this adventure.
        Definitions are loaded from external files.
        """
        # load entity type definitions in game instance:
        entity_definitions: list = list()
        for entity_def_source in self.game_instance["entity_definitions"]:
            entities_file = self.load_json(f"resources{os.sep}definitions{os.sep}{entity_def_source[:-5]}")
            entity_definitions += entities_file

        for entity_definition in entity_definitions:
            self.entity_types[entity_definition['type_name']] = dict()
            for entity_attribute in entity_definition:
                if entity_attribute == 'type_name':
                    # assign surface strings:
                    self.repr_str_to_type_dict[entity_definition['repr_str']] = entity_definition[entity_attribute]
                else:
                    # get all other attributes:
                    self.entity_types[entity_definition['type_name']][entity_attribute] = entity_definition[
                        entity_attribute]

    def initialize_room_types(self):
        """
        Load and process room types in this adventure.
        Definitions are loaded from external files.
        """
        # load room type definitions in game instance:
        room_definitions: list = list()
        for room_def_source in self.game_instance["room_definitions"]:
            rooms_file = self.load_json(f"resources{os.sep}definitions{os.sep}{room_def_source[:-5]}")
            room_definitions += rooms_file

        for room_definition in room_definitions:
            self.room_types[room_definition['type_name']] = dict()
            for room_attribute in room_definition:
                if room_attribute == 'type_name':
                    # assign surface strings:
                    self.repr_str_to_type_dict[room_definition['repr_str']] = room_definition[room_attribute]
                else:
                    # get all other attributes:
                    self.room_types[room_definition['type_name']][room_attribute] = room_definition[
                        room_attribute]

    def initialize_action_types(self):
        """
        Load and process action types in this adventure.
        Definitions are loaded from external files.
        """
        # load action type definitions in game instance:
        action_definitions: list = list()
        for action_def_source in self.game_instance["action_definitions"]:
            actions_file = self.load_json(f"resources{os.sep}definitions{os.sep}{action_def_source[:-5]}")
            action_definitions += actions_file

        for action_definition in action_definitions:
            self.action_types[action_definition['type_name']] = dict()
            # get all action attributes:
            for action_attribute in action_definition:
                if not action_attribute == 'type_name':
                    self.action_types[action_definition['type_name']][action_attribute] = action_definition[
                        action_attribute]

        for action_type in self.action_types:
            # print("action_type:", action_type)
            cur_action_type = self.action_types[action_type]

            if 'pddl' in cur_action_type:
                # print("cur_action_type:", cur_action_type)
                # print("cur_action_type['name']:", cur_action_type['name'])
                # print(cur_action_type['pddl'])
                parsed_action_pddl = action_parser.parse(cur_action_type['pddl'])
                processed_action_pddl = action_def_transformer.transform(parsed_action_pddl)
                # print(processed_action_pddl)
                cur_action_type['interaction'] = processed_action_pddl
            else:
                raise KeyError

            # convert fact to change from string to tuple:
            # cur_action_type['object_post_state'] = fact_str_to_tuple(cur_action_type['object_post_state'])

    def initialize_domain(self):
        """Load and process the domain(s) used in this adventure.
        Definitions are loaded from external files.
        """
        # load domain definitions in game instance:
        domain_definitions: list = list()
        for domain_def_source in self.game_instance["domain_definitions"]:
            domain_def_raw = self.load_json(f"resources{os.sep}definitions{os.sep}{domain_def_source[:-5]}")
            # print("domain_def_raw:", domain_def_raw)
            # print("domain_def_raw pddl_domain:", domain_def_raw['pddl_domain'])
            domain_definitions.append(domain_def_raw['pddl_domain'])

        # print("domain_definitions", domain_definitions)

        for domain_definition in domain_definitions:
            # print("domain_definition:", domain_definition)
            parsed_domain_pddl = domain_parser.parse(domain_definition)
            processed_domain_pddl = domain_def_transformer.transform(parsed_domain_pddl)
            # print("processed_domain_pddl:", processed_domain_pddl)

        # for now assume only one domain definition:
        self.domain = processed_domain_pddl
        # multiple domain definitions would need proper checks/unification

        # TODO?: full type inheritance as dict or the like?

        # print("domain:", self.domain)
        # print("domain types:", self.domain['types'])

        # TRAIT TYPES FROM ENTITY DEFINITIONS
        # print("self.entity_types:", self.entity_types)
        # print("self.domain:", self.domain)
        # print(self.domain['types']['entity'])
        trait_type_dict = dict()
        for entity_type in self.domain['types']['entity']:
            # print("domain entity type:", entity_type, "; type defined:", self.entity_types[entity_type])
            if 'traits' in self.entity_types[entity_type]:
                # print("defined type traits:", self.entity_types[entity_type]['traits'])
                for trait in self.entity_types[entity_type]['traits']:
                    if trait not in trait_type_dict:
                        trait_type_dict[trait] = [entity_type]
                    else:
                        trait_type_dict[trait].append(entity_type)
                    if trait not in self.domain['types']:
                        self.domain['types'][trait] = [entity_type]
                    else:
                        self.domain['types'][trait].append(entity_type)
        # print("trait type dict:", trait_type_dict)
        # print(self.domain['types'])

        # REVERSE SUBTYPE/SUPERTYPE DICT
        supertype_dict = dict()
        for supertype, subtypes in self.domain['types'].items():
            # print("supertype:", supertype, "subtypes:", subtypes)
            for subtype in subtypes:
                if subtype not in supertype_dict:
                    supertype_dict[subtype] = [supertype]
                else:
                    supertype_dict[subtype].append(supertype)

        # print(supertype_dict)
        self.domain['supertypes'] = supertype_dict
        # print("domain:", self.domain)

    def initialize_states_from_strings(self):
        """
        Initialize the world state set from instance data.
        Converts List[Str] world state format into Set[Tuple].
        """
        for fact_string in self.game_instance['initial_state']:
            self.world_state.add(fact_str_to_tuple(fact_string))

        # NOTE: The following world state augmentations are left in here to make manual adventure creation/modification
        # convenient. Initial adventure world states generated with the clingo adventure generator already cover these
        # augmentations. Due to the world state being a set of tuples, the augmentations done here simply unify.

        # facts to add are gathered in a set to prevent duplicates
        facts_to_add = set()

        # add trait facts for objects:
        for fact in self.world_state:
            if fact[0] == 'type':
                # add trait facts by entity type:
                # print(fact)
                if 'traits' in self.entity_types[fact[2]]:
                    type_traits: list = self.entity_types[fact[2]]['traits']
                    for type_trait in type_traits:
                        facts_to_add.add((type_trait, fact[1]))

        # add floors to rooms:
        for fact in self.world_state:
            if fact[0] == 'room':
                facts_to_add.add(('type', f'{fact[1]}floor1', 'floor'))
                # add floor:
                facts_to_add.add(('at', f'{fact[1]}floor1', fact[1]))

        self.world_state = self.world_state.union(facts_to_add)

        # dict with the type for each entity instance in the adventure:
        self.inst_to_type_dict = dict()
        # get entity instance types from world state:
        for fact in self.world_state:
            # entity instance to entity type mapping:
            if fact[0] == 'type' or fact[0] == 'room':
                self.inst_to_type_dict[fact[1]] = fact[2]

        # dict with the type for each room instance in the adventure:
        self.room_to_type_dict = dict()
        # get room instance types from world state:
        for fact in self.world_state:
            # room instance to room type mapping:
            if fact[0] == 'room':
                self.room_to_type_dict[fact[1]] = fact[2]

        # put 'supported' items on the floor if they are not 'in' or 'on':
        for fact in self.world_state:
            if fact[1] in self.inst_to_type_dict:
                if self.inst_to_type_dict[fact[1]] in self.entity_types:
                    pass
            if fact[0] == 'at' and ('needs_support', fact[1]) in self.world_state:
                currently_supported = False
                for state_pred2 in self.world_state:
                    if state_pred2[0] == 'on' and state_pred2[1] == fact[1]:
                        currently_supported = True
                        break
                    if state_pred2[0] == 'in' and state_pred2[1] == fact[1]:
                        currently_supported = True
                        break
                if not currently_supported:
                    facts_to_add.add(('on', fact[1], f'{fact[2]}floor'))

        # make items that are not 'in' closed containers or 'in' inventory 'accessible':
        for fact in self.world_state:
            if fact[1] in self.inst_to_type_dict:
                if self.inst_to_type_dict[fact[1]] in self.entity_types:
                    pass
            if fact[0] == 'in' and ('container', fact[2]) in self.world_state:
                container_currently_open = False
                for state_pred2 in self.world_state:
                    if state_pred2[0] == 'open' and state_pred2[1] == fact[2]:
                        container_currently_open = True
                        break
                if container_currently_open:
                    facts_to_add.add(('accessible', fact[1]))
            if fact[0] == 'in' and fact[2] == 'inventory':
                # print(f"{fact[1]} in inventory!")
                facts_to_add.add(('accessible', fact[1]))
            if fact[0] == 'on' and ('support', fact[2]) in self.world_state:
                facts_to_add.add(('accessible', fact[1]))
            if fact[0] == 'type' and ('needs_support', fact[1]) not in self.world_state and fact[2] not in ("floor", "player"):
                facts_to_add.add(('accessible', fact[1]))

        self.world_state = self.world_state.union(facts_to_add)
        # add initial world state to world state history:
        self.world_state_history.append(deepcopy(self.world_state))
        """
        # get goal state fact set:
        for fact_string in self.game_instance['goal_state']:
            self.goal_state.add(fact_str_to_tuple(fact_string))
        """

    def _get_inst_str(self, inst) -> str:
        """Get a full string representation of an entity or room instance with adjectives."""
        inst_adjs = list()
        # get instance adjectives from adj facts:
        for fact in self.world_state:
            if fact[0] == 'adj' and fact[1] == inst:
                inst_adjs.append(fact[2])
        # get type of instance:
        if inst in self.inst_to_type_dict:
            inst_type: str = self.inst_to_type_dict[inst]
        elif inst in self.room_to_type_dict:
            inst_type: str = self.room_to_type_dict[inst]
        # get surface string for instance type:
        if inst_type in self.entity_types:
            inst_str: str = self.entity_types[inst_type]['repr_str']
        elif inst_type in self.room_types:
            inst_str: str = self.room_types[inst_type]['repr_str']
        # combine into full surface string:
        inst_adjs.append(inst_str)
        adj_str = " ".join(inst_adjs)

        return adj_str

    def get_player_room_contents(self) -> List:
        """
        Get all contents of the current player location room.
        """
        player_room = self.get_player_room()
        room_contents = list()
        for fact in self.world_state:
            # get all entities 'at' the player's location, except the player themselves:
            if fact[0] == 'at' and fact[2] == player_room and not fact[1] == 'player1':
                room_contents.append(fact[1])

        return room_contents

    def get_player_room_contents_visible(self) -> List:
        """
        Get the visible contents of the current room.
        Entities 'in' closed entities are not returned.
        In v2, this is NO LONGER used to determine if an entity is accessible for interaction - this is handled via PDDL
        action definition now.
        """
        room_contents = self.get_player_room_contents()
        visible_contents = list()
        for thing in room_contents:
            # do not access entities that are hidden by type:
            if 'hidden' in self.entity_types[self.inst_to_type_dict[thing]]:
                continue

            # do not access entities inside closed containers:
            contained_in = None
            for fact in self.world_state:
                # check if entity is 'in' closed container:
                if fact[0] == 'in' and fact[1] == thing:
                    contained_in = fact[2]
                    # print(f"{thing} is contained in {contained_in}")
                    for state_pred2 in self.world_state:
                        if state_pred2[0] == 'closed' and state_pred2[1] == contained_in:
                            # not visible/accessible in closed container
                            break
                        elif state_pred2[0] == 'open' and state_pred2[1] == contained_in:
                            visible_contents.append(thing)
                            break
                        elif state_pred2[1] == 'inventory' and state_pred2[1] == contained_in:
                            # inventory content is not visible
                            break
            if contained_in:
                continue
            visible_contents.append(thing)

        return visible_contents

    def get_player_room(self) -> str:
        """
        Get the current player location's internal room string ID.
        """
        for fact in self.world_state:
            if fact[0] == 'at' and fact[1] == 'player1':
                player_room = fact[2]
                break

        return player_room

    def get_player_room_exits(self) -> List:
        """
        Get all passages in the current room.
        """
        player_room = self.get_player_room()
        room_exits = list()
        for fact in self.world_state:
            # passage facts are 'exit' in the adventure/instance format
            if fact[0] == 'exit' and fact[1] == player_room:
                room_exits.append(fact[2])

        return room_exits

    def get_full_room_desc(self) -> str:
        """
        Creates and returns full description of the room the player is at.
        """
        # get player room:
        player_room = self.get_player_room()
        # create room description start:
        room_repr_str = self.room_types[self.room_to_type_dict[player_room]]['repr_str']
        # using simple type surface string due to v1 not having multiple rooms of the same type:
        player_at_str = f"You are in a {room_repr_str} now."

        # get visible room content:
        internal_visible_contents = self.get_player_room_contents_visible()
        # print("internal_visible_contents:", internal_visible_contents)

        # convert to types:
        visible_contents = [self._get_inst_str(instance) for instance in internal_visible_contents]

        # create visible room content description:
        visible_contents_str = str()
        if len(visible_contents) >= 3:
            comma_list = ", a ".join(visible_contents[:-1])
            and_last = f"and a {visible_contents[-1]}"
            visible_contents_str = f"There are a {comma_list} {and_last}."
            visible_contents_str = " " + visible_contents_str
        elif len(visible_contents) == 2:
            visible_contents_str = f"There are a {visible_contents[0]} and a {visible_contents[1]}."
            visible_contents_str = " " + visible_contents_str
        elif len(visible_contents) == 1:
            visible_contents_str = f"There is a {visible_contents[0]}."
            visible_contents_str = " " + visible_contents_str

        # get predicate state facts of visible objects and create textual representations:
        visible_content_state_strs = list()
        for thing in internal_visible_contents:
            for fact in self.world_state:
                if fact[0] == 'closed' and fact[1] == thing:
                    visible_content_state_strs.append(f"The {self._get_inst_str(thing)} is closed.")
                elif fact[0] == 'open' and fact[1] == thing:
                    visible_content_state_strs.append(f"The {self._get_inst_str(thing)} is open.")
                if fact[0] == 'in' and fact[1] == thing:
                    visible_content_state_strs.append(f"The {self._get_inst_str(thing)} is in the {self._get_inst_str(fact[2])}.")
                if fact[0] == 'on' and fact[1] == thing:
                    visible_content_state_strs.append(f"The {self._get_inst_str(thing)} is on the {self._get_inst_str(fact[2])}.")

        if visible_content_state_strs:
            visible_content_state_combined = " ".join(visible_content_state_strs)
            visible_content_state_combined = " " + visible_content_state_combined
        else:
            visible_content_state_combined = str()

        # get room passages and create textual representation:
        room_exits = self.get_player_room_exits()
        exits_str = str()
        if len(room_exits) == 1:
            exits_str = f" There is a passage to a {self._get_inst_str(room_exits[0])} here."
        elif len(room_exits) == 2:
            exits_str = (f" There are passages to a {self._get_inst_str(room_exits[0])} and a "
                         f"{self._get_inst_str(room_exits[1])} here.")
        elif len(room_exits) >= 3:
            comma_exits = ", a ".join([self._get_inst_str(room_exit) for room_exit in room_exits[:-1]])
            exits_str = f" There are passages to a {comma_exits} and a {self._get_inst_str(room_exits[-1])} here."

        # combine full room description:
        room_description = f"{player_at_str}{visible_contents_str}{visible_content_state_combined}{exits_str}"

        return room_description

    def get_inventory_content(self) -> list:
        inventory_content = list()
        for fact in self.world_state:
            if fact[0] == 'in' and fact[2] == 'inventory':
                inventory_content.append(fact[1])

        return inventory_content

    def get_container_content(self, container_id) -> list:
        container_content = list()
        for fact in self.world_state:
            if fact[0] == 'in' and fact[2] == container_id:
                container_content.append(fact[1])

        return container_content

    def get_container_content_desc(self, container_id) -> str:
        container_repr = self._get_inst_str(container_id)
        container_content = self.get_container_content(container_id)
        container_item_cnt = len(container_content)
        if container_item_cnt == 0:
            content_desc = f"The {container_repr} is empty."
            return content_desc
        elif container_item_cnt == 1:
            inv_str = f"a {self._get_inst_str(container_content[0])}"
            content_desc = f"In the {container_repr} there is {inv_str}."
        else:
            content_strs = [f"a {self._get_inst_str(container_item)}" for container_item in container_content]
            content_str = ", ".join(content_strs[:-1])
            content_str += f" and {content_strs[-1]}"
            content_desc = f"In the {container_repr} there are {content_str}."

        return content_desc

    def get_inventory_desc(self) -> str:
        """Get a text description of the current inventory content.
        Used for feedback for 'take' action.
        """
        inventory_content: list = self.get_inventory_content()
        inv_list = list(inventory_content)
        inv_item_cnt = len(inv_list)
        if inv_item_cnt == 0:
            inv_desc = "Your inventory is empty."
            return inv_desc
        elif inv_item_cnt == 1:
            inv_str = f"a {self._get_inst_str(inv_list[0])}"
        else:
            inv_strs = [f"a {self._get_inst_str(inv_item)}" for inv_item in inv_list]
            inv_str = ", ".join(inv_strs[:-1])
            inv_str += f" and {inv_strs[-1]}"
        inv_desc = f"In your inventory you have {inv_str}."

        return inv_desc

    def get_entity_desc(self, entity) -> str:
        """Get a full description of an entity.
        Used for the EXAMINE action.
        """
        # get inventory description if inventory is examined:
        if entity == "inventory":
            return self.get_inventory_desc()

        # get entity ID:
        # NOTE: This assumes only one instance of any entity type is in the adventure!
        entity_id = str()
        for fact in self.world_state:
            if fact[0] == 'type' and fact[2] == entity:
                entity_id = fact[1]
                break
        print("entity ID found:", entity_id)
        entity_desc_list = list()
        # get all entity states to describe:
        for fact in self.world_state:
            if fact[1] == entity_id:
                print("entity state fact:", fact)
                # describe 'openable' entity states:
                if fact[0] == "openable":
                    openable_entity: str = fact[1]
                    while openable_entity.endswith(("0","1","2","3","4","5","6","7","8","9")):
                        openable_entity = openable_entity[:-1]
                    print("openable_entity:", openable_entity)
                    for fact2 in self.world_state:
                        if fact2[1] == entity_id and fact2[0] in ("open", "closed"):
                            openable_state = fact2[0]
                            print("openable_state:", openable_state)
                            break
                    openable_desc = f"The {openable_entity} is openable and currently {openable_state}."
                    entity_desc_list.append(openable_desc)
                # describe 'takeable' entities:
                if fact[0] == "takeable":
                    takeable_entity: str = fact[1]
                    while takeable_entity.endswith(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9")):
                        takeable_entity = takeable_entity[:-1]
                    print("takeable_entity:", takeable_entity)
                    takeable_desc = f"The {takeable_entity} is takeable."
                    entity_desc_list.append(takeable_desc)
                # describe the container or support state of 'needs_support' entities:
                if fact[0] == "needs_support":
                    needs_support_entity: str = fact[1]
                    while needs_support_entity.endswith(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9")):
                        needs_support_entity = needs_support_entity[:-1]
                    print("needs_support_entity:", needs_support_entity)

                    for fact2 in self.world_state:
                        if fact2[1] == entity_id and fact2[0] in ("on", "in"):
                            support_state = fact2[0]
                            print("support_state:", support_state)
                            supporter_entity = fact2[2]
                            print("supporter_entity:", supporter_entity)
                            break

                    if supporter_entity == "inventory":
                        supporter_entity = "your inventory"
                    else:
                        while supporter_entity.endswith(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9")):
                            supporter_entity = supporter_entity[:-1]
                        supporter_entity = f"the {supporter_entity}"

                    needs_support_desc = f"The {needs_support_entity} is {support_state} {supporter_entity}."
                    entity_desc_list.append(needs_support_desc)


                if fact[0] == "container":
                    container_entity: str = fact[1]
                    while container_entity.endswith(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9")):
                        container_entity = container_entity[:-1]
                    print("container_entity:", container_entity)

                    contained_entities = list()

                    for fact2 in self.world_state:
                        if len(fact2) == 3:
                            if fact2[2] == entity_id and fact2[0] == "in":
                                # print(fact2)
                                contained_entity = fact2[1]
                                print("contained_entity:", contained_entity)
                                # check if contained entity is accessible:
                                if ('accessible', contained_entity) not in self.world_state:
                                    continue
                                print("contained_entity is accessible")

                                while contained_entity.endswith(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9")):
                                    contained_entity = contained_entity[:-1]
                                print("contained_entity:", contained_entity)
                                contained_entities.append(f"a {contained_entity}")

                    if ('closed', fact[1]) in self.world_state:
                        container_content_desc = f"You can't see the {container_entity}'s contents because it is closed."
                    else:
                        if len(contained_entities) == 0:
                            container_content_desc = f"The {container_entity} is empty."
                        elif len(contained_entities) == 1:
                            container_content_desc = f"There is {contained_entities[0]} in the {container_entity}."
                        elif len(contained_entities) == 2:
                            container_content_desc = f"There are {contained_entities[0]} and {contained_entities[1]} in the {container_entity}."
                        elif len(contained_entities) >= 3:
                            container_content_desc = f"There are {', '.join(contained_entities[:-1])} and {contained_entities[-1]} in the {container_entity}."

                    entity_desc_list.append(container_content_desc)

                if fact[0] == "support":
                    support_entity: str = fact[1]
                    while support_entity.endswith(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9")):
                        support_entity = support_entity[:-1]
                    print("support_entity:", support_entity)

                    supported_entities = list()

                    for fact2 in self.world_state:
                        if len(fact2) == 3:
                            if fact2[2] == entity_id and fact2[0] == "on":
                                # print(fact2)
                                supported_entity = fact2[1]
                                print("supported_entity:", supported_entity)

                                while supported_entity.endswith(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9")):
                                    supported_entity = supported_entity[:-1]
                                print("supported_entity:", supported_entity)
                                supported_entities.append(f"a {supported_entity}")

                    if len(supported_entities) == 0:
                        support_content_desc = f"There is nothing on the {support_entity}."
                    elif len(supported_entities) == 1:
                        support_content_desc = f"There is {supported_entities[0]} on the {support_entity}."
                    elif len(supported_entities) == 2:
                        support_content_desc = f"There are {supported_entities[0]} and {supported_entities[1]} on the {support_entity}."
                    elif len(supported_entities) >= 3:
                        support_content_desc = f"There are {', '.join(supported_entities[:-1])} and {supported_entities[-1]} on the {support_entity}."

                    entity_desc_list.append(support_content_desc)

                # TODO?: room description?

        return " ".join(entity_desc_list)




    def check_fact(self, fact_tuple) -> bool:
        """Check if a fact tuple is in the world state."""
        # print("Checking for", fact_tuple)
        # always return True for fact tuples with None, as this marks optional action arguments
        if None in fact_tuple:
            return True

        if fact_tuple in self.world_state:
            # print(fact_tuple, "in world state!")
            return True
        else:
            return False

    def predicate_to_tuple(self, predicate, variable_map) -> tuple:
        """Convert a PDDL predicate object to a world state tuple.
        Resolves variables as well.
        Resolves type action/predicate arguments assuming single type instance.
        """

        predicate_type = predicate['predicate']

        predicate_arg1 = predicate['arg1']
        if 'variable' in predicate_arg1:
            predicate_arg1 = variable_map[predicate_arg1['variable']]
            # print("filled when condition variable:", when_condition_arg1)
            # for now:
            if type(predicate_arg1) == list:
                when_condition_arg1 = predicate_arg1[0]

        predicate_list = [predicate_type, predicate_arg1]

        predicate_arg2 = None
        if predicate['arg2']:
            predicate_arg2 = predicate['arg2']
            if 'variable' in predicate_arg2:
                predicate_arg2 = variable_map[predicate_arg2['variable']]
                # print("filled when condition variable:", when_condition_arg2)
            predicate_list.append(predicate_arg2)

        predicate_arg3 = None
        if predicate['arg3']:
            predicate_arg3 = predicate['arg3']
            if 'variable' in predicate_arg3:
                predicate_arg3 = variable_map[predicate_arg3['variable']]
                # print("filled when condition variable:", when_condition_arg3)
            predicate_list.append(predicate_arg3)

        # print("when_condition_list:", when_condition_list)
        predicate_tuple = tuple(predicate_list)
        # print("when_condition_tuple:", when_condition_tuple)

        # assume that action arguments that don't end in numbers or "floor" are type words:
        for tuple_idx, tuple_arg in enumerate(predicate_tuple[1:]):  # first tuple item is always a predicate
            # print("tuple_arg:", tuple_arg)
            type_matched_instances = list()
            if tuple_arg:
                if not tuple_arg.endswith(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9")):
                    # print(f"{tuple_arg} is not a type instance ID!")
                    # go over world state facts to find room or type predicate:
                    for fact in self.world_state:
                        # check for predicate fact matching action argument:
                        if fact[0] == "room" or fact[0] == "type":
                            if fact[2] == tuple_arg:
                                # print(f"{fact[0]} predicate fact found:", fact)
                                type_matched_instances.append(fact[1])
                        # TODO?: fail if there is no type-fitting instance in world state?

                    # print(type_matched_instances)

                    # NOTE: This assumes all room and entity types have only a single instance in the adventure!

                    # replace corresponding variable_map value with instance ID:
                    for variable in variable_map:
                        if variable_map[variable] == tuple_arg:
                            variable_map[variable] = type_matched_instances[0]
                            # print("instance-filled variable_map:", variable_map)

                    # create fact tuple to check for:
                    match len(predicate_tuple):
                        case 2:
                            predicate_tuple = (predicate_tuple[0], type_matched_instances[0])
                        case 3:
                            if tuple_idx == 0:
                                predicate_tuple = (predicate_tuple[0], type_matched_instances[0], predicate_tuple[2])
                            elif tuple_idx == 1:
                                predicate_tuple = (predicate_tuple[0], predicate_tuple[1], type_matched_instances[0])
                        case 4:
                            if tuple_idx == 0:
                                predicate_tuple = (
                                predicate_tuple[0], type_matched_instances[0], predicate_tuple[2], predicate_tuple[3])
                            elif tuple_idx == 1:
                                predicate_tuple = (
                                predicate_tuple[0], predicate_tuple[1], type_matched_instances[0], predicate_tuple[3])
                            elif tuple_idx == 2:
                                predicate_tuple = (
                                predicate_tuple[0], predicate_tuple[1], predicate_tuple[2], type_matched_instances[0])

        # print("predicate_tuple post-instance resolution:", predicate_tuple)

        return predicate_tuple

    def check_conditions(self, conditions, variable_map, check_precon_idx = True, precon_trace = True) -> bool:
        """Check if a passed condition 'and'/'or' clause is true.
        Full action preconditions must have a root 'and' clause!
        """
        # print()
        # print("check_conditions input conditions:", conditions)

        if 'not' in conditions:
            # print("'Not' phrase condition.")

            not_dict = {'not': dict()}

            conditions_polarity = False
            inner_condition = conditions['not']
            # print("'not' phrase inner_condition:", inner_condition)
            inner_condition_is_fact = self.check_conditions(inner_condition, variable_map, check_precon_idx=check_precon_idx, precon_trace=precon_trace)
            # print("inner_condition_is_fact:", inner_condition_is_fact)

            if precon_trace:
                not_dict['not'] = inner_condition_is_fact
                not_true = False
                if inner_condition_is_fact['checks_out'] == conditions_polarity:
                    not_true = True
                not_dict['checks_out'] = not_true
                self.precon_trace.append(not_dict)

                # print("not_dict:", not_dict)

                return not_dict

            if inner_condition_is_fact == conditions_polarity:
                return True
            else:
                return False

        if 'predicate' in conditions:
            # print("Bare predicate condition:", conditions)
            predicate_tuple = self.predicate_to_tuple(conditions, variable_map)
            # print("predicate_tuple:", predicate_tuple)
            if check_precon_idx:
                # print("Current self.precon_idx:", self.precon_idx)
                pass
            is_fact = self.check_fact(predicate_tuple)
            # print("is_fact:", is_fact)
            if check_precon_idx:
                self.precon_idx += 1
                self.precon_tuples.append((predicate_tuple, is_fact, self.precon_idx))

            if precon_trace:
                predicate_dict = {'predicate_tuple': predicate_tuple, 'checks_out': is_fact, 'precon_idx': self.precon_idx}
                # print("predicate_dict:", predicate_dict)
                return predicate_dict

            return is_fact

        if 'and' in conditions:
            and_dict = {'and': list()}

            and_conditions_checklist = list()
            # print("And conditions:", conditions)
            conditions = conditions['and']
            # print("Extracted and conditions list:", conditions)
            for and_condition in conditions:
                # print("and_condition:", and_condition)

                # checks_out = self.check_conditions(and_condition, variable_map, check_precon_idx=check_precon_idx, precon_trace=precon_trace)

                checks_out = self.check_conditions(and_condition, variable_map, check_precon_idx=check_precon_idx, precon_trace=precon_trace)
                # print("and item checks_out:", checks_out)
                # since all facts need to check out for 'and' clauses, immediately return failure:
                # if not checks_out:
                #    return False
                if precon_trace:
                    and_conditions_checklist.append(checks_out['checks_out'])
                    and_dict['and'].append(checks_out)
                else:
                    and_conditions_checklist.append(checks_out)
                # print()
            # print("and_conditions_checklist:", and_conditions_checklist)

            # check if all conditions are true:
            if precon_trace:
                and_phrase_true = False
                if not False in and_conditions_checklist:
                    and_phrase_true = True
                and_dict['checks_out'] = and_phrase_true
                self.precon_trace.append(and_dict)
                # print("and_dict:", and_dict)
                return and_dict
            else:
                if not False in and_conditions_checklist:
                    return True
                else:
                    return False

        if 'or' in conditions:

            or_dict = {'or': list()}

            or_conditions_checklist = list()
            # print("Or conditions:", conditions)
            conditions = conditions['or']
            # print("Extracted or conditions list:", conditions)
            for or_condition in conditions:
                # print("or_condition:", or_condition)
                checks_out = self.check_conditions(or_condition, variable_map, check_precon_idx=check_precon_idx, precon_trace=precon_trace)
                # print("or item checks_out:", checks_out)

                if precon_trace:
                    or_conditions_checklist.append(checks_out['checks_out'])
                    # print("or_conditions_checklist:", or_conditions_checklist)
                    or_dict['or'].append(checks_out)
                else:
                    or_conditions_checklist.append(checks_out)
                # print()
            # print("or_conditions_checklist:", or_conditions_checklist)

            # check if any condition is true:
            if precon_trace:
                or_phrase_true = False
                # print("or_conditions_checklist:", or_conditions_checklist)
                if True in or_conditions_checklist:
                    or_phrase_true = True
                or_dict['checks_out'] = or_phrase_true
                self.precon_trace.append(or_dict)
                return or_dict
            else:
                if True in or_conditions_checklist:
                    return True
                else:
                    return False


        # NOTE: Handling forall conditions not implemented due to time constraints.

        # print()

        return False

    def resolve_forall(self, forall_clause, variable_map):
        # print("forall effect:", forall_clause)
        forall_type = forall_clause['forall']
        # print("forall_type:", forall_type)

        forall_results = {'added': [], 'removed': []}

        forall_variable_map = dict()  # all values can be expected to be lists

        # handle single-predicate forall:
        if 'predicate' in forall_type:
            # print()
            forall_predicate = forall_type['predicate']
            if 'variable' in forall_predicate:
                # since this is no type_list, supply list of all __entities__:
                all_entities_list = [fact[1] for fact in self.world_state if fact[0] == 'type']

                # NOTE: This assumes that forall clauses will only iterate over entities, NOT rooms!

                # print("all_entities_list:", all_entities_list)
                forall_variable_map[forall_predicate['variable']] = all_entities_list
                forall_items = all_entities_list
        elif 'type_list' in forall_type:
            # TODO?: iterate over multiple type list variables?
            print("Type list forall_type:", forall_type)
            forall_type_list = forall_type['type_list']
            print("forall_type_list:", forall_type_list)
            for type_list_element in forall_type_list:
                type_list_type = type_list_element['type_list_element']
                for type_list_item in type_list_element['items']:
                    print("type_list_item:", type_list_item)
                    if 'variable' in type_list_item:
                        type_list_item_variable = type_list_item['variable']
                        print("type_list_item_variable:", type_list_item_variable)
                        # get all type-matched objects:
                        type_matched_objects = list()
                        for fact in self.world_state:
                            # TODO: use domain type definitions, employ object type inheritance
                            if fact[0] == type_list_type:  # relies on type facts for now
                                type_matched_objects.append(fact[1])
                        # assign all matched objects to forall variable map:
                        forall_variable_map[type_list_item_variable] = type_matched_objects

        print("forall_variable_map:", forall_variable_map)

        # NOTE: For now only covering forall with a single variable/type to iterate over, due to time constraints.

        for iterated_variable, iterated_values in forall_variable_map.items():
            # print("iterated_variable:", iterated_variable)
            # print("iterated_values:", iterated_values)
            for iterated_object in iterated_values:
                # print("iterated_object:", iterated_object)
                # create individual variable map for this iterated object:
                iteration_forall_variable_map = dict()
                for key, value in variable_map.items():
                    iteration_forall_variable_map[key] = value
                iteration_forall_variable_map[iterated_variable] = iterated_object
                # print("iteration_forall_variable_map:", iteration_forall_variable_map)

                # resolve forall body for iterated object:
                forall_body = forall_clause['body']
                # print("forall_body:", forall_body)

                for forall_body_element in forall_body:
                    # print("forall_body_element:", forall_body_element)
                    if 'when' in forall_body_element:
                        # print("When clause in forall body element:", forall_body_element['when'])
                        # print("When clause forall body element:", forall_body_element)
                        when_results = self.resolve_when(forall_body_element, iteration_forall_variable_map)
                        # print("when_results:", when_results)
                        forall_results['added'] += when_results['added']
                        forall_results['removed'] += when_results['removed']

                    if 'and' in forall_body_element:
                        # print("And clause forall body element:", forall_body_element)
                        # print("And clause in forall body element(s):", forall_body_element['and'])

                        and_items = forall_body_element['and']

                        for and_item in and_items:
                            # print("and_item:", and_item)
                            if 'predicate' in and_item or 'not' in and_item:
                                # print("Bare predicate or 'not' predicate item.")
                                and_item_results = self.resolve_effect(and_item, iteration_forall_variable_map)
                                # print("and_item_results:", and_item_results)
                                forall_results['added'] += and_item_results['added']
                                forall_results['removed'] += and_item_results['removed']
                            if 'when' in and_item:
                                when_results = self.resolve_when(and_item, iteration_forall_variable_map)
                                forall_results['added'] += when_results['added']
                                forall_results['removed'] += when_results['removed']
                            # print()

                    # TODO?: handle single-predicate forall bodies? -> would need grammar coverage

        # print("forall_results:", forall_results)

        return forall_results

    def resolve_when(self, when_clause, variable_map):
        when_results = {'added': [], 'removed': []}

        # when_items = when_clause['when']
        # get actual content:
        when_clause = when_clause['when']

        # print("when_clause:", when_clause)
        # print("variable_map for when clause:", variable_map)

        when_conditions_fulfilled = False

        when_conditions = when_clause[0]
        # print("when_conditions pre-and/or:", when_conditions)

        checked_conditions = self.check_conditions(when_conditions, variable_map, check_precon_idx=False, precon_trace=False)
        # print("checked_conditions:", checked_conditions)

        """
        when_conditions_type = "predicate"
        if 'and' in when_conditions:
            when_conditions_type = "and"
            when_conditions = when_conditions['and']
        elif 'or' in when_conditions:
            when_conditions_type = "or"
            when_conditions = when_conditions['or']

        if when_conditions_type in ["and", "or"]:
            # print("when_conditions after and/or:", when_conditions)
            pass


        if when_conditions_type == "and":
            for when_condition in when_conditions:
                print("and when_condition:", when_condition)
                # TODO: handle and-clause when conditions
                pass
        elif when_conditions_type == "or":
            for when_condition in when_conditions:
                print("or when_condition:", when_condition)
                # TODO: handle or-clause when conditions
                pass
        elif when_conditions_type == "predicate":
            # print("single-predicate when_conditions:", when_conditions)
            when_condition_predicate = when_conditions['predicate']

            when_condition_arg1 = when_conditions['arg1']
            if 'variable' in when_condition_arg1:
                when_condition_arg1 = variable_map[when_condition_arg1['variable']]
                # print("filled when condition variable:", when_condition_arg1)
                # for now:
                if type(when_condition_arg1) == list:
                    when_condition_arg1 = when_condition_arg1[0]

            when_condition_list = [when_condition_predicate, when_condition_arg1]

            when_condition_arg2 = None
            if when_conditions['arg2']:
                when_condition_arg2 = when_conditions['arg2']
                if 'variable' in when_condition_arg2:
                    when_condition_arg2 = variable_map[when_condition_arg2['variable']]
                    # print("filled when condition variable:", when_condition_arg2)
                when_condition_list.append(when_condition_arg2)

            when_condition_arg3 = None
            if when_conditions['arg3']:
                when_condition_arg3 = when_conditions['arg3']
                if 'variable' in when_condition_arg3:
                    when_condition_arg3 = variable_map[when_condition_arg3['variable']]
                    # print("filled when condition variable:", when_condition_arg3)
                when_condition_list.append(when_condition_arg3)

            # print("when_condition_list:", when_condition_list)
            when_condition_tuple = tuple(when_condition_list)
            # print("when_condition_tuple:", when_condition_tuple)

            # check if condition is world state fact:
            if when_condition_tuple in self.world_state:
                when_conditions_fulfilled = True
        """


        # if when_conditions_fulfilled:
        if checked_conditions:
            # print("When conditions fulfilled!")
            when_effects = when_clause[1]
            # print("when_effects:", when_effects)
            if 'and' in when_effects:
                when_effects = when_effects['and']
            else:
                # put single-predicate effect in list for uniform handling:
                when_effects = [when_effects]
            # print("when_effects after 'and' handling:", when_effects)

            for when_effect in when_effects:
                # print("when_effect:", when_effect)
                resolve_effect_results = self.resolve_effect(when_effect, variable_map)
                # print("resolve_effect_results", resolve_effect_results)
                when_results['added'] += resolve_effect_results['added']
                when_results['removed'] += resolve_effect_results['removed']
        else:
            # print("When conditions NOT fulfilled!")
            pass

        # print("when_results:", when_results)

        return when_results

    def resolve_effect(self, effect, variable_map):
        """Add or remove fact from world state based on passed effect object."""
        # print("effect passed to resolve_effect:", effect)

        resolve_effect_results = {'added': [], 'removed': []}

        effect_polarity = True
        if 'not' in effect:
            effect_polarity = False
            effect = effect['not']

        effect_list = [effect['predicate'], effect['arg1']]  # effect predicates always have at least one argument
        if effect['arg2']:
            # print("effect['arg2']:", effect['arg2'])
            effect_list.append(effect['arg2'])
            if effect['arg3']:
                effect_list.append(effect['arg3'])

        # apply variable map:
        for effect_arg_idx, effect_arg in enumerate(effect_list):
            if effect_arg_idx == 0:  # predicate does not need variable value application
                continue
            # print(f"effect_arg {effect_arg_idx}:", effect_arg)
            if type(effect_arg) == dict and 'variable' in effect_arg:
                # print("effect_arg['variable']:", effect_arg['variable'])
                effect_list[effect_arg_idx] = variable_map[effect_arg['variable']]

        effect_tuple = tuple(effect_list)
        # print("effect_tuple:", effect_tuple)

        # return unfilled dict for fact tuples with None, as this marks optional action arguments:
        if None in effect_tuple:
            return resolve_effect_results

        if effect_polarity:
            # print(f"Adding {effect_tuple} to world state.")
            self.world_state.add(effect_tuple)
            resolve_effect_results['added'].append(effect_tuple)
        elif not effect_polarity:
            # print(f"Removing {effect_tuple} from world state.")
            if effect_tuple in self.world_state:
                self.world_state.remove(effect_tuple)
            resolve_effect_results['removed'].append(effect_tuple)

        return resolve_effect_results

    def resolve_action(self, action_dict: dict) -> [bool, Union[Set, str], Union[dict, Set]]:
        # print("resolve_action input action_dict:", action_dict)
        # vars for keeping track:
        state_changed = False  # main bool controlling final result world state fact set union/removal
        facts_to_remove = list()  # facts to be removed by world state set removal
        facts_to_add = list()  # facts to union with world state fact set

        # get current action definition:
        cur_action_def = self.action_types[action_dict['type']]
        # print("cur_action_def:", cur_action_def)
        # pretty_action(cur_action_def)
        # get current action PDDL parameter mapping:
        cur_action_pddl_map = self.action_types[action_dict['type']]['pddl_parameter_mapping']
        # print("cur_action_pddl_map:", cur_action_pddl_map)

        # PARAMETERS
        variable_map = dict()
        parameters_base = cur_action_def['interaction']['parameters']
        # print(parameters_base)
        # check that parameters key correctly contains a PDDL type_list:
        if not 'type_list' in parameters_base:
            raise KeyError
        # get parameters list:
        parameters = parameters_base['type_list']
        for param_idx, parameter in enumerate(parameters):
            # print("\nparameter:", parameter, "idx:", param_idx)
            cur_parameter_type = parameter['type_list_element']
            # print("cur_parameter_type:", cur_parameter_type)
            # go over variables in parameter:
            for variable in parameter['items']:
                # print("variable:", variable)
                var_id = variable["variable"]
                # print("var_id:", var_id)
                # use parameter mapping to resolve variable:
                cur_var_map = cur_action_pddl_map[f'?{var_id}']
                # print("cur_var_map:", cur_var_map)
                match cur_var_map[0]:
                    # assign action arguments:
                    case 'arg1':
                        variable_map[var_id] = action_dict['arg1']
                    case 'arg2':
                        if 'arg2' in action_dict:
                            # print("arg2 in action_dict")
                            variable_map[var_id] = action_dict['arg2']
                        else:
                            # print("arg2 NOT in action_dict")
                            # check alternate mapping:
                            if len(cur_var_map) == 2:
                                # print("Alternate mapping:", cur_var_map[1])
                                if cur_var_map[1] == "arg1_receptacle":
                                    # print("variable_map:", variable_map)
                                    arg1_variable = None
                                    for assigned_variable, assigned_value in cur_action_pddl_map.items():
                                        # print("Checking", assigned_variable, assigned_value)
                                        # print("assigned_variable value:", cur_action_pddl_map[assigned_variable])
                                        if assigned_value[0] == "arg1":
                                            # print("arg1 variable:", assigned_variable)
                                            arg1_variable = assigned_variable[1:]
                                            # print("arg1_variable:", arg1_variable)
                                            break
                                    arg1_value = variable_map[arg1_variable]
                                    # print(arg1_value)
                                    arg1_receptacle = None
                                    for fact in self.world_state:
                                        if fact[0] in ["in", "on"]:
                                            if fact[1] == f"{arg1_value}1":  # assume only one instance of each type
                                                arg1_receptacle = fact[2]
                                                # print("arg1_receptacle:", arg1_receptacle)
                                                break
                                    variable_map[var_id] = arg1_receptacle
                            else:
                                variable_map[var_id] = None
                    # assign default wildcards:
                    case 'current_player_room':
                        variable_map[var_id] = self.get_player_room()
                    case 'player':
                        # for now only single-player, so the current player is always player1:
                        variable_map[var_id] = "player1"
                    case 'inventory':
                        # for now only single-player, so the current player inventory is always 'inventory':
                        variable_map[var_id] = "inventory"

                # check type match:
                # assume all world state instance IDs end in numbers:
                if variable_map[var_id]:
                    if variable_map[var_id].endswith(("0","1","2","3","4","5","6","7","8","9")):
                        var_type = self.inst_to_type_dict[variable_map[var_id]]
                    else:
                        # assume that other strings are essentially type strings:
                        var_type = variable_map[var_id]
                else:
                    var_type = variable_map[var_id]

                # print("var_type:", var_type)

                # DOMAIN TYPE CHECK
                type_matched = False
                if type(var_type) == str:
                    # NOTE: Inventory contents are handled via effects PDDL forall now.
                    if var_type in self.domain['supertypes']:
                        # print("domain supertypes for current var_type:", self.domain['supertypes'][var_type])
                        pass
                    # check if type matches directly:
                    if var_type == cur_parameter_type:
                        type_matched = True
                    # check if type matches through supertype:
                    elif var_type in self.domain['supertypes'] and cur_parameter_type in self.domain['supertypes'][var_type]:
                        type_matched = True
                    # print("type matched:", type_matched)
                else:
                    # Fallback for edge cases
                    type_matched = True

                if not type_matched:
                    # get the index of the mismatched variable:
                    var_idx = list(cur_action_pddl_map.keys()).index(f"?{var_id}")
                    # get fail feedback template using mismatched variable index:
                    feedback_template = cur_action_def['failure_feedback']['parameters'][var_idx]
                    feedback_jinja = jinja2.Template(feedback_template)
                    # fill feedback template:
                    jinja_args = {var_id: variable_map[var_id]}
                    feedback_str = feedback_jinja.render(jinja_args)
                    feedback_str = feedback_str.capitalize()
                    # print("parameter fail:", feedback_str)
                    return False, feedback_str, {}

        # variable map is filled during parameter checking
        # print("variable_map pre-preconditions:", variable_map)

        # PRECONDITION
        preconditions: list = cur_action_def['interaction']['precondition'][0]
        # print("preconditions/cur_action_def['interaction']['precondition'][0]:", preconditions)
        self.precon_idx = -1
        # self.precon_idx = 0
        self.precon_tuples = list()
        self.precon_trace = list()
        checked_conditions = self.check_conditions(preconditions, variable_map)
        # print("Main action checked_conditions:",checked_conditions)
        # print("Checked precon tuples:", self.precon_tuples)

        # if checked_conditions:
        if self.precon_trace[-1]['checks_out']:
            print("Preconditions fulfilled!")
            pass
        else:
            print("Preconditions not fulfilled!")

            # NOTE: The first precondition fact that does not check out is used for feedback. This means that the order
            # of predicates (and clauses) in the precondition PDDL for the action determines feedback priority!

            def feedback_idx_from_precon_trace(precon_trace):
                # iterate over precon trace:
                for item in precon_trace[-1]['and']:
                    # print("precon_trace item:", item)
                    # print("Checks out:", item['checks_out'])
                    if not item['checks_out']:
                        # print("Precon trace item does not check out:")
                        # print(item)
                        if 'or' in item:
                            # print("or clause:", item)
                            for or_item in item['or']:
                                # print("or_item:", or_item)
                                if 'and' in or_item:
                                    for and_item in or_item['and']:
                                        if not and_item['checks_out']:
                                            # print("or and_item does not check out:", and_item)
                                            feedback_idx = and_item['precon_idx']
                                            return feedback_idx
                                elif 'predicate_tuple' in or_item:
                                    if not or_item['checks_out']:
                                        feedback_idx = or_item['precon_idx']
                                        return feedback_idx
                        elif 'and' in item:
                            for and_item in item['and']:
                                if not and_item['checks_out']:
                                    # print("or and_item does not check out:", and_item)
                                    feedback_idx = and_item['precon_idx']
                                    return feedback_idx
                        elif 'predicate_tuple' in item:
                            if not item['checks_out']:
                                feedback_idx = item['precon_idx']
                                return feedback_idx

            # TODO?: Make feedback_idx extraction from precon_trace recursive for optimal robustness?

            feedback_idx = feedback_idx_from_precon_trace(self.precon_trace)

            # feedback_template = cur_action_def['failure_feedback']['precondition'][self.precon_idx]
            feedback_template = cur_action_def['failure_feedback']['precondition'][feedback_idx]

            feedback_jinja = jinja2.Template(feedback_template)
            # fill feedback template:
            clean_feedback_variable_map = deepcopy(variable_map)
            for key in clean_feedback_variable_map:
                while clean_feedback_variable_map[key].endswith(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9")):
                    clean_feedback_variable_map[key] = clean_feedback_variable_map[key][:-1]
            jinja_args = clean_feedback_variable_map
            feedback_str = feedback_jinja.render(jinja_args)
            feedback_str = feedback_str.capitalize()
            # print("fail:", feedback_str)

            # get epistemic/pragmatic info for action:
            action_epistemic_pragmatic = {'epistemic': self.action_types[action_dict['type']]['epistemic'],
                                          'pragmatic': self.action_types[action_dict['type']]['pragmatic']}
            print("action_epistemic_pragmatic:", action_epistemic_pragmatic)


            return False, feedback_str, {}


        # print("variable_map post-preconditions:", variable_map)

        # EFFECT

        effects: list = cur_action_def['interaction']['effect']
        if 'and' in effects[0]:  # handle multi-predicate effect, but allow non-and single predicate effect
            effects: list = cur_action_def['interaction']['effect'][0]['and']
        # print("effects:", effects)

        world_state_effects = {'added': [], 'removed': []}

        for effect in effects:
            # print("effect:", effect)
            if 'forall' in effect:
                forall_results = self.resolve_forall(effect, variable_map)
                world_state_effects['added'] += forall_results['added']
                world_state_effects['removed'] += forall_results['removed']
            elif 'when' in effect:
                when_results = self.resolve_when(effect, variable_map)
                world_state_effects['added'] += when_results['added']
                world_state_effects['removed'] += when_results['removed']
            else:
                resolve_effect_results = self.resolve_effect(effect, variable_map)
                world_state_effects['added'] += resolve_effect_results['added']
                world_state_effects['removed'] += resolve_effect_results['removed']

        print("world_state_effects:", world_state_effects)

        # print("World state after effects:", self.world_state)

        # SUCCESS FEEDBACK

        # type word variable map instead of instance ID:
        clean_feedback_variable_map = deepcopy(variable_map)
        for key in clean_feedback_variable_map:
            if clean_feedback_variable_map[key]:
                while clean_feedback_variable_map[key].endswith(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9")):
                    clean_feedback_variable_map[key] = clean_feedback_variable_map[key][:-1]

        success_feedback_template = cur_action_def['success_feedback']
        # print("success_feedback_template:", success_feedback_template)

        feedback_jinja = jinja2.Template(success_feedback_template)

        # jinja_args: dict = {}
        jinja_args: dict = clean_feedback_variable_map
        if "room_desc" in success_feedback_template:
            jinja_args["room_desc"] = self.get_full_room_desc()
        if "inventory_desc" in success_feedback_template:
            jinja_args["inventory_desc"] = self.get_inventory_desc()
        if "prep" in success_feedback_template:
            if "prep" in action_dict:
                jinja_args["prep"] = action_dict['prep']
            else:
                # get preposition fact from world state effects:
                for added_fact in world_state_effects['added']:
                    if added_fact[0] in ['in', 'on']:
                        jinja_args["prep"] = added_fact[0]
                        break
        if "container_content" in success_feedback_template:
            # get opened container fact from world state effects:
            for added_fact in world_state_effects['added']:
                if added_fact[0] == "open":
                    opened_container_id = added_fact[1]
                    break
            jinja_args["container_content"] = self.get_container_content_desc(opened_container_id)
        if "arg1_desc" in success_feedback_template:
            # get description of arg1 entity:
            entity_desc = self.get_entity_desc(action_dict['arg1'])
            # print()
            jinja_args["arg1_desc"] = entity_desc


        feedback_str = feedback_jinja.render(jinja_args)
        # feedback_str = feedback_str.capitalize()

        # print("feedback_str:", feedback_str)

        return True, feedback_str, {}


test_instance = {"initial_state":{
                    "type(player1,player)", "at(player1,kitchen1)", "type(inventory,inventory)",
                    "room(hallway1,hallway)", "room(kitchen1,kitchen)", "room(bedroom1,bedroom)",
                    "exit(kitchen1,hallway1)", "exit(hallway1,kitchen1)", "exit(hallway1,bedroom1)", "exit(bedroom1,hallway1)",
                    "type(sandwich1,sandwich)", "takeable(sandwich1)", "needs_support(sandwich1)",
                    "in(sandwich1,inventory)", "at(sandwich1,kitchen1)",
                    "type(apple1,apple)", "takeable(apple1)", "needs_support(apple1)",
                    "in(apple1,refrigerator1)", "at(apple1,kitchen1)",
                    "type(orange1,orange)", "takeable(orange1)", "needs_support(orange1)",
                    "in(orange1,refrigerator1)", "at(orange1,kitchen1)",
                    "type(banana1,banana)", "takeable(banana1)", "needs_support(banana1)",
                    "in(banana1,refrigerator1)", "at(banana1,kitchen1)",
                    "type(counter1,counter)", "at(counter1,kitchen1)", "support(counter1)",
                    "type(refrigerator1,refrigerator)", "at(refrigerator1,kitchen1)",
                    "container(refrigerator1)", "closed(refrigerator1)",
                    "type(plate1,plate)", "at(plate1,kitchen1)", "on(plate1,counter1)"
                    },
                "action_definitions": ["basic_actions_v2.json"],
                "room_definitions": ["home_rooms.json"],
                "entity_definitions": ["home_entities.json"],
                "domain_definitions": ["home_domain.json"]}


test_interpreter = TestIF(test_instance)

"""
for fact in test_interpreter.world_state:
    if fact[0] == "accessible":
        print("accessible fact:", fact)
"""

"""
for fact in test_interpreter.world_state:
    if fact[0] == "in":
        print(fact)
        for fact2 in test_interpreter.world_state:
            if fact[1] in fact2:
                print(fact2)
"""
"""
print(f"Inventory is a container: {('container', 'inventory') in test_interpreter.world_state}")
print(f"Inventory is open: {('open', 'inventory') in test_interpreter.world_state}")
print(f"Inventory is closed: {('closed', 'inventory') in test_interpreter.world_state}")
"""
# print("Pre-action world state:", test_interpreter.world_state)

# action_input = {'type': "go", 'arg1': "kitchen"}
# action_input = {'type': "go", 'arg1': "hallway"}
# action_input = {'type': "go", 'arg1': "balcony"}
# action_input = {'type': "go", 'arg1': "bedroom"}

# action_input = {'type': "put", 'arg1': "apple", 'arg2': "counter"}
# action_input = {'type': "put", 'arg1': "apple", 'arg2': "counter", 'prep': "on"}
# action_input = {'type': "put", 'arg1': "apple", 'arg2': "refrigerator", 'prep': "in"}


# action_input = {'type': "put", 'arg1': "apple", 'arg2': "refrigerator", 'prep': "in"}

# action_input = {'type': "put", 'arg1': "apple", 'arg2': "plate", 'prep': "on"}

# action_input = {'type': "open", 'arg1': "refrigerator"}

# action_input = {'type': "close", 'arg1': "refrigerator"}

# action_input = {'type': "take", 'arg1': "apple"}
# action_input = {'type': "take", 'arg1': "apple", 'arg2': "refrigerator", 'prep': "from"}
# action_input = {'type': "take", 'arg1': "apple", 'arg2': "counter", 'prep': "from"}

# action_input = {'type': "examine", 'arg1': "refrigerator"}
# action_input = {'type': "examine", 'arg1': "counter"}
# action_input = {'type': "examine", 'arg1': "inventory"}
# action_input = {'type': "examine", 'arg1': "sandwich"}
action_input = {'type': "examine", 'arg1': "apple"}

# action_input = {'type': "done"}

action_resolve_result = test_interpreter.resolve_action(action_input)
print("action_resolve_result:", action_resolve_result)

# print("Post-action world state:", test_interpreter.world_state)
"""
# ACTION 2

action_input = {'type': "take", 'arg1': "apple"}

# action_input = {'type': "go", 'arg1': "kitchen"}
action_resolve_result = test_interpreter.resolve_action(action_input)
print("action_resolve_result:", action_resolve_result)
"""
