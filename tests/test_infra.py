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


WORKFLOWS = REPO / ".github" / "workflows"
GITHUB_SUBJECT = "repo:pyyroo-a@195799002/jahbadh-ai@1423169832:ref:refs/heads/main"


def test_deploy_only_runs_when_asked():
    deploy = (WORKFLOWS / "deploy.yml").read_text(encoding="utf-8")
    triggers = re.search(r"^on:\n((?:  .*\n)+)", deploy, re.M)
    assert triggers and re.findall(r"^  (\w+):", triggers.group(1), re.M) == ["workflow_dispatch"]
    # it signs in with GitHub's token, never a stored password
    assert "id-token: write" in deploy and "secrets." not in deploy


def test_deploy_runs_the_tests_first():
    deploy = (WORKFLOWS / "deploy.yml").read_text(encoding="utf-8")
    assert re.search(r"^  test:\n    uses: \./\.github/workflows/ci\.yml$", deploy, re.M)
    assert re.search(r"^  deploy:\n    needs: test$", deploy, re.M)
    assert re.search(r"^  workflow_call:", (WORKFLOWS / "ci.yml").read_text(encoding="utf-8"), re.M)


def test_the_federated_credential_trusts_only_main():
    app = read("app.bicep")
    assert len(re.findall(r"'Microsoft\.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@", app)) == 1
    assert "issuer: 'https://token.actions.githubusercontent.com'" in app
    # repos made after 15 July 2026 sign in with owner and repo ids in the subject
    assert f"subject: '{GITHUB_SUBJECT}'" in app
    assert "audiences: ['api://AzureADTokenExchange']" in app
    assert "AZURE_DEPLOY_CLIENT_ID" in read("main.bicep")


def test_the_deploy_identity_can_only_change_the_app_group():
    app = read("app.bicep")
    assert "b24988ac-6180-42a0-ab88-20f7382dd24c" in app      # Contributor, on this resource group only
    assert "8311e382-0749-4cb8-b61a-304f252e45ec" in app      # AcrPush
    for owner_like in ("8e3af657-a8ff-443c-a75c-2fe8c4bcb635", "18d7d88d-d35e-4fb5-a5c3-7773c20a72d9"):
        assert owner_like not in app                          # Owner, User Access Administrator
    contributor = re.search(r"resource deployContributor '[^']+' = \{(.*?)\n\}", app, re.S)
    assert contributor and "scope:" not in contributor.group(1)   # no scope means the app group itself


def test_azd_finds_the_app_and_builds_it_in_the_cloud():
    azure = (REPO / "azure.yaml").read_text(encoding="utf-8")
    assert re.search(r"^name: jahbadh$", azure, re.M)
    assert "host: containerapp" in azure and "remoteBuild: true" in azure and "language: python" in azure
    assert "'azd-service-name': 'api'" in read("app.bicep")
