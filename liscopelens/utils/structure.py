#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# Copyright (c) 2024 Lanzhou University
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""
The structure module defines the basic data structures for representing and calculating the scope of effectiveness of
license terms. The module also provides the operator class, parser class, and loader functions for the license and
exception licenses.
"""

import os
import re
import json
import itertools
from typing import Optional, Callable
from dataclasses import dataclass, field

import toml

from liscopelens.constants import ScopeToken
from .scaffold import get_resource_path


@dataclass
class LicenseSpread(dict):
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
        blacklist: list[str], list of licenses that will be black listed
        license_isolations: list[str], list of licenses that will be isolated
        literal_mapping: dict[str, str], mapping of the usage literals to ScopeElment enum
        permissiver_spreads: list[str], list of conditions that will make a permissive license spread
        edge_literal_mapping: dict[str, str], mapping of edge type literals to enum
        edge_isolations: list[str], list of edge conditions that will block license propagation
        edge_permissive_spreads: list[str], list of edge conditions that will make permissive license spread
        default_edge_behavior: str, default behavior for unmapped edge types ("allow", "block", "inherit")
    Methods:
        literal2enum(literal: str) -> str: convert usage literal to ScopeElement enum
        enum2literal(enum: str) -> set[str]: convert ScopeElement enum to usage literals
        edge_literal2enum(literal: str) -> str: convert edge type literal to enum
        enum2edge_literal(enum: str) -> set[str]: convert enum to edge type literals
        from_toml(path: str) -> Config: load Config from a toml file
    """

    blacklist: list[str] = field(default_factory=list)
    license_isolations: list[str] = field(default_factory=list)
    permissive_spreads: list[str] = field(default_factory=list)
    literal_mapping: dict[str, str] = field(default_factory=dict)
    edge_literal_mapping: dict[str, str] = field(default_factory=dict)
    edge_isolations: list[str] = field(default_factory=list)
    edge_permissive_spreads: list[str] = field(default_factory=list)
    default_edge_behavior: str = field(default="inherit")

    def literal2enum(self, literal: str) -> Optional[str]:
        """
        Convert usage literal to ScopeElement enum.

        Usage:
        ```
        config = Config(literal_mapping={"COPYLEFT": "COMPLIANCE"})
        print(config.literal2enum("COPYLEFT"))
        # Output: "COMPLIANCE"
        ```

        Args:
            literal: str, usage literal

        Returns:
            str: ScopeElement enum
        """
        return self.literal_mapping.get(literal, None)

    def enum2literal(self, enum: str) -> set[str]:
        """
        Convert ScopeElement enum to usage literals.

        Usage:
        ```
        config = Config(literal_mapping={"COPYLEFT": "COMPLIANCE"})
        print(config.enum2literal("COMPLIANCE"))
        # Output: {"COPYLEFT"}
        ```

        Args:
            enum: str, ScopeElement enum

        Returns:
            set[str]: set of usage literals
        """
        return {k for k, v in self.literal_mapping.items() if enum in v}

    def edge_literal2enum(self, literal: str) -> Optional[str]:
        """
        Convert edge type literal to enum.

        Usage:
        ```
        config = Config(edge_literal_mapping={"depends_on": "DEPENDENCY"})
        print(config.edge_literal2enum("depends_on"))
        # Output: "DEPENDENCY"
        ```

        Args:
            literal: str, edge type literal

        Returns:
            str: edge type enum
        """
        return self.edge_literal_mapping.get(literal, None)

    def enum2edge_literal(self, enum: str) -> set[str]:
        """
        Convert enum to edge type literals.

        Usage:
        ```
        config = Config(edge_literal_mapping={"depends_on": "DEPENDENCY", "uses": "DEPENDENCY"})
        print(config.enum2edge_literal("DEPENDENCY"))
        # Output: {"depends_on", "uses"}
        ```

        Args:
            enum: str, edge type enum

        Returns:
            set[str]: set of edge type literals
        """
        return {k for k, v in self.edge_literal_mapping.items() if enum in v}

    @classmethod
    def from_toml(cls, path: str) -> "Config":
        return cls(**toml.load(path))


class Scope(dict[str, set[str]]):
    """
    Basic data structures for representing and calculating the scope of effectiveness of
    license terms.

    Usage:
        ```python
        scope = Scope({"a": set(["b", "c"]), "d": set(["e"])})
        ```

        In this example, the scope is defined as:
        ```
        a: b, c # in the scope of a, b and c are excluded
        d: e    # in the scope of d, e is excluded
        ```

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
        for _, v in self.items():
            if not isinstance(v, set):
                raise TypeError("The value of a scope must be a set")

    def __and__(self, other: "Scope") -> "Scope":
        simplified_other = self._simplify(other)
        simplified_self = self._simplify(self)

        new = self.__class__()

        if simplified_self.get(ScopeToken.UNIVERSE, False) is not False:
            for k in simplified_other:
                new[k] = simplified_other[k] | simplified_self[ScopeToken.UNIVERSE]

        if simplified_other.get(ScopeToken.UNIVERSE, False) is not False:
            for k in simplified_self:
                new[k] = simplified_self[k] | simplified_other[ScopeToken.UNIVERSE]

        for k in simplified_self:
            if simplified_other.get(k, False) is False:
                continue

            new[k] = simplified_self[k] | simplified_other[k] | new.get(k, set())
        return self._simplify(new)

    def __contains__(self, other: Optional["Scope"]) -> bool:

        if other is None:
            if not self:
                return True
            return False

        simplified_self = self._simplify(self)
        simplified_other = self._simplify(other)

        uncontains_scope = Scope({})

        if simplified_other == uncontains_scope:
            return super().__contains__(ScopeToken.UNIVERSE)

        for k in simplified_other:
            if simplified_self.get(k, False) is not False:
                remains = simplified_self[k] - simplified_other[k]

                if remains:
                    uncontains_scope[k] = remains
            else:
                uncontains_scope[k] = simplified_other[k]

        if not uncontains_scope:
            return True

        if simplified_self.get(ScopeToken.UNIVERSE, False) is False:
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
            if simplified_other.get(k, False) is False:
                new[k] = simplified_self[k]
                continue

            visited_keys.append(k)

            intersection = simplified_self[k] & simplified_other[k]
            if not intersection:
                new[k] = set()
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
    protect_scope: Optional[list]
    escape_scope: list
    scope: Scope = field(default_factory=Scope)
    target: list = field(default_factory=list)

    @classmethod
    def factory(
        cls,
        name: str,
        modal: str,
        protect_scope: Optional[list] = None,
        escape_scope: Optional[list] = None,
        scope: Optional[Scope] = None,
        target: Optional[list] = None,
    ):
        if escape_scope is None:
            escape_scope = []

        if scope is None:
            scope = Scope()

        if target is None:
            target = []

        return cls(name, modal, protect_scope, escape_scope, scope, target)

    def __post_init__(self):

        if self.protect_scope is None:
            self.protect_scope = []

        elif len(self.protect_scope) == 0:
            self.protect_scope = [ScopeToken.UNIVERSE]

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
        default_target: list[str], default target licenses for exception (only for exceptions)
    """

    spdx_id: str
    can: dict[str, ActionFeat] = field(default_factory=dict)
    cannot: dict[str, ActionFeat] = field(default_factory=dict)
    must: dict[str, ActionFeat] = field(default_factory=dict)
    special: dict[str, ActionFeat] = field(default_factory=dict)
    scope: dict[str, dict] = field(default_factory=dict)
    human_review: bool = field(default=True)
    default_target: list[str] = field(default_factory=list)

    def __post_init__(self):
        if isinstance(self.can, dict):
            self.can = {
                name: (can if isinstance(can, ActionFeat) else ActionFeat(name, **can, modal="can"))
                for name, can in self.can.items()
            }
        if isinstance(self.cannot, dict):
            self.cannot = {
                name: (cannot if isinstance(cannot, ActionFeat) else ActionFeat(name, **cannot, modal="cannot"))
                for name, cannot in self.cannot.items()
            }
        if isinstance(self.must, dict):
            self.must = {
                name: (must if isinstance(must, ActionFeat) else ActionFeat(name, **must, modal="must"))
                for name, must in self.must.items()
            }
        if isinstance(self.special, dict):
            self.special = {
                name: (special if isinstance(special, ActionFeat) else ActionFeat(name, **special, modal="special"))
                for name, special in self.special.items()
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

    def cover_from(self, other: "LicenseFeat") -> "LicenseFeat":
        """
        License add exception from another exception license. We call this behavior as cover because
        the exception license will cover the original license. Almost all cases, the exception license
        will have less restriction than the original license and add some exception to the original license.

        ! Attention: this method do not implement that multiple exception licenses can cover the original license
        ! work like a union operation. This method only cover the original license with a single exception license.
        """
        return self.__class__(
            spdx_id=self.spdx_id + "-with-" + other.spdx_id,
            can={**self.can, **other.can},
            cannot={**self.cannot, **other.cannot},
            must={**self.must, **other.must},
            special={**self.special, **other.special},
        )


@dataclass
class Schemas:
    """
    Schema for licenses, that define the properties of actions.

    Properties:
        actions: dict of actions
        action_index: dict[str, list[str], index of actions

    Methods:
        has_property(action: ActionFeat, property: str) -> bool: check if an action has a property
        properties() -> tuple[str]: return the properties of the actions

    Magic Methods:
        __getitem__(key: str) -> dict: get the action properties
    """

    actions: dict

    action_index: dict[str, list[str]] = field(default_factory=dict)

    def __post_init__(self):
        for action_name, action_property in self.actions.items():

            for key, value in action_property.items():
                if value:
                    if key not in self.action_index:
                        self.action_index[key] = []
                    self.action_index[key] = action_name

    @property
    def properties(self) -> tuple[str, ...]:
        """Get the properties of the actions."""
        return tuple(self.action_index.keys())

    def has_property(self, action: ActionFeat, prop: str) -> Optional[bool]:
        """Check if an action has a property."""
        if action.name in self.action_index.get(prop, []):
            if action.modal in self[action.name][prop]:
                return True

    def __getitem__(self, key: str) -> dict:
        return self.actions[key]

    @classmethod
    def from_toml(cls, path: str) -> "Schemas":
        """Load schema from a toml file."""
        return cls(**toml.load(path))


class ActionFeatOperator:
    """
    Operator class for ActionFeat.
    """

    @staticmethod
    def intersect(feat_a: ActionFeat, feat_b: ActionFeat) -> Scope:
        return feat_a.scope & feat_b.scope

    @staticmethod
    def contains(feat_a: ActionFeat, feat_b: ActionFeat) -> bool:
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

    __spdx_id_with_exceptions: Optional[str] = None

    def __init__(self, spdx_id: str, condition: Optional[str] = None, exceptions: Optional[list[str]] = None):
        if not exceptions:
            exceptions = []

        super().__init__(spdx_id=spdx_id, condition=condition, exceptions=exceptions)

    def __hash__(self) -> int:
        return hash((self["spdx_id"], self.get("condition", ""), tuple(self.get("exceptions", []))))

    @property
    def unit_spdx(self) -> str:
        """
        Get the SPDX ID (with exceptions) of the license.

        Usage:
            ```python
            unit = DualUnit("MIT", condition="WITH", exceptions=["GPL-3.0-exception"])
            print(unit.unit_spdx)
            # Output: "MIT-with-GPL-3.0-exception"

            unit = DualUnit("MIT")
            print(unit.unit_spdx)
            # Output: "MIT"
            ```

        Returns:
            str: SPDX ID of the license with exceptions
        """
        if not self.__spdx_id_with_exceptions:
            self.__spdx_id_with_exceptions = "-with-".join([self["spdx_id"]] + sorted(self["exceptions"]))
        return self.__spdx_id_with_exceptions


class DualLicense(set[frozenset[DualUnit]]):
    """
    Dual licenses class. Use to represent dual licenses in a set[fronsenset[DualUnit]] structure.

    Properties:
        licenses_set: set[str], set of licenses

    Usage:
        Because the license have dual circumstances, we use a set of frozenset[DualUnit] to represent the dual licenses.
        Each fronzenset in the set represents a `group` of licenses.

        ```
        licenses = [
            [DualUnit("MIT"), DualUnit("GPL-3.0")],
            [DualUnit("MIT"), DualUnit("GPL-3.0", condition="WITH", exceptions=["GPL-3.0-exception"])]
        ]

        dual_license = DualLicense(licenses)
        # or
        dual_license = DualLicense.from_list(licenses)
        ```
    """

    @property
    def licenses_set(self) -> set[str]:
        """
        Get the set of licenses.

        Returns:
            set[str]: set of licenses
        """
        return {unit["spdx_id"] for group in self for unit in group}

    @classmethod
    def from_list(cls, licenses: list[list[DualUnit] | frozenset[DualUnit]]) -> "DualLicense":
        """
        Create a DualLicense object from a list of licenses.

        Usage:
            ```python
            licenses = [
                [DualUnit("MIT"), DualUnit("GPL-3.0")],
                [DualUnit("MIT"), DualUnit("GPL-3.0", condition="WITH", exceptions=["GPL-3.0-exception"])]
            ]
            dual_license = DualLicense.from_list(licenses)
            ```

        Args:
            licenses: list[list[DualUnit]], list of licenses

        Returns:
            DualLicense: a DualLicense
        """
        return cls(frozenset({DualUnit(**license) for license in group}) for group in licenses)

    @classmethod
    def from_str(cls, licenses: str) -> "DualLicense":
        """Create a DualLicense object from a string."""
        licenses_list = json.loads(licenses)
        return cls.from_list(licenses_list)

    def __bool__(self) -> bool:
        return len(self) != 0 and self != {frozenset()}

    def __str__(self) -> str:
        return json.dumps(self, default=list)

    def __and__(self, other: "DualLicense") -> "DualLicense":
        return DualLicense((lic1 | lic2 for lic1, lic2 in itertools.product(self, other)))

    def __iand__(self, other: "DualLicense") -> "DualLicense":
        return self.__and__(other)

    def __or__(self, other: "DualLicense") -> "DualLicense":
        return DualLicense.from_list([*self, *other])

    def __ior__(self, other: "DualLicense") -> "DualLicense":
        return self.__or__(other)

    def copy(self) -> "DualLicense":
        return self.__class__(super().copy())

    def to_spdx_expression(self, factor_common=True) -> str:
        """
        Convert the DualLicense to a canonical SPDX expression string (with simplification).

        Canonicalization rules (same as your docstring) + Simplification:
        - Ignore DualUnit.condition entirely.
        - Deduplicate identical licenses within a group after ignoring condition.
        - Represent exceptions using standard "WITH": "License WITH Exception".
        - For multiple exceptions on the same license, choose the first in lexicographic order.
        - Groups are AND-joined; top-level set is OR-joined.
        - Deterministic ordering (lexicographic) for stability.
        - Simplification (absorption): remove any group that is a strict superset of another group.
        """
        if not self:
            return ""

        def unit_token(u: DualUnit) -> str:
            spdx_id = (u.get("spdx_id") or "").strip()
            if not spdx_id:
                return ""
            excs = sorted(set(u.get("exceptions") or []))
            return f"{spdx_id} WITH {excs[0]}" if excs else spdx_id

        canon_groups: set[frozenset[str]] = set()
        for group in self:
            tokens = {unit_token(u) for u in group}
            tokens.discard("")
            if tokens:
                canon_groups.add(frozenset(tokens))
        if not canon_groups:
            return ""

        minimal_groups: list[frozenset[str]] = []
        for g in sorted(canon_groups, key=lambda s: (len(s), sorted(s))):
            if any(h.issubset(g) for h in minimal_groups):
                continue
            minimal_groups = [h for h in minimal_groups if not g.issubset(h) or g == h]
            minimal_groups.append(g)

        common: set[str] = set(minimal_groups[0])
        for g in minimal_groups[1:]:
            common &= g

        def fmt_group(g: frozenset[str]) -> str:
            toks = sorted(g)
            if not toks:
                return ""  # 空组意味着 True（已在因子提取中消化）
            expr = " AND ".join(toks)
            return f"({expr})" if len(toks) > 1 else expr

        if factor_common and common:
            residuals = [frozenset(g - common) for g in minimal_groups]
            # 若有某个 residual 为空，说明 OR 部分为 True，整体就是公共因子本身
            if any(len(r) == 0 for r in residuals):
                outer = " AND ".join(sorted(common))
                return outer

            # 正常：Common AND ( r1 OR r2 OR ... )
            outer = " AND ".join(sorted(common))
            inner = " OR ".join(sorted({fmt_group(r) for r in residuals}))
            if " OR " in inner:
                inner = f"({inner})"
            return f"{outer} AND {inner}"

        # 4) 常规输出（无提因子）
        group_exprs = [fmt_group(g) for g in minimal_groups]
        group_exprs = sorted(set(group_exprs))
        return " OR ".join(group_exprs)

    def add_condition(self, conditon: Optional[str]) -> "DualLicense":
        """
        Add a condition to the licenses.

        Usage:
            ```python
            dual_license = DualLicense.from_list([
                [DualUnit("MIT"), DualUnit("GPL-3.0")],
                [DualUnit("MIT"), DualUnit("GPL-3.0", condition="WITH", exceptions=["GPL-3.0-exception"])]
            ])
            dual_license.add_condition("dynamic_linking")
            ```
        """
        if not conditon:
            return self

        new = DualLicense()
        for group in self:
            new_group = set()
            for unit in group:
                new_group.add(DualUnit(unit["spdx_id"], conditon, unit["exceptions"]))
                if unit["condition"] and unit["condition"] != conditon:
                    new_group.add(unit)
            new.add(frozenset(new_group))
        return new

    def has_license(self, spdx_id: str) -> bool:
        """
        Check if the DualLicense contains a license.

        Usage:
            ```python
            dual_license = DualLicense.from_list([
                [DualUnit("MIT"), DualUnit("GPL-3.0")],
                [DualUnit("MIT"), DualUnit("GPL-3.0", condition="WITH", exceptions=["GPL-3.0-exception"])]
            ])
            print(dual_license.has_license("MIT"))
            # Output: True
            ```

        Args:
            spdx_id: str, SPDX ID of the license

        Returns:
            bool: True if the license is in the DualLicense, otherwise False
        """
        return any(spdx_id in [unit.unit_spdx for unit in group] for group in self)

    def apply_exception_to_targets(self, exception_spdx_id: str, target_spdx_ids: list[str]) -> "DualLicense":
        """
        Apply exception license to specific target licenses within this DualLicense.

        This method adds the exception to all DualUnit instances that match the target SPDX IDs.

        Args:
            exception_spdx_id: SPDX ID of the exception license
            target_spdx_ids: List of target license SPDX IDs that this exception should apply to

        Returns:
            DualLicense: New DualLicense instance with exceptions applied

        Raises:
            ValueError: If target_spdx_ids contains invalid SPDX IDs
        """
        from liscopelens.checker import Checker

        # Validate target SPDX IDs
        checker = Checker()
        for target_id in target_spdx_ids:
            if not checker.is_license_exist(target_id):
                raise ValueError(f"Invalid target SPDX ID: {target_id}")

        # For exceptions, we check if they exist in the exceptions list instead
        try:
            exceptions = load_exceptions()
            if exception_spdx_id not in exceptions:
                # Also check if it's a regular license
                if not checker.is_license_exist(exception_spdx_id):
                    raise ValueError(f"Invalid exception SPDX ID: {exception_spdx_id}")
        except OSError as exc:
            # Fallback to basic license check if loading exceptions fails
            if not checker.is_license_exist(exception_spdx_id):
                raise ValueError(f"Invalid exception SPDX ID: {exception_spdx_id}") from exc

        new_dual_license = DualLicense()

        for group in self:
            new_group = set()
            for unit in group:
                # Check if this unit's SPDX ID matches any target
                if unit["spdx_id"] in target_spdx_ids:
                    # Create new unit with the exception added
                    current_exceptions = unit.get("exceptions", [])
                    if exception_spdx_id not in current_exceptions:
                        new_exceptions = current_exceptions + [exception_spdx_id]
                        new_unit = DualUnit(unit["spdx_id"], unit.get("condition"), new_exceptions)
                        new_group.add(new_unit)
                    else:
                        # Exception already exists, keep original
                        new_group.add(unit)
                else:
                    # No match, keep original unit
                    new_group.add(unit)

            new_dual_license.add(frozenset(new_group))

        return new_dual_license

    @staticmethod
    def merge_group(set1: set[DualUnit], set2: set[DualUnit]) -> set[DualUnit]:
        """
        Merge two sets of DualUnit instances, combining the 'filename' property of duplicates.

        :param set1: The first set of DualUnit instances.
        :param set2: The second set of DualUnit instances.
        :return: A new set with merged DualUnit instances.
        """
        # 使用字典来暂时存储合并的结果，键为 DualUnit 的哈希值
        merged = {}
        for du in set1.union(set2):
            hash_val = hash(du)
            if hash_val in merged:
                merged[hash_val]["filename"] = merged[hash_val]["filename"].union(du["filename"])
            else:
                merged[hash_val] = du

        return set(merged.values())

    def iter_spdx_ids(self):
        """Iterate over all SPDX IDs in the license, including exceptions."""
        for group in self:
            for unit in group:
                yield unit.unit_spdx


class SPDXParser:
    """
    SPDX expression parser.

    Usage:
        ```
        parser = SPDXParser()
        parser("MIT AND GPL-3.0")
        # return DualUnit tuple

        parser("MIT AND (GPL-3.0 OR Apache-2.0)", expand=True)
        # return DualLicense
        ```
    """

    expression: str
    filepath: Optional[str]
    tokens: list[str]
    current: int

    def __call__(self, expression, filepath: Optional[str] = None, proprocessor: Optional[Callable] = None):
        if not expression:
            return DualLicense([frozenset()])
        self.expression = expression
        self.filepath = filepath
        self.tokens = []
        self.current = 0
        self.expression = self.parse(proprocessor)  # type: ignore
        return self.expand_expression(self.expression)

    def tokenize(self):
        """Tokenize the expression"""
        token_pattern = re.compile(r"\s*(WITH|AND|OR|\(|\)|[a-zA-Z0-9\.-]+)\s*")
        self.tokens = token_pattern.findall(self.expression)

    def parse(self, proprocessor: Optional[Callable] = None):
        """Parse the expression"""
        self.tokenize()
        result = self.parse_expression(proprocessor)
        if self.current < len(self.tokens):
            raise SyntaxError(f"Unexpected token at the end of expression {self.tokens}")
        return result

    def parse_expression(self, proprocessor: Optional[Callable] = None):
        """Parse the expression"""
        terms = (self.parse_term(proprocessor),)
        while self.current < len(self.tokens) and self.tokens[self.current] in ("AND", "OR", "WITH"):
            op = self.tokens[self.current]
            if op == "WITH":
                self.current += 1
                if self.current >= len(self.tokens):
                    raise SyntaxError("Unexpected end of expression")

                if isinstance(terms[-1], tuple):
                    raise SyntaxError("WITH operator must be followed by single spdx not compound expression")

                terms[-1]["exceptions"] = [*terms[-1]["exceptions"], self.tokens[self.current]]  # type: ignore
                self.current += 1
                continue
            self.current += 1
            terms = terms + (op, self.parse_term(proprocessor))
        if len(terms) == 1:
            return terms
        return terms

    def parse_term(self, proprocessor: Optional[Callable] = None):
        """Parse the term"""
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

        if token == ")":
            raise SyntaxError("Unexpected closing parenthesis")

        self.current += 1
        return DualUnit(proprocessor(token)) if proprocessor else DualUnit(token)

    def expand_expression(self, expression) -> DualLicense:
        """Expand the expression"""
        idx = 0
        previous_op = "AND"
        results = DualLicense([frozenset()])
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
                current_results = DualLicense((frozenset([expression[idx]]),))
                idx += 1
            else:
                raise SyntaxError(f"Unexpected token {expression[idx]}")

            if previous_op == "AND":
                results &= current_results
            elif previous_op == "OR":
                results |= current_results
            else:
                raise SyntaxError(f"Unexpected token {expression[idx]}")

        return results


def load_licenses(path: Optional[str] = None, only_reviewed: bool = False) -> dict[str, LicenseFeat]:
    """
    Load licenses from a directory of toml files

    Args:
        path: path to directory of toml files
        only_reviewed: if True, only load licenses that need human review

    Returns:
        dict[str, LicenseFeat]: dictionary of licenses
    """

    if path is None:
        path = str(get_resource_path().joinpath("licenses"))

    paths = filter(lambda x: not x.startswith("schemas") and x.endswith(".toml"), os.listdir(path))

    ret = {lic.spdx_id: lic for p in paths if (lic := LicenseFeat.from_toml(os.path.join(path, p)))}
    if only_reviewed:
        ret = {k: v for k, v in ret.items() if v.human_review}
    return ret


def load_exceptions(path: Optional[str] = None) -> dict[str, LicenseFeat]:
    """
    Load exceptions from a directory of toml files

    Args:
        path: path to directory of toml files

    Returns:
        dict[str, LicenseFeat]: dictionary of exceptions
    """
    if path is None:
        path = str(get_resource_path().joinpath("exceptions"))

    paths = filter(lambda x: not x.startswith("schemas") and x.endswith(".toml"), os.listdir(path))

    return {lic.spdx_id: lic for p in paths if (lic := LicenseFeat.from_toml(os.path.join(path, p)))}


def load_schemas(path: Optional[str] = None) -> Schemas:
    """
    Load schema from a toml file

    Args:
        path: path to toml file

    Returns:
        Schemas: schema object
    """

    if path is None:
        path = str(get_resource_path().joinpath("schemas.toml"))

    return Schemas.from_toml(path)


def load_config(path: Optional[str] = None) -> Config:
    """
    Load Config from a toml file

    Args:
        path: path to toml file

    Returns:
        Config: Config object
    """

    if path is None:
        path = str(get_resource_path(file_name="default.toml", resource_name="config"))
    else:
        # 检查是否带有.toml后缀
        if path.endswith(".toml"):
            # 如果带有.toml后缀，按照标准路径查找
            pass  # 保持原路径不变
        else:
            # 如果不带.toml后缀，去config/目录下查找默认配置（拼接.toml）
            path = str(get_resource_path(file_name=f"{path}.toml", resource_name="config"))

    return Config.from_toml(path)


class DualLicenseEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, DualLicense):
            return [[dict(unit) for unit in group] for group in o]
        if isinstance(o, DualUnit):
            return dict(o)
        if isinstance(o, set):
            return list(o)
        if isinstance(o, frozenset):
            return list(o)
        if isinstance(o, Scope):
            return dict(o)
        return super().default(o)


if __name__ == "__main__":
    print(
        SPDXParser()(
            "MIT AND (MIT AND (GPL-3.0 OR Apache-2.0)) AND (Apache-2.0 WITH c OR GPL WITH a) "
        ).to_spdx_expression()
    )
