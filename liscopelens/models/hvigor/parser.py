import json
from typing import Union, Dict, Literal

from .ver5 import (
    AppProfile,
    ModuleProfile,
    ProjectProfile,
    ModuleBuildProfile,
    OhPackageProjectProfile,
    OhPackageModuleProfile,
    HvigorConfig,
    BaseModel,
)

V5_MODELS = {
    "app": AppProfile,
    "module": ModuleProfile,
    "build-profile-project": ProjectProfile,
    "build-profile-module": ModuleBuildProfile,
    "oh-package-project": OhPackageProjectProfile,
    "oh-package-module": OhPackageModuleProfile,
    "hvigor-config": HvigorConfig,
}


SUPPORTED_VERSIONS = {
    "5.0.0": V5_MODELS,
}


def parse_json_to_dataclass(
    json_content: Union[str, Dict],
    config_type: Literal[
        "app",
        "module",
        "build-profile-project",
        "build-profile-module",
        "oh-package-project",
        "oh-package-module",
        "hvigor-config",
    ],
    version: str = "5.0.0",
) -> BaseModel:
    """
    Parses a JSON string or dictionary into a Pydantic dataclass model.

    Args:
        json_content: The JSON content to parse, as a string or a dictionary.
        config_type: The type of configuration to parse.
        version: The version of the configuration format.

    Returns:
        An instance of the corresponding Pydantic model.

    Raises:
        ValueError: If the version or config_type is not supported.
        json.JSONDecodeError: If the json_content string is not valid JSON.
        pydantic.ValidationError: If the JSON content does not match the model schema.
    """
    if version not in SUPPORTED_VERSIONS:
        raise ValueError(f"Version '{version}' is not supported. Supported versions: {list(SUPPORTED_VERSIONS.keys())}")

    models = SUPPORTED_VERSIONS[version]

    if config_type not in models:
        raise ValueError(
            f"Config type '{config_type}' is not supported for version '{version}'. "
            f"Supported types: {list(models.keys())}"
        )

    model_class = models[config_type]

    if isinstance(json_content, str):
        data = json.loads(json_content)
    else:
        data = json_content

    return model_class.model_validate(data)
