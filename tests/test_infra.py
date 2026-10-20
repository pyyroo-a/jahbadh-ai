"""Plain text checks on the Azure templates. Nothing here talks to Azure."""

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INFRA = REPO / "infra"
ALLOWED = {"germanywestcentral", "austriaeast", "uaenorth", "polandcentral", "centralindia"}


def read(name: str) -> str:
    return (INFRA / name).read_text(encoding="utf-8")


def param_block(text: str, name: str) -> str:
    """The decorators and declaration of one param, from the end of the previous statement."""
    match = re.search(rf"((?:@[^\n]*\n|//[^\n]*\n)*)param {name}\b[^\n]*", text)
    assert match, f"param {name} is missing"
    return match.group(0)


def test_the_app_never_runs_two_copies():
    app = read("app.bicep")
    assert re.findall(r"maxReplicas:\s*(\S+)", app) == ["1"]
    assert re.findall(r"minReplicas:\s*(\S+)", app) == ["minReplicas"]
    for name in ("main.bicep", "app.bicep"):
        block = param_block(read(name), "minReplicas")
        assert "@minValue(0)" in block and "@maxValue(1)" in block and "= 0" in block


def test_the_environment_is_a_standard_one_that_can_mount_the_share():
    # left unset, Azure made an Express environment (20 Oct), and Express refuses Azure Files storage
    app = read("app.bicep")
    env = re.search(r"resource environment 'Microsoft\.App/managedEnvironments@([^']+)' = \{(.*?)\n\}", app, re.S)
    assert env and env.group(1) >= "2026-07-01"
    assert "environmentMode: 'WorkloadProfiles'" in env.group(2)
    assert "workloadProfileType: 'Consumption'" in env.group(2) and "Dedicated" not in env.group(2)


def test_only_allowed_regions_can_be_picked():
    block = param_block(read("main.bicep"), "location")
    listed = re.search(r"@allowed\(\[(.*?)\]\)", block, re.S)
    assert listed and set(re.findall(r"'([a-z]+)'", listed.group(1))) == ALLOWED
    assert "= 'uaenorth'" in block


def test_azd_down_can_only_remove_the_app_group():
    main = read("main.bicep")
    groups = re.findall(r"resource \w+ 'Microsoft\.Resources/resourceGroups@[^']+'( existing)? = \{\s*name: ([^\n]+)",
                        main)
    created = [name.strip() for existing, name in groups if not existing]
    assert created == ["'rg-jahbadh-app'"]
    # nothing is ever deployed into the Foundry group by azd: the roles go in with their own command
    modules = re.findall(r"module \w+ '([^']+)' = \{(.*?)\n\}", main, re.S)
    assert modules and all("scope: appGroup" in body for _, body in modules)
    assert "roles.bicep" not in [path for path, _ in modules]
    # the roles file only adds role assignments to the two accounts it references
    roles = read("roles.bicep")
    declared = re.findall(r"^resource \w+ '([^']+)'( existing)?", roles, re.M)
    assert {t.split("@")[0] for t, existing in declared if not existing} == {"Microsoft.Authorization/roleAssignments"}


def test_the_roles_are_the_two_least_privileged_ones():
    roles = read("roles.bicep")
    assert "5e0bd9bd-7b93-4f28-af87-19fc36ad61bd" in roles       # Cognitive Services OpenAI User
    assert "a97b65f3-24c7-4388-baec-2e87135dc908" in roles       # Cognitive Services User
    assert "7f951dda-4ed3-4680-a7ca-43fe172d538d" in read("app.bicep")   # AcrPull
    assert len(re.findall(r"resource \w+ 'Microsoft\.CognitiveServices/accounts@[^']+' existing", roles)) == 2


def test_no_key_is_written_into_the_templates():
    texts = {p.name: p.read_text(encoding="utf-8") for p in INFRA.glob("*")} | \
            {"azure.yaml": (REPO / "azure.yaml").read_text(encoding="utf-8")}
    for name, text in texts.items():
        for bad in ("api_key", "FOUNDRY_API_KEY=", "InstrumentationKey=", "AccountKey=", "IngestionEndpoint="):
            assert bad not in text, f"{bad} in {name}"
    main = read("main.bicep")
    for secret in ("ingestToken", "foundryKey", "translatorKey"):
        assert "@secure()" in param_block(main, secret)


def test_reprovisioning_keeps_the_deployed_image():
    values = json.loads(read("main.parameters.json"))["parameters"]
    assert values["apiExists"]["value"] == "${SERVICE_API_RESOURCE_EXISTS=false}"
    assert values["minReplicas"]["value"] == "${MIN_REPLICAS=0}"
    assert values["location"]["value"] == "${AZURE_LOCATION}"
    assert "fetch-image.bicep" in read("app.bicep")


def test_azd_finds_the_app_and_builds_it_in_the_cloud():
    azure = (REPO / "azure.yaml").read_text(encoding="utf-8")
    assert re.search(r"^name: jahbadh$", azure, re.M)
    assert "host: containerapp" in azure and "remoteBuild: true" in azure and "language: python" in azure
    assert "'azd-service-name': 'api'" in read("app.bicep")
