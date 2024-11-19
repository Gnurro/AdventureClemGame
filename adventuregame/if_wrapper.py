"""
    IF interpreter for adventuregame.
"""

import json
import lark
from lark import Lark, Transformer
import jinja2

import os
from copy import deepcopy
from typing import List, Set, Union

from clemgame.clemgame import GameResourceLocator
from clemgame import get_logger

from games.adventuregame.adv_util import fact_str_to_tuple, fact_tuple_to_str

PATH = "games/adventuregame/"
RESOURCES_SUBPATH = "resources/"

GAME_NAME = "adventuregame"
logger = get_logger(__name__)


class IFTransformer(Transformer):
    """
    IF action grammar transformer to convert Lark parse to python dict for further use.
    """
    # since this is solely for action command parse conversion, any input is converted to a parsed action dict:
    def action(self, content):
        action: lark.Tree = content[0]
        action_type = action.data  # main grammar rule the input was parsed as
        action_content = action.children  # all parsed arguments of the action 'VP'
        action_dict = {'type': action_type.value}  # value = string name of rule in grammar

        arguments = []
        arg_idx = 1

        for child in action_content:
            # handle potentially multi-word 'thing' arguments; roughly equivalent to generic 'NP':
            if type(child) == lark.Tree and child.data == 'thing':
                argument_words = [word.value for word in child.children if word.type == 'WORD']
                arguments.append(" ".join(argument_words))
                # extract defined adjectives:
                argument_adjs = [adj.value.strip() for adj in child.children[:-1] if adj.type == 'ADJ']
                if argument_adjs:
                    action_dict[f'arg{arg_idx}_adjs'] = argument_adjs
                action_dict[f'arg{arg_idx}'] = arguments[-1]
                arg_idx += 1
            # extract defined prepositions:
            if type(child) == lark.Token and child.type == 'PREP':
                action_dict['prep'] = child.value.strip()
            # if the input can't be parsed as a defined action command, the grammar labels it as 'unknown'
            # in this case, the first word is assumed to be the verb and is returned for feedback:
            if action_type.value == 'unknown' and type(child) == lark.Token and child.type == 'WORD':
                action_dict[f'arg{arg_idx}'] = child.value
                break

        return action_dict


class AdventureIFInterpreter(GameResourceLocator):
    """
    IF interpreter for adventuregame.
    Holds game world state and handles all interaction and feedback.
    """
    def __init__(self, game_instance: dict, name: str = GAME_NAME, verbose: bool = False):
        super().__init__(name)
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

        self.world_state: set = set()
        self.world_state_history: list = list()
        self.goal_state: set = set()
        self.goals_achieved: set = set()
        self.initialize_states_from_strings()

        self.initialize_action_parsing(print_lark_grammar=verbose)

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

        # TODO: read and parse PDDL action representation

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
            # convert fact to change from string to tuple:
            cur_action_type['object_post_state'] = fact_str_to_tuple(cur_action_type['object_post_state'])

    def initialize_action_parsing(self, print_lark_grammar: bool = False):
        """
        Initialize the lark action input parser and transformer.
        Constructs a lark grammar string from action definition lark snippets.
        """
        act_grammar_rules = list()
        act_grammar_larks = list()

        for action_type in self.action_types:
            cur_action_type = self.action_types[action_type]
            action_rule = cur_action_type['lark'].split(":")[0]
            act_grammar_rules.append(action_rule)
            act_grammar_larks.append(cur_action_type['lark'])
        # root rule to parse any action command input, with fallback 'unknown':
        act_grammar_action_line = f"action: {' | '.join(act_grammar_rules)} | unknown\n"
        # append all individual action lark grammar snippets:
        act_grammar_larks_str = "\n".join(act_grammar_larks)
        # gather all possible adjectives from entity definitions:
        all_adjs = set()
        for entity_type, entity_def in self.entity_types.items():
            if 'possible_adjs' in entity_def:
                new_adj_set = set(entity_def['possible_adjs'])
                all_adjs.update(new_adj_set)
        all_adjs = [f'"{adj}"' for adj in all_adjs]
        # adjective rule:
        act_grammar_adj_line = f"ADJ.1: ({' | '.join(all_adjs)}) WS\n"
        # load the core grammar from file:
        grammar_core = self.load_json(f"resources{os.sep}grammar_core")
        grammar_head = grammar_core['grammar_head']
        grammar_foot = grammar_core['grammar_foot']
        # combine adventure-specific grammar rules with core grammar:
        act_grammar = (f"{grammar_head}{act_grammar_action_line}"
                       f"{act_grammar_larks_str}\n{act_grammar_adj_line}{grammar_foot}")
        # print grammar in verbose mode for inspection:
        if print_lark_grammar:
            print(act_grammar)
        # initialize lark parser with the combined grammar:
        self.act_parser = Lark(act_grammar, start='action')
        # initialize parse result transformer:
        self.act_transformer = IFTransformer()

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
            if fact[0] == 'type':
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
        # get goal state fact set:
        for fact_string in self.game_instance['goal_state']:
            self.goal_state.add(fact_str_to_tuple(fact_string))

    def _get_inst_str(self, inst) -> str:
        """
        Get a full string representation of an entity or room instance with adjectives.
        """
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

    def get_player_room(self) -> str:
        """
        Get the current player location's internal room string ID.
        """
        for fact in self.world_state:
            if fact[0] == 'at' and fact[1] == 'player1':
                player_room = fact[2]
                break

        return player_room

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
        Get the 'visible' contents of the current room.
        This is also used to determine if an entity is accessible for interaction. Entities 'in' closed entities are not
        returned.
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
                    for state_pred2 in self.world_state:
                        if state_pred2[0] == 'closed' and state_pred2[1] == contained_in:
                            # not visible/accessible in closed container
                            break
                        elif state_pred2[0] == 'open' and state_pred2[1] == contained_in:
                            visible_contents.append(thing)
                            break
                        elif state_pred2[1] == 'inventory' and state_pred2[1] == contained_in:
                            visible_contents.append(thing)
                            break
            if contained_in:
                continue
            visible_contents.append(thing)

        return visible_contents

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

    def get_inventory_content(self) -> Set:
        """
        Get set of inventory content.
        """
        inventory_content = set()
        for fact in self.world_state:
            if fact[0] == 'in' and fact[2] == 'inventory':
                inventory_content.add(fact[1])

        return inventory_content

    def get_inventory_desc(self) -> str:
        """
        Get a text description of the current inventory content.
        Used for feedback for 'take' action.
        """
        inventory_content: set = self.get_inventory_content()
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

    def parse_action_input(self, action_input: str) -> [bool, Union[dict, str], Union[dict, Set]]:
        """
        Parse input action command string to action dict.
        Input is cleaned by removing trailing punctuation and lower-casing it.
        Fail if action/entities are not defined or input command is not covered by grammar.
        This method is effectively the parsing phase mentioned in the paper.
        Returns tuple of: failure bool, parsed action dict or failure feedback, failure information dict or empty set.
        """
        # remove final punctuation:
        if action_input.endswith(".") or action_input.endswith("!"):
            action_input = action_input[:-1]
        # lower for proper parsing:
        action_input = action_input.lower()

        logger.info(f"Cleaned action input: {action_input}")

        # try parsing input, return lark_exception failure if parsing fails:
        try:
            parsed_command = self.act_parser.parse(action_input)
        except Exception as exception:
            logger.info(f"Parsing lark exception")
            fail_dict: dict = {'phase': "parsing", 'fail_type': "lark_exception", 'arg': str(exception)}
            return False, f"I don't know what you mean.", fail_dict
        action_dict = self.act_transformer.transform(parsed_command)

        # catch 'unknown' action parses:
        if action_dict['type'] == "unknown":
            if action_dict['arg1'] in self.action_types:
                logger.info(f"Parsing unknown action with defined verb")
                fail_dict: dict = {'phase': "parsing", 'fail_type': "malformed_command", 'arg': str(action_dict)}
                return False, f"I don't know what you mean.", fail_dict

        if action_dict['type'] not in self.action_types:
            if 'arg1' in action_dict:
                logger.info(f"Parsing undefined action with undefined verb")
                fail_dict: dict = {'phase': "parsing", 'fail_type': "undefined_action_verb", 'arg': action_dict['arg1']}
                return False, f"I don't know how to interpret this '{action_dict['arg1']}' action.", fail_dict
            else:
                logger.info(f"Parsing undefined action without verb")
                fail_dict: dict = {'phase': "parsing", 'fail_type': "undefined_action", 'arg': action_input}
                return False, f"I don't know what you mean.", fail_dict

        if action_dict['arg1'] in self.repr_str_to_type_dict:
            # convert arg1 from repr to internal type:
            action_dict['arg1'] = self.repr_str_to_type_dict[action_dict['arg1']]
        else:
            # in this case, the action is defined, but the first argument isn't, leading to corresponding feedback
            fail_dict: dict = {'phase': "parsing", 'fail_type': "undefined_repr_str", 'arg': action_dict['arg1']}
            return False, f"I don't know what '{action_dict['arg1']}' means.", fail_dict

        if action_dict['arg1'] not in self.entity_types:
            logger.info(f"Action arg1 '{action_dict['arg1']}' is not an entity")
            # handle manipulating rooms, ie "> take from kitchen":
            if action_dict['arg1'] in self.room_types:
                if action_dict['type'] in ["take", "put", "open", "close"]:
                    logger.info(f"Action type is '{action_dict['type']}', manipulating room")
                    fail_dict: dict = {'phase': "parsing", 'fail_type': "manipulating_room", 'arg': action_dict['arg1']}
                    if action_dict['type'] == "take":
                        fail_response = f"You can't {action_dict['type']} the '{action_dict['arg1']}'."
                    elif action_dict['type'] == "put":
                        fail_response = f"You can't {action_dict['type']} the '{action_dict['arg1']}' anywhere."
                    elif action_dict['type'] == "open":
                        fail_response = f"You don't need to {action_dict['type']} the '{action_dict['arg1']}'."
                    elif action_dict['type'] == "close":
                        fail_response = f"You can't {action_dict['type']} the '{action_dict['arg1']}'."
                    return False, fail_response, fail_dict
            else:
                logger.info(f"Action arg1 {action_dict['arg1']} is not a room either")
                fail_dict: dict = {'phase': "parsing", 'fail_type': "undefined_argument_type", 'arg': action_dict['arg1']}
                return False, f"I don't know what a '{action_dict['arg1']}' is.", fail_dict

        if 'arg2' in action_dict:
            if action_dict['type'] == "take":
                # handle unnecessary inventory interaction:
                if action_dict['arg2'] == "inventory":
                    logger.info("Taking from inventory")
                    # get inventory content:
                    inventory_content = self.get_inventory_content()
                    for inventory_item in inventory_content:
                        if self.inst_to_type_dict[inventory_item] == action_dict['arg1']:
                            fail_dict: dict = {'phase': "resolution", 'fail_type': "taking_from_inventory",
                                               'arg': action_dict['arg1']}
                            return False, f"The {self.entity_types[action_dict['arg1']]['repr_str']} is already in your inventory.", fail_dict
                    fail_dict: dict = {'phase': "parsing", 'fail_type': "taking_from_inventory", 'arg': action_dict['arg2']}
                    return False, f"You don't need to take things from your inventory.", fail_dict
            if action_dict['arg2'] in self.repr_str_to_type_dict:
                # convert arg1 from repr to internal type:
                action_dict['arg2'] = self.repr_str_to_type_dict[action_dict['arg2']]
                # handle other room interaction attempts; ie "> take plate from kitchen" while player is elsewhere:
                if action_dict['arg2'] in self.room_types:
                    cur_room_str = self.room_types[self.room_to_type_dict[self.get_player_room()]]['repr_str']
                    if not action_dict['arg2'] == cur_room_str:
                        fail_dict: dict = {'phase': "parsing", 'fail_type': "other_room_argument",
                                           'arg': action_dict['arg2']}
                        return False, f"You are not in a {action_dict['arg2']}.", fail_dict
            else:
                fail_dict: dict = {'phase': "parsing", 'fail_type': "undefined_repr_str", 'arg': action_dict['arg2']}
                return False, f"I don't know what '{action_dict['arg2']}' means.", fail_dict

        return True, action_dict, {}

    def resolve_action(self, action_dict: dict) -> [bool, Union[Set, str], Union[dict, Set]]:
        """
        Check action viability and change world state if applicable.
        This method is effectively the resolution phase mentioned in the paper.
        Returns tuple of: failure bool, changed state facts set or failure feedback, failure information dict or empty
        set.
        """
        # deepcopy the world state to prevent referential interaction:
        prior_world_state = deepcopy(self.world_state)

        # TODO: convert to use PDDL-based action representation
        # TODO: improve feedback
        # TODO: align feedback with action parameters, preconditions (and conditional effects?)

        # get state changes for current action:
        state_changes = self.action_types[action_dict['type']]['state_changes']

        state_changed = False  # main bool controlling final result world state fact set union/removal
        facts_to_remove = list()  # facts to be removed by world state set removal
        facts_to_add = list()  # facts to union with world state fact set

        for state_change in state_changes:  # each state-change fact an action can result in is handled individually
            logger.info(f"Checking state change: {state_change}")
            # GO ACTION/ROOM TRAVERSAL
            if "HERE" in state_change['pre_state'] or "HERE" in state_change['post_state']:
                logger.info(f"State change is location-based")
                # check if arg is a room type; handles "> go to table" and similar inputs:
                if action_dict['arg1'] not in self.room_types:
                    fail_dict: dict = {'phase': "resolution", 'fail_type': "not_room_type", 'arg': action_dict['arg1']}
                    not_room_type_str: str = f"I don't know what room '{action_dict['arg1']}' is."
                    return False, not_room_type_str, fail_dict

                # get currently accessible entities:
                things_here = set(self.get_player_room_contents_visible()) | self.get_inventory_content()

                # get passages in current room:
                present_exits = self.get_player_room_exits()
                passable_exits = {self.room_to_type_dict[instance]: [] for instance in present_exits}
                for instance in present_exits:
                    passable_exits[self.room_to_type_dict[instance]].append(instance)
                # handle 'go' with argument for which no passages are present:
                if action_dict['arg1'] not in passable_exits:
                    # handle going to same room; simply use room type as v1 has only one room of each type:
                    if action_dict['arg1'] == self.room_to_type_dict[self.get_player_room()]:
                        logger.info(f"Traversal to current room type: {self.get_player_room()}")
                        fail_dict: dict = {'phase': "resolution", 'fail_type': "going_to_current_room", 'arg': action_dict['arg1']}
                        no_exit_to_str: str = f"You are already in the {self.room_types[action_dict['arg1']]['repr_str']}."
                        return False, no_exit_to_str, fail_dict
                    else:
                        logger.info(f"Traversal to '{action_dict['arg1']}' not possible")
                        fail_dict: dict = {'phase': "resolution", 'fail_type': "no_exit_to", 'arg': action_dict['arg1']}
                        no_exit_to_str: str = f"There is no passage to a {self.room_types[action_dict['arg1']]['repr_str']} here."
                        return False, no_exit_to_str, fail_dict
                # handle multiple passages to argument room type; not used in v1:
                elif len(passable_exits[action_dict['arg1']]) > 1:
                    fail_dict: dict = {'phase': "resolution", 'fail_type': "multiple_exits_to", 'arg': action_dict['arg1']}
                    return False, f"There are multiple {self.room_types[action_dict['arg1']]['repr_str']}s here.", fail_dict
                else:
                    # get the internal instance ID of target adjacent room:
                    arg1_inst = passable_exits[action_dict['arg1']][0]

                # get the main state-change fact and insert current player room:
                pre_state: str = state_change['pre_state'].replace("HERE", self.get_player_room())
                # Example: pre_state = "at(PLAYER,HERE)" -> pre_state = "at(PLAYER,kitchen1)"
                # this is the fact to remove from the world state set when this state-change
                # of the current action is resolved successfully

                if "PLAYER" in pre_state:  # handle PLAYER pre-states separately
                    # insert player ID into state-change pre-state string template:
                    pre_state = pre_state.replace("PLAYER", "player1")
                    # Example: pre_state = "at(PLAYER,kitchen1)" -> pre_state = "at(player1,kitchen1)"
                    # in v1, the player entity ID is always player1
                    pre_state_tuple = fact_str_to_tuple(pre_state)

                    # insert target room ID into state-change post-state string template:
                    post_state: str = state_change['post_state'].replace("TARGET", arg1_inst)
                    # Example: post_state = "at(PLAYER,TARGET)" -> post_state = "at(PLAYER,pantry1)"
                    # insert player ID into state-change post-state string template:
                    post_state = post_state.replace("PLAYER", "player1")
                    # Example: post_state = "at(PLAYER,pantry1)" -> post_state = "at(player1,pantry1)"
                    post_state_tuple = fact_str_to_tuple(post_state)

                    # each state-change has at least one world state fact condition
                    # all condition facts must hold in the current world state for the state-change to be processed
                    # check state-change fact conditions:
                    conditions_fulfilled: bool = True  # conditions assumed to hold for straight-forward resolution
                    for condition in state_change['conditions']:
                        # insert internal IDs into template and convert to fact tuple:
                        player_condition = condition.replace("HERE", self.get_player_room())
                        player_condition = player_condition.replace("TARGET", arg1_inst)
                        player_condition_tuple = fact_str_to_tuple(player_condition)
                        # check if fact holds for current world state:
                        if player_condition_tuple not in self.world_state:
                            conditions_fulfilled = False

                    if conditions_fulfilled:
                        facts_to_remove.append(pre_state_tuple)
                        facts_to_add.append(post_state_tuple)
                        if facts_to_add or facts_to_remove:
                            if not facts_to_add == facts_to_remove:
                                state_changed = True

                if "THING" in pre_state:
                    # handle entities in inventory 'following' the player:
                    # at(apple1,pantry1), at(player1,pantry1) + "> go kitchen"
                    # -> at(apple1,kitchen1), at(player1,kitchen1)

                    # check things at location:
                    internal_visible_contents = self.get_player_room_contents_visible()
                    for thing_here in things_here:
                        # insert internal IDs into template and convert to fact tuple:
                        pre_state: str = state_change['pre_state'].replace("HERE", self.get_player_room())
                        pre_state = pre_state.replace("THING", thing_here)
                        pre_state_tuple = fact_str_to_tuple(pre_state)
                        # insert internal IDs into template and convert to fact tuple:
                        post_state: str = state_change['post_state'].replace("TARGET", arg1_inst)
                        post_state = post_state.replace("THING", thing_here)
                        post_state_tuple = fact_str_to_tuple(post_state)

                        # check conditions
                        conditions_fulfilled: bool = True
                        for condition in state_change['conditions']:
                            thing_condition = condition.replace("THING", thing_here)
                            thing_condition_tuple = fact_str_to_tuple(thing_condition)
                            if thing_condition_tuple not in self.world_state:
                                conditions_fulfilled = False

                        if conditions_fulfilled:
                            facts_to_remove.append(pre_state_tuple)
                            facts_to_add.append(post_state_tuple)
                            if facts_to_add or facts_to_remove:
                                if not facts_to_add == facts_to_remove:
                                    state_changed = True

            # ENTITY INTERACTION / TAKE, PUT, OPEN, CLOSE
            elif "THING" in state_change['pre_state'] or "THING" in state_change['post_state']:
                logger.info(f"State change is entity manipulation")
                # ENTITY ACCESSIBILITY
                # get visible room content:
                internal_visible_contents = self.get_player_room_contents_visible()

                # get inventory content:
                inventory_content = self.get_inventory_content()

                # convert to types:
                accessible_contents = {self.inst_to_type_dict[instance]: [] for instance in internal_visible_contents}
                for instance in internal_visible_contents:
                    accessible_contents[self.inst_to_type_dict[instance]].append(instance)
                for inventory_item in inventory_content:
                    if self.inst_to_type_dict[inventory_item] not in accessible_contents:
                        accessible_contents[self.inst_to_type_dict[inventory_item]] = []
                    accessible_contents[self.inst_to_type_dict[inventory_item]].append(inventory_item)
                # add floor to accessible room contents to allow taking from floor:
                accessible_contents["floor"] = [f"{self.get_player_room()}floor"]

                if action_dict['type'] == "take":
                    for inventory_item in inventory_content:
                        # in v1, there is only one entity of each type, making resolution straight-forward
                        if self.inst_to_type_dict[inventory_item] == action_dict['arg1']:
                            fail_dict: dict = {'phase': "resolution", 'fail_type': "entity_already_inventory",
                                               'arg': action_dict['arg1']}
                            return False, f"The {self.entity_types[action_dict['arg1']]['repr_str']} is already in your inventory.", fail_dict

                arg1 = action_dict['arg1']
                if arg1 not in accessible_contents:
                    logger.info(f"THING action argument not accessible: {arg1}")
                    # handle "> open pantry"-type actions:
                    if arg1 in self.room_types:
                        logger.info(f"THING action arg1 '{arg1}' is a room type")
                        logger.info(f"current player room: {self.get_player_room()}")
                        fail_dict: dict = {'phase': "resolution", 'fail_type': "thing_arg1_room", 'arg': arg1}
                        thing_arg2_room_str: str = f"You can't do this with a room."
                        return False, thing_arg2_room_str, fail_dict
                    else:
                        # handle inaccessible entity:
                        fail_dict: dict = {'phase': "resolution", 'fail_type': "entity_not_accessible",
                                           'arg': action_dict['arg1']}
                        return False, f"You can't see a {self.entity_types[arg1]['repr_str']} here.", fail_dict
                elif len(accessible_contents[arg1]) > 1:
                    # in v1, there is only one entity of each type, so this is not used
                    fail_dict: dict = {'phase': "resolution", 'fail_type': "multiple_entity_ambiguity",
                                       'arg': action_dict['arg1']}
                    return False, f"There are multiple {self.entity_types[arg1]['repr_str']} here.", fail_dict
                else:
                    arg1_inst = accessible_contents[arg1][0]

                # handle "> take book from shelf"-type actions:
                arg2_inst = None
                if 'arg2' in action_dict:
                    arg2 = action_dict['arg2']
                    logger.info(f"THING action has arg2: '{arg2}'")
                    if arg2 not in accessible_contents:
                        logger.info(f"THING action arg2 '{arg2}' is not accessible")
                        # check if arg2 is room:
                        if arg2 in self.room_types:
                            # handle "> take book from living room"-type actions:
                            logger.info(f"THING action arg2 '{arg2}' is a room type")
                            logger.info(f"current player room: {self.get_player_room()}")
                            fail_dict: dict = {'phase': "resolution", 'fail_type': "thing_arg2_room", 'arg': arg2}
                            thing_arg2_room_str: str = f"You need to be more specific."
                            return False, thing_arg2_room_str, fail_dict
                        else:
                            fail_dict: dict = {'phase': "resolution", 'fail_type': "entity_not_accessible",
                                               'arg': arg2}
                            thing_not_accessible_str: str = f"You can't see a {self.entity_types[arg2]['repr_str']} here."
                            return False, thing_not_accessible_str, fail_dict
                    elif len(accessible_contents[arg2]) > 1:
                        # in v1, there is only one entity of each type, so this is not used
                        fail_dict: dict = {'phase': "resolution", 'fail_type': "multiple_entity_ambiguity",
                                           'arg': arg2}
                        return False, f"There are multiple {self.entity_types[arg2]['repr_str']} here.", fail_dict
                    else:
                        arg2_inst = accessible_contents[arg2][0]

                # replace string placeholders with fact IDs:
                pre_state: str = state_change['pre_state'].replace("THING", arg1_inst)

                # handle ANY templates; this is used to account for entities being 'in' or 'on' other entities:
                if "ANY" in pre_state:
                    any_match = False
                    pred = fact_str_to_tuple(pre_state)[0]
                    for state_pred in self.world_state:
                        if state_pred[0] == pred and state_pred[1] == arg1_inst:
                            any_match = True
                            pre_state = pre_state.replace("ANY", state_pred[2])
                            break
                    if not any_match:
                        continue  # with next state-change

                post_state: str = state_change['post_state'].replace("THING", arg1_inst)
                # Example: post_state = PREP(THING,TARGET) -> post_state = PREP(apple1,TARGET)

                if "PREP" in post_state:
                    post_state = post_state.replace("PREP", action_dict['prep'])
                    # Example: post_state = PREP(apple1,TARGET) -> post_state = on(apple1,TARGET)

                if "TARGET" in post_state:
                    post_state = post_state.replace("TARGET", arg2_inst)
                    # Example: post_state = on(apple1,TARGET) -> post_state = on(apple1,table1)

                # convert to fact tuples:
                pre_state_tuple = fact_str_to_tuple(pre_state)
                post_state_tuple = fact_str_to_tuple(post_state)

                # check conditions:
                conditions_fulfilled: bool = True
                for condition in state_change['conditions']:
                    thing_condition = condition.replace("THING", arg1_inst)
                    if arg2_inst:
                        thing_condition = thing_condition.replace("TARGET", arg2_inst)
                    logger.info(f"Checking state change condition: {thing_condition}")
                    thing_condition_tuple = fact_str_to_tuple(thing_condition)
                    if thing_condition_tuple not in self.world_state:
                        logger.info(f"State change condition '{thing_condition}' is not in world state")
                        conditions_fulfilled = False
                    else:
                        logger.info(f"State change condition '{thing_condition}' is in world state")

                if conditions_fulfilled:
                    facts_to_remove.append(pre_state_tuple)
                    facts_to_add.append(post_state_tuple)
                    if facts_to_add or facts_to_remove:
                        if not facts_to_add == facts_to_remove:
                            state_changed = True

        if state_changed:
            for remove_fact in facts_to_remove:
                if remove_fact in self.world_state:
                    self.world_state.remove(remove_fact)
                else:
                    # proper specific feedback would be needed to make this useful
                    pass
            for add_fact in facts_to_add:
                self.world_state.add(add_fact)

            # add deepcopy of new current world state to world state history:
            self.world_state_history.append(deepcopy(self.world_state))

            # get all changed facts:
            post_world_state = deepcopy(self.world_state)
            post_resolution_changes = post_world_state.difference(prior_world_state)
            if prior_world_state == self.world_state_history[-2]:
                logger.info(f"Prior world state matches second to last world state in history")
            logger.info(f"Resolution world state changes: {post_resolution_changes}")

            logger.info(f"Resolution resulted in changed world state; "
                        f"removed facts: {facts_to_remove}; "
                        f"added facts: {facts_to_add}")
            if facts_to_add:
                return True, facts_to_add[0], {}
        else:  # fallback if world state hasn't been changed by action resolution
            logger.info(f"No state change fallback")
            pre_state_tuple = fact_str_to_tuple(pre_state)
            logger.info(f"Pre-state tuple: {pre_state_tuple}")
            # sanity check for pre-state and world state:
            if pre_state_tuple not in self.world_state:
                logger.info(f"Pre-state {pre_state_tuple} not in world state")
            else:
                logger.info(f"Pre-state {pre_state_tuple} in world state")
            # edge case handling:
            if len(pre_state_tuple) >= 3:
                if pre_state_tuple[2] == "ANY":
                    pre_state_antecedent = "anything"
                else:
                    pre_state_antecedent = pre_state_tuple[1]
                pre_state_response = f"{pre_state_tuple[0]} {pre_state_antecedent}"
                response_str = f"The {self.entity_types[action_dict['arg1']]['repr_str']} is not {pre_state_response}."
                # this can result in rather cryptic responses; better feedback would require more hardcode like below
            elif action_dict['type'] in ["open", "close"]:
                response_str = f"The {self.entity_types[action_dict['arg1']]['repr_str']} is not {pre_state_tuple[0]}."
            else:
                response_str = f"You can't do that with the {self.entity_types[action_dict['arg1']]['repr_str']} right now."
            fail_dict: dict = {'phase': "resolution", 'fail_type': "pre_state_mismatch",
                               'arg': [action_dict['arg1'], pre_state]}
            return False, response_str, fail_dict

    def process_action(self, action_input: str):
        """
        Fully process an action input.
        First parses the input, then resolves the parsed action, and returns feedback and goal achievement.
        """
        # PARSING PHASE
        parsed, parse_result, fail = self.parse_action_input(action_input)
        if not parsed:
            return self.goals_achieved, parse_result, fail
        else:
            # RESOLUTION PHASE
            # get visible/accessible entities before resolution:
            prior_visibles = set(self.get_player_room_contents_visible())
            # resolve action:
            resolved, resolution_result, fail = self.resolve_action(parse_result)
            if not resolved:
                return self.goals_achieved, resolution_result, fail
            else:
                logger.info(f"Resolution result: {resolution_result}")
                # get action feedback template:
                feedback_template = self.action_types[parse_result['type']]['feedback_template']
                feedback_jinja = jinja2.Template(feedback_template)
                template_tags = ["thing", "inventory_desc", "prep", "target", "room_desc"]
                jinja_args = dict()
                for template_tag in template_tags:
                    if template_tag in feedback_template:
                        if template_tag == "thing":
                            jinja_args[template_tag] = self._get_inst_str(resolution_result[1])
                        if template_tag == "inventory_desc":
                            jinja_args[template_tag] = self.get_inventory_desc()
                        if template_tag == "prep":
                            jinja_args[template_tag] = resolution_result[0]
                        if template_tag == "target":
                            jinja_args[template_tag] = self._get_inst_str(resolution_result[2])
                        if template_tag == "room_desc":
                            jinja_args[template_tag] = self.get_full_room_desc()
                # fill feedback template:
                base_result_str = feedback_jinja.render(jinja_args)
                # check goal achievement:
                self.goals_achieved = self.goal_state & self.world_state
                goals_achieved_response = list(self.goal_state & self.world_state)
                # convert to goal states to string version:
                for goal_state_idx, goal_state in enumerate(goals_achieved_response):
                    goals_achieved_response[goal_state_idx] = fact_tuple_to_str(goal_state)
                goals_achieved_response = set(goals_achieved_response)
                # check for newly visible/accessible entities:
                post_visibles = set(self.get_player_room_contents_visible())
                changed_visibles = post_visibles.difference(prior_visibles)
                # feedback on newly visible/accessible entities in current room:
                if changed_visibles and not parse_result['type'] == "go":
                    visible_content_state_strs = list()
                    for thing in changed_visibles:
                        for fact in self.world_state:
                            if fact[0] == 'in' and fact[1] == thing:
                                visible_content_state_strs.append(f"There is a {self._get_inst_str(thing)} in the {self._get_inst_str(fact[2])}.")
                    visible_content_state_combined = " ".join(visible_content_state_strs)
                    if visible_content_state_combined:
                        visible_content_state_combined = " " + visible_content_state_combined
                    return goals_achieved_response, f"{base_result_str}{visible_content_state_combined}", {}
                else:  # 'go' feedback with description of newly entered room:
                    return goals_achieved_response, base_result_str, {}

    def execute_optimal_solution(self):
        """
        Run through the game_instance's optimal solution.
        Used to verify parity of IF interpreter and solution generation.
        """
        print(self.get_full_room_desc())
        for command in self.game_instance["optimal_commands"]:
            print(f"> {command}")
            goals_achieved, response, fail = self.process_action(command)
            print(response)
            print("Goals achieved:", goals_achieved)
            print("Fail:", fail)
            print()

    def execute_plan_sequence(self, command_sequence: list) -> List:
        """
        Execute a command sequence plan and return results up to first failure.
        Used for plan logging and evaluation.
        Returns a list of action processing results including first failed plan action.
        """
        logger.info(f"Plan command sequence: {command_sequence}")
        # deepcopy world state before plan execution to assure proper reversion:
        pre_plan_world_state = deepcopy(self.world_state)

        result_sequence: list = list()
        world_state_change_count: int = 0
        for cmd_idx, command in enumerate(command_sequence):
            logger.info(f"Resolving plan action {cmd_idx}: {command}")
            # get result as list for mutability:
            result = list(self.process_action(command))
            # convert result goals achieved to list for JSON dumping:
            result[0] = list(result[0])
            result_sequence.append(result)
            # check for command failure:
            # result[2] is fail info; if it is truthy, the command failed
            if result[2]:
                # stop executing commands at the first failure
                logger.info(f"Plan sequence failed at step {cmd_idx}")
                logger.info(f"Plan sequence fail dict: {result[2]}")
                logger.info(f"Plan world state change count at failure: {world_state_change_count}")
                break
            else:
                world_state_change_count += 1
                logger.info(f"New plan world state change count: {world_state_change_count}")

        # revert the world state to before plan execution if it changed:
        if world_state_change_count:
            logger.info(f"Plan world state change count: {world_state_change_count}; reverting changes")
            # deepcopy world state after plan execution to prevent reference issues:
            post_plan_world_state = deepcopy(self.world_state)
            logger.info(f"World state history before reverting: {self.world_state_history}")
            logger.info(f"World state history length before reverting: {len(self.world_state_history)}")
            # reset world state history to before executed plan:
            self.world_state_history = self.world_state_history[:-world_state_change_count]
            logger.info(f"World state history after reverting: {self.world_state_history}")
            logger.info(f"World state history length after reverting: {len(self.world_state_history)}")
            # check that world state has been properly reset:
            if self.world_state_history[-1] == pre_plan_world_state:
                logger.info(f"Last world state history item matches pre-plan world state")
            else:
                logger.info(f"Last world state history item DOES NOT match pre-plan world state")
            if self.world_state_history[-1] == post_plan_world_state:
                logger.info(f"Last world state history item DOES match post-plan world state")
            else:
                logger.info(f"Last world state history item does not match post-plan world state")
            # reset world state to before plan execution:
            self.world_state = deepcopy(self.world_state_history[-1])
            # double-check that world state has been reset properly:
            if self.world_state == pre_plan_world_state:
                logger.info(f"Pre-plan world state matches reverted post-plan world state")
            else:
                logger.info(f"Pre-plan world state does not match reverted post-plan world state")
            # log specific reverted fact changes from plan:
            post_plan_changes = post_plan_world_state.difference(self.world_state)
            logger.info(f"Reverted plan world state changes: {post_plan_changes}")
        else:
            logger.info(f"Plan world state change count: {world_state_change_count}; no changes to revert")

        logger.info(f"Plan result sequence: {result_sequence}")

        return result_sequence


if __name__ == "__main__":
    PATH = ""
    # example game instance:
    game_instance_exmpl = {"game_id": 11, "variant": "basic",
     "prompt": "You are playing a text adventure game. I will describe what you can perceive in the game. You write the single action you want to take in the game starting with >. Only reply with actions.\nFor example:\n> examine cupboard\n\nYour goal for this game is: Put the book on the table, the plate on the table and the mop on the table.\n\n",
     "initial_state": ["at(kitchen1floor,kitchen1)", "at(pantry1floor,pantry1)", "at(hallway1floor,hallway1)",
                       "at(livingroom1floor,livingroom1)", "at(broomcloset1floor,broomcloset1)",
                       "at(bedroom1floor,bedroom1)", "at(table1,livingroom1)", "at(sidetable1,livingroom1)",
                       "at(counter1,kitchen1)", "at(refrigerator1,pantry1)", "at(cupboard1,kitchen1)",
                       "at(wardrobe1,bedroom1)", "at(shelf1,livingroom1)", "at(freezer1,pantry1)",
                       "at(pottedplant1,hallway1)", "at(chair1,livingroom1)", "at(bed1,bedroom1)",
                       "at(couch1,livingroom1)", "at(broom1,broomcloset1)", "at(mop1,broomcloset1)",
                       "at(sandwich1,pantry1)", "at(apple1,pantry1)", "at(banana1,pantry1)", "at(orange1,pantry1)",
                       "at(peach1,pantry1)", "at(plate1,kitchen1)", "at(book1,livingroom1)", "at(pillow1,bedroom1)",
                       "at(player1,bedroom1)", "type(kitchen1floor,floor)", "type(pantry1floor,floor)",
                       "type(hallway1floor,floor)", "type(livingroom1floor,floor)", "type(broomcloset1floor,floor)",
                       "type(bedroom1floor,floor)", "type(player1,player)", "type(table1,table)",
                       "type(sidetable1,sidetable)", "type(counter1,counter)", "type(refrigerator1,refrigerator)",
                       "type(cupboard1,cupboard)", "type(wardrobe1,wardrobe)", "type(shelf1,shelf)",
                       "type(freezer1,freezer)", "type(pottedplant1,pottedplant)", "type(chair1,chair)",
                       "type(bed1,bed)", "type(couch1,couch)", "type(broom1,broom)", "type(mop1,mop)",
                       "type(sandwich1,sandwich)", "type(apple1,apple)", "type(banana1,banana)", "type(orange1,orange)",
                       "type(peach1,peach)", "type(plate1,plate)", "type(book1,book)", "type(pillow1,pillow)",
                       "room(kitchen1,kitchen)", "room(pantry1,pantry)", "room(hallway1,hallway)",
                       "room(livingroom1,livingroom)", "room(broomcloset1,broomcloset)", "room(bedroom1,bedroom)",
                       "support(kitchen1floor)", "support(pantry1floor)", "support(hallway1floor)",
                       "support(livingroom1floor)", "support(broomcloset1floor)", "support(bedroom1floor)",
                       "support(table1)", "support(sidetable1)", "support(counter1)", "support(shelf1)",
                       "support(bed1)", "on(book1,sidetable1)", "on(plate1,kitchen1floor)",
                       "on(mop1,broomcloset1floor)", "on(broom1,broomcloset1floor)", "on(pottedplant1,hallway1floor)",
                       "container(refrigerator1)", "container(cupboard1)", "container(wardrobe1)",
                       "container(freezer1)", "in(pillow1,wardrobe1)", "in(peach1,refrigerator1)",
                       "in(orange1,refrigerator1)", "in(banana1,refrigerator1)", "in(apple1,refrigerator1)",
                       "in(sandwich1,refrigerator1)", "exit(kitchen1,pantry1)", "exit(kitchen1,livingroom1)",
                       "exit(kitchen1,hallway1)", "exit(pantry1,kitchen1)", "exit(hallway1,kitchen1)",
                       "exit(hallway1,livingroom1)", "exit(hallway1,broomcloset1)", "exit(livingroom1,kitchen1)",
                       "exit(livingroom1,hallway1)", "exit(broomcloset1,hallway1)", "exit(bedroom1,livingroom1)",
                       "exit(livingroom1,bedroom1)", "openable(refrigerator1)", "openable(cupboard1)",
                       "openable(wardrobe1)", "openable(freezer1)", "closed(refrigerator1)", "closed(cupboard1)",
                       "closed(wardrobe1)", "closed(freezer1)", "takeable(pottedplant1)", "takeable(broom1)",
                       "takeable(mop1)", "takeable(sandwich1)", "takeable(apple1)", "takeable(banana1)",
                       "takeable(orange1)", "takeable(peach1)", "takeable(plate1)", "takeable(book1)",
                       "takeable(pillow1)", "movable(pottedplant1)", "movable(broom1)", "movable(mop1)",
                       "movable(sandwich1)", "movable(apple1)", "movable(banana1)", "movable(orange1)",
                       "movable(peach1)", "movable(plate1)", "movable(book1)", "movable(pillow1)",
                       "needs_support(pottedplant1)", "needs_support(broom1)", "needs_support(mop1)",
                       "needs_support(sandwich1)", "needs_support(apple1)", "needs_support(banana1)",
                       "needs_support(orange1)", "needs_support(peach1)", "needs_support(plate1)",
                       "needs_support(book1)", "needs_support(pillow1)"],
     "goal_state": ["on(book1,table1)", "on(plate1,table1)", "on(mop1,table1)"], "max_turns": 50, "optimal_turns": 12,
     "optimal_solution": [["go", "livingroom1"], ["put", "book1", "table1"], ["go", "kitchen1"], ["take", "plate1"],
                          ["go", "livingroom1"], ["put", "plate1", "table1"], ["go", "hallway1"],
                          ["go", "broomcloset1"], ["take", "mop1"], ["go", "hallway1"], ["go", "livingroom1"],
                          ["put", "mop1", "table1"]],
     "optimal_commands": ["go living room", "put book on table", "go kitchen", "take plate", "go living room",
                          "put plate on table", "go hallway", "go broom closet", "take mop", "go hallway",
                          "go living room", "put mop on table"], "action_definitions": ["basic_actions.json"],
     "room_definitions": ["home_rooms.json"], "entity_definitions": ["home_entities.json"]}
    # initialize test interpreter:
    test_interpreter = AdventureIFInterpreter(game_instance_exmpl)
    # run optimal solution:
    test_interpreter.execute_optimal_solution()
