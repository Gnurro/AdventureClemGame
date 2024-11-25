import json
import os
from copy import deepcopy
from typing import List, Set, Union

import lark
from lark import Lark, Transformer

from adv_util import fact_str_to_tuple, fact_tuple_to_str


with open("pddl_actions.lark") as grammar_file:
    action_grammar = grammar_file.read()

# print(action_grammar)

action_parser = Lark(action_grammar, start="action")

# test_pddl = "test_pddl_actions.txt"
test_pddl = "test_pddl_actions_take.txt"

with open(test_pddl) as action_file:
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
                if item_element.type == "WORD":
                    type_list_items.append(item_element)
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

    def initialize_states_from_strings(self):
        """
        Initialize the world state set from instance data.
        Converts List[Str] world state format into Set[Tuple].
        """
        for fact_string in self.game_instance['initial_state']:
            self.world_state.add(fact_str_to_tuple(fact_string))

        # NOTE: The following world state augmentations are left in here to make manual adventure creation/modification
        # convenient. Initial adventure world states generated with the clingo adventure generator already cover these
        # augmentations.

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
        print(action_dict)
        # vars for keeping track:
        state_changed = False  # main bool controlling final result world state fact set union/removal
        facts_to_remove = list()  # facts to be removed by world state set removal
        facts_to_add = list()  # facts to union with world state fact set
        # get current action definition:
        cur_action_def = self.action_types[action_dict['type']]['interaction']
        # get current action PDDL parameter mapping:
        cur_action_pddl_map = self.action_types[action_dict['type']]['pddl_parameter_mapping']
        # pretty_action(cur_action_def)
        # PARAMETERS
        variable_map = dict()
        parameters_base = cur_action_def['parameters']
        # print(parameters_base)
        # check that parameters key correctly contains a PDDL type_list:
        if not 'type_list' in parameters_base:
            raise KeyError
        # get parameters list:
        parameters = parameters_base['type_list']
        for parameter in parameters:
            print("\nparameter:", parameter)
            cur_parameter_type = parameter['type_list_item']
            # go over variables in parameter:
            for variable in parameter['items']:
                print("variable:", variable)
                var_id = variable["variable"]
                print("var_id:", var_id)
                # use parameter mapping to resolve variable:
                cur_var_map = cur_action_pddl_map[f'?{var_id}']
                print("cur_var_map:", cur_var_map)
                match cur_var_map:
                    # assign action arguments:
                    case 'arg1':
                        variable_map[var_id] = action_dict['arg1']
                    case 'arg2':
                        variable_map[var_id] = action_dict['arg2']
                    # assign default wildcards:
                    case 'current_player_room':
                        variable_map[var_id] = self.get_player_room()
                    case 'current_player':
                        # for now only single-player, so the current player is always player1:
                        variable_map[var_id] = "player1"
                    case 'current_player_inventory':
                        # for now only single-player, so the current player inventory is always 'inventory':
                        variable_map[var_id] = "inventory"
                    case 'current_player_inventory_content':
                        variable_map[var_id] = self.get_inventory_content()

                # check type match:
                # assume all world state instance IDs end in numbers:
                if variable_map[var_id][-1] in ["0","1","2","3","4","5","6","7","8","9"]:
                    var_type = self.inst_to_type_dict[variable_map[var_id]]
                else:
                    # assume that other strings are essentially type strings:
                    var_type = variable_map[var_id]
                print("var_type:", var_type)
                # TODO: check for predicates to match

        print("variable_map:", variable_map)



test_instance = {"initial_state":
                    {"type(player1,player)", "inventory(inventory1,player1)", "at(player1,hallway1)",
                    "room(hallway1,hallway)", "room(kitchen1,kitchen)",
                    "exit(kitchen1,hallway1)", "exit(hallway1,kitchen1)",
                    "type(sandwich1,sandwich)", "takeable(sandwich1)",
                    "in(sandwich1,inventory)"},
                "action_definitions": ["basic_actions_v2.json"],
                "room_definitions": ["home_rooms.json"],
                "entity_definitions": ["home_entities.json"]}

test_interpreter = TestIF(test_instance)


action_input = {'type': "go", 'arg1': "kitchen"}

test_interpreter.resolve_action(action_input)
