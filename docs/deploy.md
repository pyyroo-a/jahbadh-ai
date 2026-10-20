# Deploying Jahbadh to Azure

This guide puts the desk on Azure Container Apps, signed in without keys and traced into Foundry. You run every step yourself, in order. Each one says what it costs, what you should see and how to check it worked.

**What gets made.** Everything new goes in its own resource group, `rg-jahbadh-app`, in UAE North:

- a Container Apps environment (Consumption profile only, so there's no plan fee) and the container app `ca-jahbadh` (0.5 vCPU, 1 GiB, never more than one copy)
- a Container Registry (Basic) for the image
- a storage account with a small file share, `state`, which keeps the daily live counter through restarts
- Log Analytics for the app's container logs (capped at 0.15 GB a day, so the month stays inside the free 5 GB); the agents' traces go to Foundry's own Application Insights, which already exists (step 10)
- a managed identity, `id-jahbadh-app`, which the app uses to sign in to the registry, Foundry and Translator
- a second identity, `id-jahbadh-deploy`, which GitHub's Deploy workflow signs in as to ship new versions (it can only change `rg-jahbadh-app`)

**What stays put.** Foundry, the `gpt-5-mini` deployment and Translator stay in `rg-jahbadh-ai`. The templates only read them. The templates also read the connection string of Foundry's own Application Insights there, so traces show up in Foundry. The one thing that adds anything to that group is step 8, which gives the app's identity two roles there, and you run it with its own command (step 10 also has an optional daily cap you can set there). So `azd down` never sees `rg-jahbadh-ai` and can never remove it.

**What it costs until 10 Nov** (UAE North prices, checked 19 Oct):

| Item | Cost |
|---|---|
| Container Registry Basic | $0.1666 a day, about $3.50 from 20 Oct to 10 Nov |
| Container app while it sleeps between visits (`MIN_REPLICAS 0`) | nothing idle; the monthly free grant covers hours of watching |
| Container app always on for judging (`MIN_REPLICAS 1`, 25 Oct to 10 Nov) | about $3.40 idle, plus a few cents an hour while people watch |
| Storage account and file share | a few cents |
| Building and shipping on GitHub Actions | free (public repo) |
| Log Analytics and traces | free: the app's logs are capped, and the traces are small |
| A live run ("Run a fresh match" or a spotlight) | about $0.35 for the desk's own lines, about $0.70 to $0.85 if a viewer adds all 8 extra versions, at most 3 a day |

So the setup is about $8 until 10 Nov, plus live runs. If judges used all 3 live runs every day from 25 Oct to 10 Nov (about 51 runs) and added every version each time, that adds at most about $40 to $45. The credit had about $95 left on 20 Oct, and the budget alerts at $50 and $80 (step 11) would tell you well before it runs out.

The commands below are for PowerShell, run from the repo folder.

## 1. Install the Azure CLI and the Azure Developer CLI

**Cost:** free.

```powershell
winget install -e --id Microsoft.AzureCLI
winget install -e --id Microsoft.Azd
```

Close and reopen PowerShell, then check both are there:

```powershell
az version
azd version
```

**You should see:** a version number from each. You don't need Docker: azd builds the image in the cloud.

## 2. Sign in

**Cost:** free.

```powershell
az login
azd auth login
az account show --query "{name:name, id:id}" -o table
```

**You should see:** a browser sign-in for each, then your Azure for Students subscription in the table. If another subscription shows, pick the right one with `az account set --subscription <id>`.

## 3. Turn on the Azure services the app uses

**Cost:** free. This only lets your subscription use them.

```powershell
foreach ($ns in "Microsoft.App", "Microsoft.OperationalInsights", "Microsoft.ContainerRegistry", "Microsoft.Storage", "Microsoft.Insights", "Microsoft.ManagedIdentity") { az provider register --namespace $ns }
```

Registering can take a few minutes. Check it:

```powershell
foreach ($ns in "Microsoft.App", "Microsoft.OperationalInsights", "Microsoft.ContainerRegistry", "Microsoft.Storage", "Microsoft.Insights", "Microsoft.ManagedIdentity") { "$ns " + (az provider show --namespace $ns --query registrationState -o tsv) }
```

**You should see:** `Registered` next to all six.

## 4. Make the azd environment

**Cost:** free. This only writes settings into the `.azure` folder on your machine (it's gitignored).

```powershell
azd env new jahbadh
azd env set AZURE_LOCATION uaenorth
azd env set AZURE_SUBSCRIPTION_ID (az account show --query id -o tsv)
```

The last line pins the environment to the subscription `az` is on, which you picked in step 2. Set it even if azd didn't ask, so it can never fall back to another subscription on your account.

Find the Translator resource's name and save it:

```powershell
az cognitiveservices account list --resource-group rg-jahbadh-ai --query "[].{name:name, kind:kind}" -o table
azd env set TRANSLATOR_NAME <the name next to TextTranslation>
```

Make a fresh random ingest token. This line makes it and saves it in one go, so it never shows on screen:

```powershell
azd env set JAHBADH_INGEST_TOKEN (.venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(24))")
```

**Check it** (the first line hides the token, so it's safe to screenshot):

```powershell
azd env get-values | Select-String -NotMatch "TOKEN"
if (azd env get-value JAHBADH_INGEST_TOKEN) { "token is set" }
```

**You should see:** `AZURE_ENV_NAME="jahbadh"`, `AZURE_LOCATION="uaenorth"`, your Azure for Students `AZURE_SUBSCRIPTION_ID` and `TRANSLATOR_NAME`, then `token is set`. Never paste the token into a chat.

## 5. Preview what will be made

**Cost:** free. Nothing is created.

```powershell
azd provision --preview
```

**You should see:** a list of resources to create, all in `rg-jahbadh-app`: the resource group, a Log Analytics workspace, a container registry, a storage account, the Container Apps environment and the container app. Smaller pieces that live under these (the file share, the two identities and their roles, the environment's storage link) are made with them but not listed. Nothing should be listed in `rg-jahbadh-ai`. Read it through. If anything else shows up, stop and ask.

## 6. Create the resources

**Cost:** this is the step that starts the costs in the table above. Only run it after a yes.

```powershell
azd provision
```

It takes about 5 minutes. **You should see:** `SUCCESS`. The container app exists now but runs a public placeholder image, so the site doesn't show the desk yet. Step 7 ships the real image.

Why not `azd up`, which would also build and ship? azd builds the image inside the registry (ACR Tasks), and Microsoft has paused ACR Tasks for subscriptions on free credits, Azure for Students included. `azd up` there stops with `TasksOperationsNotAllowed`. On a pay-as-you-go subscription, `azd up` works and you can skip step 7.

## 7. Ship the app from GitHub

**Cost:** free. GitHub Actions minutes are free for public repos.

The Deploy workflow (`.github/workflows/deploy.yml`) runs the tests, builds the image with Docker on GitHub's machine, pushes it to the registry and points the app at it. It signs in as `id-jahbadh-deploy`, an identity that only trusts GitHub runs on this repo's `main` branch, so no password is stored anywhere. It only runs when you press the button.

First, print the five values the workflow needs (none of them is a secret, they're ids and addresses):

```powershell
"AZURE_CLIENT_ID = " + (azd env get-value AZURE_DEPLOY_CLIENT_ID)
"AZURE_TENANT_ID = " + (az account show --query tenantId -o tsv)
"AZURE_SUBSCRIPTION_ID = " + (azd env get-value AZURE_SUBSCRIPTION_ID)
"AZURE_CONTAINER_REGISTRY_ENDPOINT = " + (azd env get-value AZURE_CONTAINER_REGISTRY_ENDPOINT)
"SERVICE_API_URI = " + (azd env get-value SERVICE_API_URI)
```

Then add them on GitHub:

1. Open the repo on GitHub, then **Settings**, **Secrets and variables**, **Actions**, and the **Variables** tab.
2. Choose **New repository variable** for each of the five, with exactly the name and value printed above. Use Variables, not Secrets.

Then run it:

1. Open the **Actions** tab, pick **Deploy** on the left, then **Run workflow** on `main`.
2. Wait for both jobs to go green: the tests take about 7 minutes, the build and ship about 5.

**You should see:** a green run whose last step prints `{"ok":true}`. Save the address for the checks below:

```powershell
$url = azd env get-value SERVICE_API_URI
```

**If "Sign in to Azure" fails** with `AADSTS700213` (no matching federated identity), the message names the subject GitHub sent. Send it over: the trusted subject in `infra/app.bicep` must match it exactly. To ship a new version later, just press Run workflow again.

## 8. Give the app's identity its two roles

**Cost:** free.

This lets the app call the model ("Cognitive Services OpenAI User" on Foundry) and Translator ("Cognitive Services User" on Translator), and nothing more. It's the one command that touches `rg-jahbadh-ai`, and it only adds these two role assignments there.

```powershell
az deployment group create --resource-group rg-jahbadh-ai --template-file infra/roles.bicep --parameters principalId=$(azd env get-value APP_IDENTITY_PRINCIPAL_ID) translatorName=$(azd env get-value TRANSLATOR_NAME)
```

**You should see:** `"provisioningState": "Succeeded"`. Roles can take up to 10 minutes to start working.

**If it says `AuthorizationFailed`:** the subscription won't let you hand out roles. Skip to step 13 for the key fallback.

## 9. Check the site

**Cost:** free (replay never calls the model).

```powershell
curl.exe -s "$url/api/health"
curl.exe -s "$url/api/config"
```

**You should see:** `{"ok":true}`, then the config with `"live_mode":true` and the match-042 showcase.

Then open the URL in a browser: replay should play, and the Fan, Analyst and Player watch views should all work. Open it on your phone too.

**The cold start:** leave the site alone for 15 minutes so the app goes to sleep, then time the first request:

```powershell
curl.exe -s -o NUL -w "%{time_total}`n" "$url/api/health"
```

Write the number down (it goes in the README). A second request straight after should be quick.

## 10. Traces in Foundry: already connected

**Cost:** free. Nothing to click.

When you made the Foundry resource, Azure also made an Application Insights resource for it, `jahbadh-foundry-appinsights` in `rg-jahbadh-ai`, and connected it to the `jahbadh` project. The templates send the app's traces straight there (they only read its connection string), so the agents' traces land where Foundry already looks. You can check the connection without changing anything:

```powershell
az rest --method get --url "https://management.azure.com/subscriptions/$(azd env get-value AZURE_SUBSCRIPTION_ID)/resourceGroups/rg-jahbadh-ai/providers/Microsoft.CognitiveServices/accounts/jahbadh-foundry/projects/jahbadh/connections?api-version=2025-06-01" --query "value[].{name:name, category:properties.category}" -o table
```

**You should see:** one connection with category `AppInsights`. Traces show up after the live run in step 12.

**Optional, but a good idea:** that resource's Log Analytics workspace, `jahbadh-foundry-logs`, has no daily cap. Our traces are small, well inside the free 5 GB a month, but a cap is a cheap guard. This changes a setting on a Foundry-group resource, so only run it if you're happy to:

```powershell
az monitor log-analytics workspace update --resource-group rg-jahbadh-ai --workspace-name jahbadh-foundry-logs --quota 0.15
```

## 11. Try the budget alerts

**Cost:** free.

1. In the Azure portal, open **Cost Management**, then **Budgets**, then **Add**.
2. Make a monthly budget of $50 for the subscription, with an email alert at 100%.
3. Make a second one at $80.

**If Azure refuses** (Microsoft's docs say Azure for Students may not support budgets), the fallback is the credit's own hard stop: Azure stops paid services when the credit runs out. Check the balance at [microsoftazuresponsorships.com](https://www.microsoftazuresponsorships.com/Balance) every couple of days. Either way, note which one we have, because it goes in the README.

## 12. One live run

**Cost:** about $0.35, or about $0.70 to $0.85 if you add all 8 extra versions, and it uses one of today's 3 live runs. Only run it after a yes.

Open the site and press **Run a fresh match** in the top bar, next to the replay speeds. Agent lines arrive about 1 to 2 minutes after each key moment.

**You should see:**
- agent lines in the feed, each with evidence you can click
- `curl.exe -s "$url/api/config"` shows `"live_remaining":2`
- in the Azure portal, the storage account's **File shares**, then `state`, has a `live.json` (so the counter survives restarts)
- after a few minutes, traces for the agents (analyst, tactical, writer, referee): in the Azure portal, open `jahbadh-foundry-appinsights`, then **Search** (or **Transaction search**), and in Foundry wherever this project lists traces

If the feed says live mode isn't set up, or the lines never come, the roles from step 8 may still be settling. Wait 10 minutes and try once more. If it still fails, use step 13.

## 13. Only if step 8 failed: the key fallback

**Cost:** free.

The app always prefers a key when it has one. Type the keys in your own terminal (never in a chat). Find them in the portal: the Foundry resource's **Keys and Endpoint**, and the same page on the Translator resource.

```powershell
azd env set FOUNDRY_KEY <the Foundry key>
azd env set TRANSLATOR_KEY <the Translator key>
azd provision
```

They're kept as Container Apps secrets, never in the repo. The README then says the cloud app uses keys and why.

## 14. On submission day: keep one copy always on

**Cost:** about $3.40 until 10 Nov (see the table).

```powershell
azd env set MIN_REPLICAS 1
azd provision
```

**You should see:** the app keeps its image (provision reads the one it's running). In the portal, the container app's **Scale** shows min 1, max 1. The site now answers straight away, with no cold start.

## 15. After 10 Nov: take it all down

**Cost:** stops the costs.

```powershell
azd down
```

**You should see:** azd lists `rg-jahbadh-app` and asks you to confirm. It's the only group it removes. Foundry and Translator stay in `rg-jahbadh-ai`. The two role assignments from step 8 are left pointing at an identity that's gone. They're harmless, and you can delete them in the portal under each resource's **Access control (IAM)**.

## Good to know

**Changing a secret needs a restart.** If `azd provision` only changes a secret's value (the ingest token, a key, the trace connection string), Container Apps keeps the running copy as it is, so it still has the old value. Restart it to pick up the new one (free, about 30 seconds):

```powershell
$rev = az resource show --ids "/subscriptions/$(azd env get-value AZURE_SUBSCRIPTION_ID)/resourceGroups/rg-jahbadh-app/providers/Microsoft.App/containerApps/ca-jahbadh" --api-version 2026-07-01 --query properties.latestRevisionName -o tsv
az rest --method post --url "https://management.azure.com/subscriptions/$(azd env get-value AZURE_SUBSCRIPTION_ID)/resourceGroups/rg-jahbadh-app/providers/Microsoft.App/containerApps/ca-jahbadh/revisions/$rev/restart?api-version=2026-07-01"
```
