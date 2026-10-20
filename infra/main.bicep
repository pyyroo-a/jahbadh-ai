// Jahbadh on Azure. The app gets its own resource group, rg-jahbadh-app, so azd down can only ever remove the app.
// Foundry and Translator stay where they are in rg-jahbadh-ai: this file only reads them, it never changes them.
// The app's identity gets its two roles there from roles.bicep, which you run with its own command (docs/deploy.md).
targetScope = 'subscription'

@description('Where the app runs. Only the regions this subscription allows.')
@allowed(['germanywestcentral', 'austriaeast', 'uaenorth', 'polandcentral', 'centralindia'])
param location string = 'uaenorth'

@description('The azd environment name, used as a tag so azd can find the app.')
param environmentName string = 'jahbadh'

@description('The resource group that already holds Foundry and Translator. Only read here.')
param foundryResourceGroup string = 'rg-jahbadh-ai'

@description('The Foundry resource with the gpt-5-mini deployment.')
param foundryName string = 'jahbadh-foundry'

@description('The Translator resource, by name.')
param translatorName string

@description('1 keeps one copy always on (judging week), 0 lets it sleep when nobody is watching.')
@minValue(0)
@maxValue(1)
param minReplicas int = 0

@description('The token every write to the ingest API must carry.')
@secure()
param ingestToken string

@description('Only if Azure refuses the role assignments: the Foundry key, kept as a Container Apps secret.')
@secure()
param foundryKey string = ''

@description('Only if Azure refuses the role assignments: the Translator key, kept as a Container Apps secret.')
@secure()
param translatorKey string = ''

@description('Set by azd once the app exists, so provisioning again keeps the image it runs.')
param apiExists bool = false

resource appGroup 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-jahbadh-app'
  location: location
  tags: { 'azd-env-name': environmentName }
}

resource foundryGroup 'Microsoft.Resources/resourceGroups@2024-03-01' existing = {
  name: foundryResourceGroup
}

resource translator 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: translatorName
  scope: foundryGroup
}

module app 'app.bicep' = {
  name: 'jahbadh-app'
  scope: appGroup
  params: {
    location: location
    environmentName: environmentName
    minReplicas: minReplicas
    ingestToken: ingestToken
    foundryKey: foundryKey
    translatorKey: translatorKey
    apiExists: apiExists
    foundryBaseUrl: 'https://${foundryName}.services.ai.azure.com/openai/v1/'
    translatorResourceId: translator.id
    translatorRegion: translator.location
  }
}

output AZURE_LOCATION string = location
output AZURE_RESOURCE_GROUP string = appGroup.name
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = app.outputs.registryEndpoint
output SERVICE_API_URI string = app.outputs.uri
output APPLICATIONINSIGHTS_NAME string = app.outputs.appInsightsName
output APP_IDENTITY_PRINCIPAL_ID string = app.outputs.identityPrincipalId
output FOUNDRY_RESOURCE_GROUP string = foundryResourceGroup
