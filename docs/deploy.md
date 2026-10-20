# Deploying Jahbadh to Azure

This guide puts the desk on Azure Container Apps, signed in without keys and traced into Foundry. You run every step yourself, in order. Each one says what it costs, what you should see and how to check it worked.

**What gets made.** Everything new goes in its own resource group, `rg-jahbadh-app`, in UAE North:

- a Container Apps environment (Consumption profile only, so there's no plan fee) and the container app `ca-jahbadh` (0.5 vCPU, 1 GiB, never more than one copy)
- a Container Registry (Basic) for the image
- a storage account with a small file share, `state`, which keeps the daily live counter through restarts
- Log Analytics (capped at 0.15 GB a day, so the month stays inside the free 5 GB) and Application Insights for traces
- a managed identity, `id-jahbadh-app`, which the app uses to sign in to the registry, Foundry and Translator

**What stays put.** Foundry, the `gpt-5-mini` deployment and Translator stay in `rg-jahbadh-ai`. The templates only read them. The one thing that touches that group is step 7, which gives the app's identity two roles there, and you run it with its own command. So `azd down` never sees `rg-jahbadh-ai` and can never remove it.

**What it costs until 10 Nov** (UAE North prices, checked 19 Oct):

| Item | Cost |
|---|---|
| Container Registry Basic | $0.1666 a day, about $3.50 from 20 Oct to 10 Nov |
| Container app while it sleeps between visits (`MIN_REPLICAS 0`) | nothing idle; the monthly free grant covers hours of watching |
| Container app always on for judging (`MIN_REPLICAS 1`, 25 Oct to 10 Nov) | about $3.40 idle, plus a few cents an hour while people watch |
| Storage account and file share | a few cents |
| Log Analytics and Application Insights | free under the daily cap |
| A live run ("Run a fresh match" or a spotlight) | about $0.50 each, at most 3 a day |

So the setup is about $7 to $8 until 10 Nov, plus live runs. If judges used all 3 live runs every day from 25 Oct to 10 Nov, that adds at most about $25. The credit had about $90 left on 20 Oct.

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
```

azd asks which subscription to use: pick the student one.

Find the Translator resource's name and save it:

```powershell
az cognitiveservices account list --resource-group rg-jahbadh-ai --query "[].{name:name, kind:kind}" -o table
azd env set TRANSLATOR_NAME <the name next to TextTranslation>
```

Make a fresh random ingest token. This line makes it and saves it in one go, so it never shows on screen:

```powershell
azd env set JAHBADH_INGEST_TOKEN (.venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(24))")
```

**Check it:** `azd env get-values` lists `AZURE_LOCATION="uaenorth"`, `TRANSLATOR_NAME` and `JAHBADH_INGEST_TOKEN`. Never paste the token into a chat.

## 5. Preview what will be made

**Cost:** free. Nothing is created.

```powershell
azd provision --preview
```

**You should see:** a list of resources to create, all in `rg-jahbadh-app`: the resource group, a Log Analytics workspace, Application Insights, a container registry, a storage account with its file share, the managed identity and its AcrPull role, the Container Apps environment with its storage link, and the container app. Nothing should be listed in `rg-jahbadh-ai`. Read it through. If anything else shows up, stop and ask.

## 6. Create it and ship the app

**Cost:** this is the step that starts the costs in the table above. Only run it after a yes.

```powershell
azd up
```

It takes about 5 to 10 minutes. First it creates the resources, then it uploads the code, builds the image in the registry and starts the app. For a minute before the build is done, the app runs a placeholder image and may look unhealthy. That's expected.

**You should see:** `SUCCESS` and an endpoint like `https://ca-jahbadh.<something>.uaenorth.azurecontainerapps.io`. Save it:

```powershell
$url = azd env get-value SERVICE_API_URI
```

## 7. Give the app's identity its two roles

**Cost:** free.

This lets the app call the model ("Cognitive Services OpenAI User" on Foundry) and Translator ("Cognitive Services User" on Translator), and nothing more. It's the one command that touches `rg-jahbadh-ai`, and it only adds these two role assignments there.

```powershell
az deployment group create --resource-group rg-jahbadh-ai --template-file infra/roles.bicep --parameters principalId=$(azd env get-value APP_IDENTITY_PRINCIPAL_ID) translatorName=$(azd env get-value TRANSLATOR_NAME)
```

**You should see:** `"provisioningState": "Succeeded"`. Roles can take up to 10 minutes to start working.

**If it says `AuthorizationFailed`:** the subscription won't let you hand out roles. Skip to step 12 for the key fallback.

## 8. Check the site

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

## 9. Connect Application Insights to Foundry

**Cost:** free.

1. Open [ai.azure.com](https://ai.azure.com) and the `jahbadh` project.
2. Open **Tracing** (under Observe or Monitoring in the left menu).
3. Choose **Connect** and pick the Application Insights resource whose name starts with `appi-jahbadh-`.

**You should see:** the Tracing page, empty for now. Traces show up after the live run in step 11.

## 10. Try the budget alerts

**Cost:** free.

1. In the Azure portal, open **Cost Management**, then **Budgets**, then **Add**.
2. Make a monthly budget of $50 for the subscription, with an email alert at 100%.
3. Make a second one at $80.

**If Azure refuses** (Microsoft's docs say Azure for Students may not support budgets), the fallback is the credit's own hard stop: Azure stops paid services when the credit runs out. Check the balance at [microsoftazuresponsorships.com](https://www.microsoftazuresponsorships.com/Balance) every couple of days. Either way, note which one we have, because it goes in the README.

## 11. One live run

**Cost:** about $0.50, and it uses one of today's 3 live runs. Only run it after a yes.

Open the site and press **Run a fresh match** in the top bar, next to the replay speeds. Agent lines arrive about 1 to 2 minutes after each key moment.

**You should see:**
- agent lines in the feed, each with evidence you can click
- `curl.exe -s "$url/api/config"` shows `"live_remaining":2`
- in the Azure portal, the storage account's **File shares**, then `state`, has a `live.json` (so the counter survives restarts)
- in Foundry's Tracing page, after a few minutes, traces for the agents (analyst, tactical, writer, referee)

If the feed says live mode isn't set up, or the lines never come, the roles from step 7 may still be settling. Wait 10 minutes and try once more. If it still fails, use step 12.

## 12. Only if step 7 failed: the key fallback

**Cost:** free.

The app always prefers a key when it has one. Type the keys in your own terminal (never in a chat). Find them in the portal: the Foundry resource's **Keys and Endpoint**, and the same page on the Translator resource.

```powershell
azd env set FOUNDRY_KEY <the Foundry key>
azd env set TRANSLATOR_KEY <the Translator key>
azd provision
```

They're kept as Container Apps secrets, never in the repo. The README then says the cloud app uses keys and why.

## 13. On submission day: keep one copy always on

**Cost:** about $3.40 until 10 Nov (see the table).

```powershell
azd env set MIN_REPLICAS 1
azd provision
```

**You should see:** the app keeps its image (provision reads the one it's running). In the portal, the container app's **Scale** shows min 1, max 1. The site now answers straight away, with no cold start.

## 14. After 10 Nov: take it all down

**Cost:** stops the costs.

```powershell
azd down
```

**You should see:** azd lists `rg-jahbadh-app` and asks you to confirm. It's the only group it removes. Foundry and Translator stay in `rg-jahbadh-ai`. The two role assignments from step 7 are left pointing at an identity that's gone. They're harmless, and you can delete them in the portal under each resource's **Access control (IAM)**.
