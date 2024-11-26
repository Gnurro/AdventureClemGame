import json
import os
from copy import deepcopy
from typing import List, Set, Union

import lark
from lark import Lark, Transformer
import jinja2

from adv_util import fact_str_to_tuple, fact_tuple_to_str

# PDDL ACTIONS

with open("pddl_actions.lark") as grammar_file:
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

    def type_list_item(self, content):
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

        return {'type_list_item': cat_name, 'items': type_list_items}

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
            if 'type_list_item' in cont:
                types_list.append(cont)
        types_dict = dict()
        for type_list in types_list:
            # print(type_list)
            types_dict[f'{type_list["type_list_item"]}'] = type_list['items']
        # print("types return:", {'types': types_list})
        return {'types': types_dict}

    def type_list(self, content):
        # print(content)
        return {'type_list': content}

    def type_list_item(self, content):
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
        return {'type_list_item': cat_name, 'items': type_list_items}


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
            cur_action_type = self.action_types[action_type]

            if 'pddl' in cur_action_type:
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
        # print(self.entity_types)
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
                facts_to_add.add(('type', f'{fact[1]}floor', 'floor'))
                # add floor:
                facts_to_add.add(('at', f'{fact[1]}floor', fact[1]))

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

        self.world_state = self.world_state.union(facts_to_add)
        # add initial world state to world state history:
        self.world_state_history.append(deepcopy(self.world_state))
        """
        # get goal state fact set:
        for fact_string in self.game_instance['goal_state']:
            self.goal_state.add(fact_str_to_tuple(fact_string))
        """

    def get_player_room(self) -> str:
        """
        Get the current player location's internal room string ID.
        """
        for fact in self.world_state:
            if fact[0] == 'at' and fact[1] == 'player1':
                player_room = fact[2]
                break

        return player_room

    def get_inventory_content(self, player: str = 'player1') -> list:
        # single-player for now, so default to player1
        inventory_content = list()
        for fact in self.world_state:
            if fact[0] == 'in' and fact[2] == 'inventory':
                inventory_content.append(fact[1])

        return inventory_content

    # def check_predicate(self, ):

    def resolve_action(self, action_dict: dict) -> [bool, Union[Set, str], Union[dict, Set]]:
        # print(action_dict)
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
            cur_parameter_type = parameter['type_list_item']
            # print("cur_parameter_type:", cur_parameter_type)
            # go over variables in parameter:
            for variable in parameter['items']:
                # print("variable:", variable)
                var_id = variable["variable"]
                # print("var_id:", var_id)
                # use parameter mapping to resolve variable:
                cur_var_map = cur_action_pddl_map[f'?{var_id}']
                # print("cur_var_map:", cur_var_map)
                match cur_var_map:
                    # assign action arguments:
                    case 'arg1':
                        variable_map[var_id] = action_dict['arg1']
                    case 'arg2':
                        variable_map[var_id] = action_dict['arg2']
                    # assign default wildcards:
                    case 'current_player_room':
                        variable_map[var_id] = self.get_player_room()
                    case 'player':
                        # for now only single-player, so the current player is always player1:
                        variable_map[var_id] = "player1"
                    case 'inventory':
                        # for now only single-player, so the current player inventory is always 'inventory':
                        variable_map[var_id] = "inventory"
                    case 'inventory_content':
                        variable_map[var_id] = self.get_inventory_content()
                # check type match:
                # assume all world state instance IDs end in numbers:
                if variable_map[var_id][-1] in ["0","1","2","3","4","5","6","7","8","9"]:
                    var_type = self.inst_to_type_dict[variable_map[var_id]]
                else:
                    # assume that other strings are essentially type strings:
                    var_type = variable_map[var_id]
                # print("var_type:", var_type)

                # DOMAIN TYPE CHECK
                type_matched = False
                if type(var_type) == str:
                    # TODO: handle inventory contents - does it make sense to handle them as a list like this in the first place?
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
                    # just pass through for now, see TODO above
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
        print("variable_map:", variable_map)

        # PRECONDITION
        preconditions: list = cur_action_def['interaction']['precondition'][0]['and']
        # print("preconditions:", preconditions)
        precon_idx = 0
        for precondition in preconditions:
            print(precondition)
            # 'polarity' of the precondition:
            # if True, the precondition is fulfilled if its fact is in the world state
            # if False, the precondition is NOT fulfilled if its fact is in the world state
            precon_polarity = True
            if 'not' in precondition:
                print("not clause in precondition!")
                precon_polarity = False
                precondition = precondition['not']
            cur_predicate = precondition['predicate']
            if not precondition['arg3']:
                # print("No arg3 in precondition!")
                if not precondition['arg2']:
                    # print("No arg2 in precondition!")
                    arg1_value = variable_map[precondition['arg1']['variable']]
                    precon_tuple = (cur_predicate, arg1_value)
                else:
                    arg1_value = variable_map[precondition['arg1']['variable']]
                    arg2_value = variable_map[precondition['arg2']['variable']]
                    precon_tuple = (cur_predicate, arg1_value, arg2_value)
            else:
                arg1_value = variable_map[precondition['arg1']['variable']]
                arg2_value = variable_map[precondition['arg2']['variable']]
                arg3_value = variable_map[precondition['arg3']['variable']]
                precon_tuple = (cur_predicate, arg1_value, arg2_value, arg3_value)

            print("precon_tuple:", precon_tuple)
            # TODO: handle type word in action input to world state mapping; ie arg2='kitchen' to match 'kitchen1'

            # check for predicate fact to match the precondition:
            precon_is_fact = False

            if precon_tuple in self.world_state:
                print(f"Precondition {precon_tuple} is in the world state!")
                precon_is_fact = True
            else:
                print(f"Precondition {precon_tuple} is NOT in the world state!")

            precon_fulfilled = False
            # check that precondition 'polarity' matches:
            if precon_is_fact == precon_polarity:
                precon_fulfilled = True

            if precon_fulfilled:
                print("Precondition fulfilled!")
            else:
                print("Precondition not fulfilled!")
                # get fail feedback template using precondition index:
                feedback_template = cur_action_def['failure_feedback']['precondition'][precon_idx]
                feedback_jinja = jinja2.Template(feedback_template)
                # fill feedback template:
                # jinja_args = {var_id: variable_map[var_id]}
                jinja_args = variable_map
                feedback_str = feedback_jinja.render(jinja_args)
                feedback_str = feedback_str.capitalize()
                print("fail:", feedback_str)

            print("\n")
            precon_idx += 1
            # break




test_instance = {"initial_state":{
                    "type(player1,player)", "at(player1,hallway1)",
                    "room(hallway1,hallway)", "room(kitchen1,kitchen)",
                    "exit(kitchen1,hallway1)", "exit(hallway1,kitchen1)",
                    "type(sandwich1,sandwich)", "takeable(sandwich1)",
                    "in(sandwich1,inventory)"
                    },
                "action_definitions": ["basic_actions_v2.json"],
                "room_definitions": ["home_rooms.json"],
                "entity_definitions": ["home_entities.json"],
                "domain_definitions": ["home_domain.json"]}

test_interpreter = TestIF(test_instance)


action_input = {'type': "go", 'arg1': "kitchen"}
# action_input = {'type': "go", 'arg1': "balcony"}

test_interpreter.resolve_action(action_input)
