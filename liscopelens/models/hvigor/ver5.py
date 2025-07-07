# -*- coding: utf-8 -*-

"""
This module provides Pydantic models for parsing HarmonyOS configuration files
such as module.json5 and build-profile.json5, based on the specifications
found in the profile.md documentation.
"""

from typing import Any, Dict, List, Optional, Union, Literal

from pydantic import BaseModel, Field


class AppEnvironment(BaseModel):
    """
    Model for appEnvironments items.
    """

    name: Optional[str] = None
    value: Optional[str] = None


class Metadata(BaseModel):
    """
    Model for metadata items.
    """

    name: Optional[str] = None
    value: Optional[str] = None
    resource: Optional[str] = None


# Models for app.json5


class DeviceSpec(BaseModel):
    """
    Model for device-specific configurations (tablet, tv, etc.).
    """

    minAPIVersion: Optional[int] = None


class MultiAppMode(BaseModel):
    """
    Model for the multiAppMode object.
    """

    multiAppModeType: Literal["multiInstance", "appClone"]
    maxCount: int


class AppInfo(BaseModel):
    """
    Model for the "app" object in app.json5.
    """

    bundleName: str
    bundleType: Optional[Literal["app", "atomicService", "shared", "appService"]] = "app"
    debug: Optional[bool] = False
    icon: str
    label: str
    description: Optional[str] = None
    vendor: Optional[str] = None
    versionCode: int
    versionName: str
    minCompatibleVersionCode: Optional[int] = None
    minAPIVersion: Optional[int] = None
    targetAPIVersion: Optional[int] = None
    apiReleaseType: Optional[str] = None
    accessible: Optional[bool] = False
    multiProjects: Optional[bool] = False
    asanEnabled: Optional[bool] = False
    tablet: Optional[DeviceSpec] = None
    tv: Optional[DeviceSpec] = None
    wearable: Optional[DeviceSpec] = None
    car: Optional[DeviceSpec] = None
    default: Optional[DeviceSpec] = None
    targetBundleName: Optional[str] = None
    targetPriority: Optional[int] = 1
    generateBuildHash: Optional[bool] = False
    GWPAsanEnabled: Optional[bool] = False
    appEnvironments: Optional[List[AppEnvironment]] = None
    maxChildProcess: Optional[int] = None
    multiAppMode: Optional[MultiAppMode] = None
    cloudFileSyncEnabled: Optional[bool] = False
    configuration: Optional[str] = None


class AppProfile(BaseModel):
    """
    Top-level model for app.json5.
    """

    app: AppInfo


# Models for module.json5


class SkillUri(BaseModel):
    """
    Model for skill uris items.
    """

    scheme: Optional[str] = None
    host: Optional[str] = None
    port: Optional[str] = None
    path: Optional[str] = None
    pathStartWith: Optional[str] = None
    pathRegex: Optional[str] = None
    type: Optional[str] = None
    utd: Optional[str] = None
    maxFileSupported: Optional[int] = 0
    linkFeature: Optional[str] = None


class Skill(BaseModel):
    """
    Model for skills items.
    """

    actions: Optional[List[str]] = None
    entities: Optional[List[str]] = None
    uris: Optional[List[SkillUri]] = None
    permissions: Optional[List[str]] = None
    domainVerify: Optional[bool] = False


class Ability(BaseModel):
    """
    Model for abilities items.
    """

    name: str
    srcEntry: str
    launchType: Optional[Literal["multiton", "singleton", "specified", "standard"]] = "singleton"
    description: Optional[str] = None
    icon: Optional[str] = None
    label: Optional[str] = None
    permissions: Optional[List[str]] = None
    metadata: Optional[List[Metadata]] = None
    exported: Optional[bool] = False
    continuable: Optional[bool] = False
    skills: Optional[List[Skill]] = None
    backgroundModes: Optional[List[str]] = None
    startWindowIcon: str
    startWindowBackground: str
    removeMissionAfterTerminate: Optional[bool] = False
    orientation: Optional[
        Literal[
            "unspecified",
            "landscape",
            "portrait",
            "follow_recent",
            "landscape_inverted",
            "portrait_inverted",
            "auto_rotation",
            "auto_rotation_landscape",
            "auto_rotation_portrait",
            "auto_rotation_restricted",
            "auto_rotation_landscape_restricted",
            "auto_rotation_portrait_restricted",
            "locked",
            "auto_rotation_unspecified",
            "follow_desktop",
        ]
    ] = "unspecified"
    supportWindowMode: Optional[List[Literal["fullscreen", "split", "floating"]]] = Field(
        default_factory=lambda: ["fullscreen", "split", "floating"]
    )
    maxWindowRatio: Optional[float] = None
    minWindowRatio: Optional[float] = None
    maxWindowWidth: Optional[int] = None
    minWindowWidth: Optional[int] = None
    maxWindowHeight: Optional[int] = None
    minWindowHeight: Optional[int] = None
    recoverable: Optional[bool] = False
    isolationProcess: Optional[bool] = False
    excludeFromDock: Optional[bool] = False
    preferMultiWindowOrientation: Optional[Literal["default", "portrait", "landscape", "landscape_auto"]] = "default"
    continueType: Optional[List[str]] = None


class ExtensionAbility(BaseModel):
    """
    Model for extensionAbilities items.
    """

    name: str
    srcEntry: str
    description: Optional[str] = None
    icon: Optional[str] = None
    label: Optional[str] = None
    type: str
    permissions: Optional[List[str]] = None
    readPermission: Optional[str] = None
    writePermission: Optional[str] = None
    uri: Optional[str] = None
    skills: Optional[List[Skill]] = None
    metadata: Optional[List[Metadata]] = None
    exported: Optional[bool] = False
    extensionProcessMode: Optional[Literal["instance", "type", "bundle"]] = None
    dataGroupIds: Optional[List[str]] = None


class DefinePermission(BaseModel):
    """
    Model for definePermissions items.
    """

    name: str
    grantMode: Optional[Literal["system_grant", "user_grant"]] = "system_grant"
    availableLevel: Optional[Literal["system_core", "system_basic", "normal"]] = "normal"
    provisionEnable: Optional[bool] = True
    distributedSceneEnable: Optional[bool] = False
    label: Optional[str] = None
    description: Optional[str] = None


class RequestPermissionUsedScene(BaseModel):
    """
    Model for requestPermissions usedScene.
    """

    abilities: Optional[List[str]] = None
    when: Literal["inuse", "always"]


class RequestPermission(BaseModel):
    """
    Model for requestPermissions items.
    """

    name: str
    reason: Optional[str] = None
    usedScene: Optional[RequestPermissionUsedScene] = None


class TestRunner(BaseModel):
    """
    Model for testRunner.
    """

    name: str
    srcPath: str


class AtomicServicePreload(BaseModel):
    """
    Model for atomicService preloads.
    """

    moduleName: str


class AtomicService(BaseModel):
    """
    Model for atomicService.
    """

    preloads: Optional[List[AtomicServicePreload]] = None


class Dependency(BaseModel):
    """
    Model for dependencies items.
    """

    bundleName: Optional[str] = None
    moduleName: str
    versionCode: Optional[int] = None


class HnpPackage(BaseModel):
    """
    Model for hnpPackages items.
    """

    package: str
    type: Literal["public", "private"]


class ModuleConfig(BaseModel):
    """
    Model for the "module" object in module.json5.
    """

    name: str
    type: Literal["entry", "feature", "har", "shared"]
    srcEntry: Optional[str] = None
    description: Optional[str] = None
    mainElement: Optional[str] = None
    deviceTypes: List[str]
    deliveryWithInstall: Optional[bool] = None
    installationFree: Optional[bool] = None
    virtualMachine: Optional[str] = None
    pages: Optional[str] = None
    metadata: Optional[List[Metadata]] = None
    abilities: Optional[List[Ability]] = None
    extensionAbilities: Optional[List[ExtensionAbility]] = None
    definePermissions: Optional[List[DefinePermission]] = None
    requestPermissions: Optional[List[RequestPermission]] = None
    testRunner: Optional[TestRunner] = None
    atomicService: Optional[AtomicService] = None
    dependencies: Optional[List[Dependency]] = None
    proxyData: Optional[List[Dict[str, Any]]] = None
    generateBuildHash: Optional[bool] = False
    compressNativeLibs: Optional[bool] = False
    libIsolation: Optional[bool] = False
    fileContextMenu: Optional[str] = None
    querySchemes: Optional[List[str]] = None
    routerMap: Optional[str] = None
    appEnvironments: Optional[List[AppEnvironment]] = None
    appStartup: Optional[str] = None
    hnpPackages: Optional[List[HnpPackage]] = None


class ModuleProfile(BaseModel):
    """
    Top-level model for module.json5.
    """

    module: ModuleConfig
    targetModuleName: Optional[str] = None
    targetPriority: Optional[int] = 1
    isolationMode: Optional[Literal["nonisolationFirst", "isolationFirst", "isolationOnly", "nonisolationOnly"]] = (
        "nonisolationFirst"
    )


# Models for build-profile.json5 (Project Level)


class SigningMaterial(BaseModel):
    """
    Model for signingConfigs material.
    """

    storePassword: str
    certpath: str
    keyAlias: str
    keyPassword: str
    profile: str
    signAlg: str
    storeFile: str


class SigningConfig(BaseModel):
    """
    Model for signingConfigs items.
    """

    name: str
    material: SigningMaterial
    type: Optional[Literal["HarmonyOS", "OpenHarmony"]] = None


class ResCompressionFilterFile(BaseModel):
    path: Optional[List[str]] = None
    size: Optional[List[List[Union[int, str]]]] = None
    resolution: Optional[List[List[Dict[str, int]]]] = None


class ResCompressionFilter(BaseModel):
    method: Dict[str, str]
    files: Optional[ResCompressionFilterFile] = None
    exclude: Optional[ResCompressionFilterFile] = None


class ResCompression(BaseModel):
    media: Optional[Dict[str, bool]] = None
    filters: Optional[List[ResCompressionFilter]] = None


class ResOptions(BaseModel):
    compression: Optional[ResCompression] = None


class ExternalNativeOptions(BaseModel):
    path: Optional[str] = None
    abiFilters: Optional[List[Literal["arm64-v8a", "x86_64", "armeabi-v7a"]]] = None
    arguments: Optional[Union[str, List[str]]] = None
    cppFlags: Optional[str] = None


class SourceOption(BaseModel):
    workers: Optional[List[str]] = None


class NativeLibSelect(BaseModel):
    package: Optional[str] = None
    version: Optional[str] = None
    include: Optional[List[str]] = None
    exclude: Optional[List[str]] = None


class NativeLibFilter(BaseModel):
    excludes: Optional[List[str]] = None
    pickFirsts: Optional[List[str]] = None
    pickLasts: Optional[List[str]] = None
    enableOverride: Optional[bool] = False
    select: Optional[List[NativeLibSelect]] = None


class DebugSymbol(BaseModel):
    strip: Optional[bool] = True
    exclude: Optional[List[str]] = None


class NativeLib(BaseModel):
    filter: Optional[NativeLibFilter] = None
    debugSymbol: Optional[DebugSymbol] = None
    headerPath: Optional[Union[str, List[str]]] = None
    collectAllLibs: Optional[bool] = False
    excludeFromHar: Optional[bool] = True


class NapiLibFilterOption(BaseModel):
    excludes: Optional[List[str]] = None
    pickFirsts: Optional[List[str]] = None
    pickLasts: Optional[List[str]] = None
    enableOverride: Optional[bool] = False


class TscConfig(BaseModel):
    targetESVersion: Optional[Literal["ES2017", "ES2021"]] = "ES2021"


class ArkOptions(BaseModel):
    apPath: Optional[str] = None
    buildProfileFields: Optional[Dict[str, Union[str, int, bool]]] = None
    hostPGO: Optional[bool] = False
    types: Optional[List[str]] = None
    tscConfig: Optional[TscConfig] = None


class StrictMode(BaseModel):
    noExternalImportByPath: Optional[bool] = None
    useNormalizedOHMUrl: Optional[bool] = False
    caseSensitiveCheck: Optional[bool] = False
    duplicateDependencyCheck: Optional[bool] = False
    harLocalDependencyCheck: Optional[bool] = False


class BuildOption(BaseModel):
    packOptions: Optional[Dict[str, bool]] = None
    debuggable: Optional[bool] = True
    resOptions: Optional[ResOptions] = None
    externalNativeOptions: Optional[ExternalNativeOptions] = None
    sourceOption: Optional[SourceOption] = None
    nativeLib: Optional[NativeLib] = None
    napiLibFilterOption: Optional[NapiLibFilterOption] = None
    arkOptions: Optional[ArkOptions] = None
    strictMode: Optional[StrictMode] = None
    nativeCompiler: Optional[Literal["Original", "BiSheng"]] = "Original"


class ProductResource(BaseModel):
    directories: List[str]


class ProductOutput(BaseModel):
    artifactName: str


class Product(BaseModel):
    name: str
    signingConfig: Optional[str] = None
    bundleName: Optional[str] = None
    buildOption: Optional[BuildOption] = None
    runtimeOS: Optional[Literal["HarmonyOS", "OpenHarmony"]] = None
    arkTSVersion: Optional[Literal["1.0", "1.1"]] = None
    compileSdkVersion: Optional[Union[str, int]] = None
    compatibleSdkVersion: Union[str, int]
    compatibleSdkVersionStage: Optional[str] = None
    targetSdkVersion: Optional[Union[str, int]] = None
    bundleType: Optional[Literal["app", "atomicService", "shared"]] = None
    label: Optional[str] = None
    icon: Optional[str] = None
    versionCode: Optional[int] = None
    versionName: Optional[str] = None
    resource: Optional[ProductResource] = None
    output: Optional[ProductOutput] = None
    vendor: Optional[str] = None


class BuildMode(BaseModel):
    name: str
    buildOption: Optional[BuildOption] = None


class ModuleTarget(BaseModel):
    name: str
    applyToProducts: Optional[List[str]] = None


class ProjectModule(BaseModel):
    name: str
    srcPath: str
    targets: Optional[List[ModuleTarget]] = None


class AppConfig(BaseModel):
    signingConfigs: Optional[List[SigningConfig]] = None
    products: Optional[List[Product]] = None
    buildModeSet: Optional[List[BuildMode]] = None
    multiProjects: Optional[bool] = False


class ProjectProfile(BaseModel):
    app: AppConfig
    modules: List[ProjectModule]


# Models for build-profile.json5 (Module Level)


class DistroFilterPolicy(BaseModel):
    policy: Literal["include", "exclude"]
    value: List[Union[str, int]]


class DistroFilter(BaseModel):
    apiVersion: Optional[DistroFilterPolicy] = None
    screenShape: Optional[DistroFilterPolicy] = None
    screenWindow: Optional[DistroFilterPolicy] = None
    screenDensity: Optional[DistroFilterPolicy] = None
    countryCode: Optional[DistroFilterPolicy] = None


class TargetConfig(BaseModel):
    distroFilter: Optional[DistroFilter] = None
    distributionFilter: Optional[DistroFilter] = None
    deviceType: Optional[List[str]] = None
    buildOption: Optional[BuildOption] = None  # Reusing project-level buildOption
    atomicService: Optional[Dict[str, Any]] = None  # Simplified for now


class TargetSourceAbility(BaseModel):
    name: str
    pages: Optional[List[str]] = None


class TargetSource(BaseModel):
    abilities: Optional[List[TargetSourceAbility]] = None
    pages: Optional[List[str]] = None
    sourceRoots: Optional[List[str]] = None


class TargetResource(BaseModel):
    directories: Optional[List[str]] = None


class TargetOutput(BaseModel):
    artifactName: str


class ModuleTargetConfig(BaseModel):
    name: str
    runtimeOS: Optional[Literal["HarmonyOS", "OpenHarmony"]] = None
    config: Optional[TargetConfig] = None
    source: Optional[TargetSource] = None
    resource: Optional[TargetResource] = None
    output: Optional[TargetOutput] = None


class ModuleBuildOption(BuildOption):  # Extends project-level buildOption
    name: Optional[str] = None
    copyFrom: Optional[str] = None


class BuildModeMapping(BaseModel):
    targetName: Optional[str] = None
    buildOptionName: Optional[str] = None


class BuildModeBinder(BaseModel):
    buildModeName: Optional[str] = None
    mappings: Optional[List[BuildModeMapping]] = None


class ModuleBuildProfile(BaseModel):
    apiType: Optional[Literal["stageMode", "faMode"]] = None
    targets: Optional[List[ModuleTargetConfig]] = None
    showInServiceCenter: Optional[bool] = False
    buildOption: Optional[ModuleBuildOption] = None
    buildOptionSet: Optional[List[ModuleBuildOption]] = None
    buildModeBinder: Optional[List[BuildModeBinder]] = None
    entryModules: Optional[List[str]] = None


# Models for oh-package.json5 (Project Level)


class OhPackageProjectProfile(BaseModel):
    modelVersion: Optional[str] = None
    description: Optional[str] = None
    dependencies: Optional[Dict[str, str]] = None
    devDependencies: Optional[Dict[str, str]] = None
    dynamicDependencies: Optional[Dict[str, str]] = None
    overrides: Optional[Dict[str, str]] = None
    overrideDependencyMap: Optional[Dict[str, str]] = None
    scripts: Optional[Dict[str, str]] = None
    hooks: Optional[Dict[str, str]] = None
    parameterFile: Optional[str] = None


# Models for oh-package.json5 (Module Level)


class Author(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None


class NativeComponent(BaseModel):
    name: str
    compatibleSdkVersion: Optional[str] = None
    compatibleSdkType: Optional[str] = None


class OhPackageModuleProfile(BaseModel):
    name: str
    version: str
    description: Optional[str] = None
    keywords: Optional[List[str]] = None
    author: Optional[Union[str, Author]] = None
    homepage: Optional[str] = None
    repository: Optional[Union[str, Dict[str, Any]]] = None
    license: Optional[str] = None
    dependencies: Optional[Dict[str, str]] = None
    devDependencies: Optional[Dict[str, str]] = None
    dynamicDependencies: Optional[Dict[str, str]] = None
    main: Optional[str] = None
    types: Optional[str] = None
    compatibleSdkVersion: Optional[str] = None
    compatibleSdkType: Optional[str] = None
    obfuscated: Optional[bool] = None
    nativeComponents: Optional[List[NativeComponent]] = None
    artifactType: Optional[str] = "original"
    scripts: Optional[Dict[str, str]] = None
    hooks: Optional[Dict[str, str]] = None
    category: Optional[str] = None
    packageType: Optional[str] = "InterfaceHar"


# Models for hvigor-config.json5


class Execution(BaseModel):
    """
    Model for the "execution" object in hvigor-config.json5.
    """

    analyze: Optional[Union[Literal["normal", "advanced"], bool]] = "normal"
    daemon: Optional[bool] = True
    incremental: Optional[bool] = True
    parallel: Optional[bool] = True
    typeCheck: Optional[bool] = False


class Logging(BaseModel):
    """
    Model for the "logging" object in hvigor-config.json5.
    """

    level: Optional[Literal["debug", "info", "warn", "error"]] = "info"


class Debugging(BaseModel):
    """
    Model for the "debugging" object in hvigor-config.json5.
    """

    stacktrace: Optional[bool] = False


class NodeOptions(BaseModel):
    """
    Model for the "nodeOptions" object in hvigor-config.json5.
    """

    maxOldSpaceSize: Optional[int] = None
    exposeGC: Optional[bool] = True


class Properties(BaseModel):
    """
    Model for the "properties" object in hvigor-config.json5.
    """

    hvigor_cacheDir: Optional[str] = Field(None, alias="hvigor.cacheDir")
    ohos_buildDir: Optional[str] = Field(None, alias="ohos.buildDir")
    enableSignTask: Optional[bool] = True
    ohos_arkCompile_maxSize: Optional[int] = Field(5, alias="ohos.arkCompile.maxSize")
    hvigor_pool_maxSize: Optional[int] = Field(None, alias="hvigor.pool.maxSize")
    ohos_pack_compressLevel: Optional[Literal["fast", "standard", "ultimate"]] = Field(
        "fast", alias="ohos.pack.compressLevel"
    )
    hvigor_analyzeHtml: Optional[bool] = Field(False, alias="hvigor.analyzeHtml")
    hvigor_dependency_useNpm: Optional[bool] = Field(False, alias="hvigor.dependency.useNpm")
    ohos_compile_lib_entryfile: Optional[bool] = Field(False, alias="ohos.compile.lib.entryfile")
    ohos_align_target: Optional[str] = Field(None, alias="ohos.align.target")
    ohos_fallback_target: Optional[List[str]] = Field(None, alias="ohos.fallback.target")
    ohos_arkCompile_sourceMapDir: Optional[str] = Field(None, alias="ohos.arkCompile.sourceMapDir")
    hvigor_enableMemoryCache: Optional[bool] = Field(True, alias="hvigor.enableMemoryCache")
    hvigor_memoryThreshold: Optional[int] = Field(None, alias="hvigor.memoryThreshold")
    ohos_nativeResolver: Optional[bool] = Field(True, alias="ohos.nativeResolver")
    ohos_sign_har: Optional[bool] = Field(False, alias="ohos.sign.har")
    hvigor_keepDependency: Optional[bool] = Field(True, alias="hvigor.keepDependency")


class HvigorConfig(BaseModel):
    """
    Top-level model for hvigor-config.json5.
    """

    modelVersion: Optional[str] = None
    dependencies: Optional[Dict[str, Any]] = None
    execution: Optional[Execution] = None
    logging: Optional[Logging] = None
    debugging: Optional[Debugging] = None
    nodeOptions: Optional[NodeOptions] = None
    properties: Optional[Properties] = None
