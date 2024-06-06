import os
import re
import json
import itertools
from dataclasses import dataclass, field

import toml

from .scaffold import get_resource_path
from lict.constants import ScopeToken
from lict.constants import ScopeElement


@dataclass
class LicenseSpread:
    """
    Define the license spread mechanism occur in which usage conditions.

    Properties:
        spread_conditions: list[str], list of usage conditions that will make a license spread, although
            the license itself has no varility (same license).
        non_spread_conditions: list[str], list of usage conditions that will make a license not spread.
    """

    spread_conditions: list[str] = field(default_factory=list)
    non_spread_conditions: list[str] = field(default_factory=list)


@dataclass
class Config:
    """
    The Config store which usage conditions that will make a license spread or not.

    Properties:
        license_spread: LicenseSpread, define the spread conditions
        literal_mapping: dict[str, str], mapping of the usage literals to ScopeElment enum

    Methods:
        literal2enum(literal: str) -> str: convert usage literal to ScopeElement enum
        enum2literal(enum: str) -> set[str]: convert ScopeElement enum to usage literals
        from_toml(path: str) -> Config: load Config from a toml file
    """

    license_isolations: list[str] = field(default_factory=list)
    license_spread: LicenseSpread = field(default_factory=LicenseSpread)
    literal_mapping: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        self.license_spread = LicenseSpread(**self.license_spread)

    def literal2enum(self, literal: str) -> str:
        return self.literal_mapping.get(literal, "")

    def enum2literal(self, enum: str) -> set[str]:
        return {k for k, v in self.literal_mapping.items() if enum in v}

    @classmethod
    def from_toml(cls, path: str) -> "Config":
        config = os.path.basename(path).replace(".toml", "")
        return cls(**toml.load(path))


class Scope(dict[str, set[str]]):
    """
    Basic data structures for representing and calculating the scope of effectiveness of
    license terms.

    Properties:
        protect_scope: list[str], list of protect scope
        is_universal: bool, check if the scope is universal

    Methods:
        universe() -> Scope: return a universal scope
        from_dict(scope_dict: dict[str, list[str]]) -> Scope: create a Scope object from a dict
        from_str(scope_str: str) -> Scope: create a Scope object from a string
        negate() -> Scope: negate the scope

    Private Methods:
        _simplify(scope: Scope) -> Scope: simplify the scope

    Magic Methods:
        __contains__(other: object) -> bool: check if a scope contains another scope
        __or__(other: Scope) -> Scope: calculate the union of two scopes
        __bool__() -> bool: check if the scope is empty
        __and__(other: Scope) -> Scope: calculate the intersection of two scopes
        __str__() -> str: return the string representation of the scope
    """

    def __hash__(self) -> int:
        return hash(str(self))

    @classmethod
    def universe(cls) -> "Scope":
        return cls({ScopeToken.UNIVERSE: set()})

    @classmethod
    def from_dict(cls, scope_dict: dict[str, list[str]]) -> "Scope":
        return cls({k: set(v) for k, v in scope_dict.items()})

    @classmethod
    def from_str(cls, scope_str: str) -> "Scope":
        scope = cls()
        for k, v in json.loads(scope_str).items():
            scope[k] = set(v)
        return scope

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __and__(self, other: "Scope") -> "Scope":
        simplified_other = self._simplify(other)
        simplified_self = self._simplify(self)

        new = self.__class__()

        if simplified_self.get(ScopeToken.UNIVERSE, False) != False:
            for k in simplified_other:
                new[k] = simplified_other[k] | simplified_self[ScopeToken.UNIVERSE]

        if simplified_other.get(ScopeToken.UNIVERSE, False) != False:
            for k in simplified_self:
                new[k] = simplified_self[k] | simplified_other[ScopeToken.UNIVERSE]

        for k in simplified_self:
            if simplified_other.get(k, False) == False:
                continue

            new[k] = simplified_self[k] | simplified_other[k] | new.get(k, set())
        return self._simplify(new)

    def __contains__(self, other: object) -> bool:
        simplified_self = self._simplify(self)
        simplified_other = self._simplify(other)

        uncontains_scope = Scope({})

        for k in simplified_other:
            if simplified_self.get(k, False) != False:
                remains = simplified_self[k] - simplified_other[k]
                if remains:
                    uncontains_scope[k] = remains
            else:
                uncontains_scope[k] = simplified_other[k]

        if not uncontains_scope:
            return True

        if simplified_self.get(ScopeToken.UNIVERSE, False) == False:
            return False

        for k in uncontains_scope:
            if k in simplified_self[ScopeToken.UNIVERSE]:
                return False

        return True

    def __or__(self, other: "Scope") -> "Scope":
        simplified_other = self._simplify(other)
        simplified_self = self._simplify(self)

        new = self.__class__()
        visited_keys = []

        for k in simplified_self:
            if simplified_other.get(k, False) == False:
                new[k] = simplified_self[k]
                continue

            visited_keys.append(k)

            intersection = simplified_self[k] & simplified_other[k]
            if not intersection:
                new[k] = {}
                continue

            new[k] = intersection

        for k in simplified_other:

            if k in visited_keys:
                continue

            new[k] = simplified_other[k]
        return self._simplify(new)

    def __bool__(self) -> bool:
        return len(self._simplify(self).keys()) != 0

    def _simplify(self, scope: "Scope") -> "Scope":

        new = self.__class__()
        if scope.get(ScopeToken.UNIVERSE, False) == set():
            new[ScopeToken.UNIVERSE] = set()
            return new

        delete_flag = False
        for k in scope:
            for v in scope[k]:
                if k == v:
                    delete_flag = True
                    break
            if not delete_flag:
                new[k] = scope[k]
            delete_flag = False
        return new

    def negate(self) -> "Scope":
        if not self:
            return self.__class__.universe()

        new = self.__class__()
        for k in self:
            for v in self[k]:
                if new.get(v, False) == False:
                    new[v] = set()

                if k == ScopeToken.UNIVERSE:
                    new[v] = set()
                    continue

                new[v].add(k)
        return new

    def __str__(self) -> str:
        new_dict = {k: tuple(v) for k, v in self.items()}
        return json.dumps(new_dict)

    @property
    def protect_scope(self):
        return list(self.keys())

    @property
    def is_universal(self) -> bool:
        return self.get(ScopeToken.UNIVERSE, False) != False and self[ScopeToken.UNIVERSE] == set()


@dataclass
class ActionFeat:
    """
    Action (feature) class

    Properties:
        name: name of the action
        modal: modal of the action
        protect_scope: protect scope of the action
        escape_scope: escape scope of the action
        scope: scope of the action
        target: target of the action
    """

    name: str
    modal: str
    protect_scope: list
    escape_scope: list
    scope: Scope = field(default_factory=Scope)
    target: list = field(default_factory=list)

    def __post_init__(self):

        if self.protect_scope == []:
            self.protect_scope = [ScopeToken.UNIVERSE]

        if self.protect_scope == None:
            self.protect_scope = []

        self.scope = Scope({k: set(self.escape_scope) for k in self.protect_scope})


@dataclass
class LicenseFeat:
    """
    License (feature) class, represent the properties of a license.

    Properties:
        spdx_id: SPDX ID of the license
        can: dict[str, ActionFeat], action that can be done
        cannot: dict[str, ActionFeat], action that cannot be done
        must: dict[str, ActionFeat], action that must be done
        special: dict[str, ActionFeat], special action
        human_review: bool, check if the license need human review
    """

    spdx_id: str
    can: dict[str, ActionFeat] = field(default_factory=dict)
    cannot: dict[str, ActionFeat] = field(default_factory=dict)
    must: dict[str, ActionFeat] = field(default_factory=dict)
    special: dict[str, ActionFeat] = field(default_factory=dict)
    scope: dict[str, dict] = field(default_factory=dict)
    human_review: bool = field(default=True)

    def __post_init__(self):
        if isinstance(self.can, dict):
            self.can = {name: ActionFeat(name, **can, modal="can") for name, can in self.can.items()}
        if isinstance(self.cannot, dict):
            self.cannot = {name: ActionFeat(name, **cannot, modal="cannot") for name, cannot in self.cannot.items()}
        if isinstance(self.must, dict):
            self.must = {name: ActionFeat(name, **must, modal="must") for name, must in self.must.items()}
        if isinstance(self.special, dict):
            self.special = {
                name: ActionFeat(name, **special, modal="special") for name, special in self.special.items()
            }

    @property
    def features(self) -> list[ActionFeat]:
        return list(itertools.chain(self.can.values(), self.cannot.values(), self.must.values(), self.special.values()))

    @property
    def scope_elems(self) -> list[str]:
        return list(self.scope.keys())

    @classmethod
    def from_toml(cls, path: str) -> "LicenseFeat":
        spdx_id = os.path.basename(path).replace(".toml", "")
        return cls(spdx_id, **toml.load(path))


@dataclass
class Schemas:
    """
    Schema for licenses, that define the properties of actions.

    Properties:
        actions: list[dict], list of actions
        action_index: dict[str, list[str], index of actions

    Methods:
        has_property(action: ActionFeat, property: str) -> bool: check if an action has a property
        properties() -> tuple[str]: return the properties of the actions

    Magic Methods:
        __getitem__(key: str) -> dict: get the action properties
    """

    actions: list[dict]

    action_index: dict[str, list[str]] = field(default_factory=dict)

    def __post_init__(self):
        for action_name, action_property in self.actions.items():

            for key, value in action_property.items():
                if value:
                    if key not in self.action_index:
                        self.action_index[key] = []
                    self.action_index[key] = action_name

    @property
    def properties(self) -> tuple[str]:
        return tuple(self.action_index.keys())

    def has_property(self, action: ActionFeat, property: str) -> bool:
        if action.name in self.action_index.get(property, []):
            if action.modal in self[action.name][property]:
                return True

    def __getitem__(self, key: str) -> dict:
        return self.actions[key]

    @classmethod
    def from_toml(cls, path: str) -> "Schemas":
        return cls(**toml.load(path))


class ActionFeatOperator:
    """
    Operator class for ActionFeat.
    """

    @staticmethod
    def intersect(feat_a: ActionFeat, feat_b: ActionFeat) -> Scope:
        return feat_a.scope & feat_b.scope

    @staticmethod
    def contains(feat_a: ActionFeat, feat_b: ActionFeat) -> Scope:
        return feat_b.scope in feat_a.scope

    @staticmethod
    def negate(feat: ActionFeat) -> Scope:
        return feat.scope.negate()


class DualUnit(dict):
    """
    Dual unit class. Use to represent the unit of dual licenses.

    Properties:
        spdx_id: str, SPDX ID of the license
        condition: str, condition of the license
        exceptions: list[str], list of exceptions

    Magic Methods:
        __hash__() -> int: hash the object
    """

    def __init__(self, spdx_id: str, condition="", exceptions=[]):
        super().__init__(spdx_id=spdx_id, condition=condition, exceptions=exceptions)

    def __hash__(self):
        return hash((self["spdx_id"], self.get("condition", ""), tuple(self.get("exceptions", []))))


class DualLicense(set):
    """
    Dual licenses class. Use to represent dual licenses in a set[tuple[tuple[str, str]]] structure.
    """

    @classmethod
    def from_list(cls, licenses: list[list[DualUnit]]) -> "DualLicense":
        return cls(tuple({DualUnit(**license) for license in group}) for group in licenses)

    @classmethod
    def from_str(cls, licenses: str) -> "DualLicense":
        licenses = json.loads(licenses)
        return cls.from_list(licenses)

    def __bool__(self) -> bool:
        return len(self) != 0 and self != {()}

    def __str__(self) -> str:
        return json.dumps(self, default=lambda o: list(o))

    def __and__(self, other: "DualLicense") -> "DualLicense":
        return DualLicense.from_list([tuple({*lic1, *lic2}) for lic1, lic2 in itertools.product(self, other)])

    def __iand__(self, other: "DualLicense") -> "DualLicense":
        return self.__and__(other)

    def __or__(self, other: "DualLicense") -> "DualLicense":
        return DualLicense.from_list([*self, *other])

    def __ior__(self, other: "DualLicense") -> "DualLicense":
        return self.__or__(other)

    def add_condition(self, conditon: str) -> "DualLicense":
        new = DualLicense()
        for group in self:
            new_group = set()
            for unit in group:

                new_group.add(DualUnit(unit["spdx_id"], conditon, unit["exceptions"]))
                if not unit["condition"] or unit["condition"] == conditon:
                    new_group.add(unit)
                else:
                    new_group.update([(license, unit["condition"]), (license, conditon)])
            new.add(tuple(new_group))
        return new

    def get_outbound(self, config: Config) -> "DualLicense":
        default_spread = "DEFAULT" in config.license_spread.spread_conditions

        if not self:
            return self

        new = DualLicense()
        for group in self:
            new_group = set()
            for license in group:

                if license["condition"] in config.license_spread.spread_conditions:
                    new_group.add(DualUnit(license["spdx_id"], None, license["exceptions"]))

                elif default_spread and license["condition"] not in config.license_spread.spread_conditions:
                    new_group.add(DualUnit(license["spdx_id"], None, license["exceptions"]))

            new.add(tuple(new_group))
        return new


class SPDXParser:

    def __call__(self, expression, expand=False, proprocessor: callable = None):
        self.expression = expression
        self.tokens = []
        self.current = 0
        self.expression = self.parse(proprocessor)
        if expand:
            return self.expand_expression(self.expression)
        return self.expression

    def tokenize(self):
        token_pattern = re.compile(r"\s*(WITH|AND|OR|\(|\)|[a-zA-Z0-9\.-]+)\s*")
        self.tokens = token_pattern.findall(self.expression)

    def parse(self, proprocessor: callable = None):
        self.tokenize()
        result = self.parse_expression(proprocessor)
        if self.current < len(self.tokens):
            raise SyntaxError(f"Unexpected token at the end of expression {self.tokens}")
        return result

    def parse_expression(self, proprocessor: callable = None):
        terms = (self.parse_term(proprocessor),)
        while self.current < len(self.tokens) and self.tokens[self.current] in ("AND", "OR", "WITH"):
            op = self.tokens[self.current]
            if op == "WITH":
                self.current += 1
                if self.current >= len(self.tokens):
                    raise SyntaxError("Unexpected end of expression")

                if isinstance(terms[-1], tuple):
                    raise SyntaxError("WITH operator must be followed by single spdx not compound expression")

                terms[-1]["exceptions"] = [*terms[-1]["exceptions"], self.tokens[self.current]]
                self.current += 1
                continue
            self.current += 1
            terms = terms + (op, self.parse_term(proprocessor))
        if len(terms) == 1:
            return terms
        return terms

    def parse_term(self, proprocessor: callable = None):
        if self.current >= len(self.tokens):
            raise SyntaxError("Unexpected end of expression")

        token = self.tokens[self.current]
        if token == "(":
            self.current += 1
            expr = self.parse_expression()
            if self.current >= len(self.tokens) or self.tokens[self.current] != ")":
                raise SyntaxError("Missing closing parenthesis")
            self.current += 1
            return expr
        elif token == ")":
            raise SyntaxError("Unexpected closing parenthesis")
        else:
            self.current += 1
            return DualUnit(proprocessor(token)) if proprocessor else DualUnit(token)

    def expand_expression(self, expression):
        idx = 0
        previous_op = "AND"
        results = DualLicense.from_list([[]])
        while idx < len(expression):
            if expression[idx] == "AND":
                previous_op = "AND"
                idx += 1
                continue

            if expression[idx] == "OR":
                previous_op = "OR"
                idx += 1
                continue

            if isinstance(expression[idx], tuple):
                current_results = self.expand_expression(expression[idx])
                idx += 1
            elif isinstance(expression[idx], DualUnit):
                current_results = DualLicense.from_list([[expression[idx]]])

                idx += 1

            if previous_op == "AND":
                results &= current_results
            elif previous_op == "OR":
                results |= current_results
            else:
                raise SyntaxError(f"Unexpected token {expression[idx]}")

        return results


def load_licenses(path: str = None) -> dict[str, LicenseFeat]:
    """
    Load licenses from a directory of toml files

    Args:
        path: path to directory of toml files

    Returns:
        dict[str, LicenseFeat]: dictionary of licenses
    """

    if path is None:
        path = get_resource_path(resource_name="resources.licenses")

    paths = filter(lambda x: not x.startswith("schemas") and x.endswith(".toml"), os.listdir(path))

    return {lic.spdx_id: lic for p in paths if (lic := LicenseFeat.from_toml(os.path.join(path, p)))}


def load_exceptions(path: str = None) -> dict[str, LicenseFeat]:
    """
    Load exceptions from a directory of toml files

    Args:
        path: path to directory of toml files

    Returns:
        dict[str, LicenseFeat]: dictionary of exceptions
    """
    if path is None:
        path = get_resource_path(resource_name="resources.exceptions")

    paths = filter(lambda x: not x.startswith("schemas") and x.endswith(".toml"), os.listdir(path))

    return {lic.spdx_id: lic for p in paths if (lic := LicenseFeat.from_toml(os.path.join(path, p)))}


def load_schemas(path: str = None) -> Schemas:
    """
    Load schema from a toml file

    Args:
        path: path to toml file

    Returns:
        Schemas: schema object
    """

    if path is None:
        path = get_resource_path()

    return Schemas.from_toml(os.path.join(path, "schemas.toml"))


def load_config(path: str = None) -> Config:
    """
    Load Config from a toml file

    Args:
        path: path to toml file

    Returns:
        Config: Config object
    """

    if path is None:
        path = os.path.join(get_resource_path(resource_name="config"), "default.toml")

    return Config.from_toml(path)
