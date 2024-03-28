import re
import json
import itertools
from dataclasses import dataclass, field, fields, asdict

from typing import Any
import importlib.resources as pkg_resources
from ..utils.scaffold import load_resource

@dataclass
class License:
    """
    ! will deprecated in the future
    """

    id: int = field(metadata={"json_key": "id"})
    name: str = field(metadata={"json_key": "name"})
    spdx_name: str = field(metadata={"json_key": "spdxName"})
    full_text: str = field(metadata={"json_key": "fullText"})
    main_tags: list[dict] = field(metadata={"json_key": "licenseMainTags"})
    cannot_tags: list[dict] = field(metadata={"json_key": "cannotFeatureTags"})
    can_tags: list[dict] = field(metadata={"json_key": "canFeatureTags"})
    must_tags: list[dict] = field(metadata={"json_key": "mustFeatureTags"})
    virality: dict[Any] = field(metadata={"json_key": "virality"})

    def __repr__(self):
        return f"{self.spdx_name or self.name}"

    def __hash__(self) -> int:
        return hash(self.spdx_name + self.name)

    def __eq__(self, other):
        if isinstance(other, License):
            return self.id == other.id
        elif isinstance(other, str):
            return self.spdx_name == other or self.name == other
        return False

    @property
    def is_taged(self):
        if not (self.must_tags and self.can_tags and self.cannot_tags and self.main_tags):
            return False

        for tag in self.cannot_tags + self.must_tags + self.cannot_tags:
            if tag["name"] == "None Yet.":
                return False
        return True

    @classmethod
    def from_dict(cls, data_dict):
        def _load(data_key):
            if data_key in [
                "cannotFeatureTags",
                "canFeatureTags",
                "mustFeatureTags",
            ]:
                return list(filter(lambda x: x["name"] != "None Yet.", data_dict.get(data_key)))
            else:
                return data_dict.get(data_key)

        args = {field.name: _load(field.metadata.get("json_key")) for field in fields(cls)}
        return cls(**args)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Licenses:
    """
    ! will deprecated in the future
    """

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.data[key]
        if not self.__data_ids:
            self.__data_ids = [tl.spdx_name for tl in self.data]
        idx = self.__data_ids.index(key)
        return None if idx == -1 else self.data[idx]

    def __init__(self, data_path: str = "licenses_feature.json", filter_list: list = None) -> None:
        self.index = 0
        self._meta_data = load_resource("licenses_feature.json")

        self.__nodes: dict = None
        self.all_tags: list = None
        self.data: list[License] = []
        self.__data_ids: list[str] = []
        self.vec_data: dict[list] = {}
        self.compatible_data: list[tuple] = []

        self.tag_set = set()
        self.can_tags = set()
        self.cannot_tags = set()
        self.must_tags = set()

        for lic in json.loads(self._meta_data):
            license = License.from_dict(lic)

            if filter_list and license.spdx_name not in filter_list:
                continue

            self.data.append(license)
            self.can_tags.update([tag["name"] for tag in license.can_tags])
            self.cannot_tags.update([tag["name"] for tag in license.cannot_tags])
            self.must_tags.update([tag["name"] for tag in license.must_tags])

        self.tag_set = self.can_tags | self.cannot_tags | self.must_tags
        self.all_tags = sorted(self.tag_set)
        self.can_tags = sorted(self.can_tags)
        self.cannot_tags = sorted(self.cannot_tags)
        self.must_tags = sorted(self.must_tags)

    def __iter__(self):
        return iter(self.data)

    def get_combinations(self):
        return list(itertools.combinations(self.data, 2))

    def get_permutations(self):
        return list(itertools.permutations(self.data, 2))

    def get_product(self):
        return list(itertools.product(self.data, self.data))

    def __len__(self):
        return len(self.data)

    def tag2vec(self, license: License):
        return [1 if tag in license.tags else 0 for tag in self.all_tags]

    @property
    def nodes(self):
        if not self.__nodes:
            tmp = {d.spdx_name: d for d in self.data}.values()
            self.__nodes = sorted(tmp, key=lambda x: x.spdx_name)
        return self.__nodes

    @property
    def licenses_vec(self):
        if not self.vec_data:
            for license in self.data:
                self.vec_data[license.spdx_name] = self.tag2vec(license)
        return self.vec_data

    def preprocess(self, full_text):
        text = re.sub(r"<p>(.*?)</p>", r"<s>\1</s>", full_text)
        return re.sub(r"<(?!\/?s\b)[^>]+>", "", text).lstrip()

    def to_json(self, file_path: str):
        with open(file_path, "w", encoding="utf8") as f:
            json.dump([license.to_dict() for license in self.data], f)

    @classmethod
    def from_json(cls, file_path: str, filter_list: list[str] = None):
        licenses = cls(file_path, filter_list=filter_list)
        return licenses
