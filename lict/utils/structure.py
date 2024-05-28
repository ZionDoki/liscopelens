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

    spread_conditions: list[str] = field(default_factory=list)
    non_spread_conditions: list[str] = field(default_factory=list)


@dataclass
class Config:

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
    Base class for license scope
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
    License (feature) class
    """

    spdx_id: str
    can: dict[str, ActionFeat] = field(default_factory=dict)
    cannot: dict[str, ActionFeat] = field(default_factory=dict)
    must: dict[str, ActionFeat] = field(default_factory=dict)
    special: dict[str, ActionFeat] = field(default_factory=dict)
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

    @classmethod
    def from_toml(cls, path: str) -> list["LicenseFeat"]:
        spdx_id = os.path.basename(path).replace(".toml", "")
        return cls(spdx_id, **toml.load(path))


@dataclass
class Schemas:
    """
    Schema for licenses
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

    @staticmethod
    def intersect(feat_a: ActionFeat, feat_b: ActionFeat) -> Scope:
        return feat_a.scope & feat_b.scope

    @staticmethod
    def contains(feat_a: ActionFeat, feat_b: ActionFeat) -> Scope:
        return feat_b.scope in feat_a.scope

    @staticmethod
    def negate(feat: ActionFeat) -> Scope:
        return feat.scope.negate()


class DualLicense(set):
    """
    Dual licenses class. Use to represent dual licenses in a set[tuple[tuple[str, str]]] structure.
    """

    @classmethod
    def from_list(cls, licenses: list[list[tuple[str, str]]]) -> "DualLicense":
        return cls(tuple({tuple(license) for license in group}) for group in licenses)

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
            for license, cond in group:
                if not cond or cond == conditon:
                    new_group.add((license, conditon))
                else:
                    new_group.update([(license, cond), (license, conditon)])
            new.add(tuple(new_group))
        return new

    def get_outbound(self, config: Config) -> "DualLicense":

        if not self:
            return self

        new = DualLicense()
        for group in self:
            new_group = set()
            for lic, conds in group:
                if conds in config.license_spread.spread_conditions:
                    new_group.add((lic, None))
            new.add(tuple(new_group))
        return new


class SPDXParser:

    def __call__(self, expression, expand=False):
        self.expression = expression
        self.tokens = []
        self.current = 0
        self.expression = self.parse()
        if expand:
            return self.expand_expression(self.expression)
        return self.expression

    def tokenize(self):
        token_pattern = re.compile(r"\s*(WITH|AND|OR|\(|\)|[a-zA-Z0-9\.-]+)\s*")
        self.tokens = token_pattern.findall(self.expression)

    def parse(self):
        self.tokenize()
        result = self.parse_expression()
        if self.current < len(self.tokens):
            raise SyntaxError(f"Unexpected token at the end of expression {self.tokens}")
        return result

    def parse_expression(self):
        terms = (self.parse_term(),)
        while self.current < len(self.tokens) and self.tokens[self.current] in ("AND", "OR", "WITH"):
            op = self.tokens[self.current]
            self.current += 1
            terms = terms + (op, self.parse_term())
        if len(terms) == 1:
            return terms
        return terms

    def parse_term(self):
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
            return token

    def expand_expression(self, expression) -> "DualLicense":
        results = DualLicense.from_list([[]])
        and_flag = True
        or_flag = False
        for exp in expression:
            if isinstance(exp, tuple):
                exp_results = self.expand_expression(exp)
                if and_flag:
                    results &= exp_results
                    and_flag = False
                elif or_flag:
                    if results == {()}:
                        results = exp_results
                    else:
                        results |= exp_results
                    or_flag = False
                else:
                    raise SyntaxError("Invalid expression")
            else:
                if and_flag and or_flag:
                    raise SyntaxError("Invalid expression")
                if and_flag:
                    results &= DualLicense.from_list([[(exp, None)]])
                    and_flag = False
                elif or_flag:
                    if results == {()}:
                        results = DualLicense.from_list([[(exp, None)]])
                    else:
                        results |= DualLicense.from_list([[(exp, None)]])
                    or_flag = False
                elif exp == "AND" or exp == "WITH":
                    and_flag = True
                elif exp == "OR":
                    or_flag = True
                else:
                    raise SyntaxError("Invalid expression")
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
        path = get_resource_path()

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
