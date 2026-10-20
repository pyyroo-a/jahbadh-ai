// Everything the app needs, all in rg-jahbadh-app. Removing this group removes all of it and nothing else.
param location string
param environmentName string

@minValue(0)
@maxValue(1)
param minReplicas int = 0

@secure()
param ingestToken string

@secure()
param foundryKey string

@secure()
param translatorKey string

@secure()
param appInsightsConnectionString string

param apiExists bool
param foundryBaseUrl string
param translatorResourceId string
param translatorRegion string

var suffix = uniqueString(resourceGroup().id)
var tags = { 'azd-env-name': environmentName }
var appName = 'ca-jahbadh'
// a public sample image, used only until the first azd deploy puts our image in
var placeholderImage = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
var acrPull = '7f951dda-4ed3-4680-a7ca-43fe172d538d' // AcrPull

// The app's container logs. The daily cap keeps the month under the free 5 GB. Traces go to Foundry's own
// Application Insights instead (see main.bicep), so they show up in Foundry.
resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-jahbadh-${suffix}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
    workspaceCapping: { dailyQuotaGb: json('0.15') }
  }
}

// Holds the app's image. No admin user: the app pulls with its identity.
resource registry 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: 'crjahbadh${suffix}'
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false
    policies: {
      azureADAuthenticationAsArmPolicy: { status: 'enabled' }
    }
  }
}

// The daily live counter lives on this share, so it survives restarts.
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: 'stjahbadh${suffix}'
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
    allowSharedKeyAccess: true // the Container Apps file mount signs in with the account key
  }
}

resource fileService 'Microsoft.Storage/storageAccounts/fileServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource share 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-05-01' = {
  parent: fileService
  name: 'state'
  properties: { shareQuota: 1 }
}

// The app signs in to Foundry, Translator and the registry as this identity. No keys.
resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-jahbadh-app'
  location: location
  tags: tags
}

resource pull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, identity.id, acrPull)
  scope: registry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPull)
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// GitHub's Deploy workflow signs in as this identity, with GitHub's own short-lived token: no stored password.
// It builds the image (Azure for Students can't build in the registry), pushes it, and points the app at it.
var contributor = 'b24988ac-6180-42a0-ab88-20f7382dd24c' // Contributor, on this resource group only
var acrPush = '8311e382-0749-4cb8-b61a-304f252e45ec' // AcrPush

resource deployIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-jahbadh-deploy'
  location: location
  tags: tags
}

resource githubMain 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: deployIdentity
  name: 'github-main'
  properties: {
    issuer: 'https://token.actions.githubusercontent.com'
    // GitHub repos made after 15 July 2026 put the owner and repo ids in the subject; only main is trusted
    subject: 'repo:pyyroo-a@195799002/jahbadh-ai@1423169832:ref:refs/heads/main'
    audiences: ['api://AzureADTokenExchange']
  }
}

resource deployContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, deployIdentity.id, contributor)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', contributor)
    principalId: deployIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource deployPush 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, deployIdentity.id, acrPush)
  scope: registry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPush)
    principalId: deployIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// Only the Consumption profile: pay for what runs, no plan management fee. The mode is set on purpose: left
// unset, Azure makes an Express environment, and Express can't mount the file share.
resource environment 'Microsoft.App/managedEnvironments@2026-07-01' = {
  name: 'cae-jahbadh-${suffix}'
  location: location
  tags: tags
  properties: {
    environmentMode: 'WorkloadProfiles'
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
    workloadProfiles: [
      { name: 'Consumption', workloadProfileType: 'Consumption' }
    ]
    zoneRedundant: false
  }
}

resource stateStorage 'Microsoft.App/managedEnvironments/storages@2026-07-01' = {
  parent: environment
  name: 'state'
  properties: {
    azureFile: {
      accountName: storage.name
      accountKey: storage.listKeys().keys[0].value
      shareName: share.name
      accessMode: 'ReadWrite'
    }
  }
}

module fetchImage 'fetch-image.bicep' = {
  name: 'fetch-api-image'
  params: {
    exists: apiExists
    name: appName
  }
}

// Keys only go in if the role assignments were refused (docs/deploy.md step 13). A key always wins in the app.
var keySecrets = concat(
  empty(foundryKey) ? [] : [{ name: 'foundry-key', value: foundryKey }],
  empty(translatorKey) ? [] : [{ name: 'translator-key', value: translatorKey }]
)
var keyEnv = concat(
  empty(foundryKey) ? [] : [{ name: 'FOUNDRY_API_KEY', secretRef: 'foundry-key' }],
  empty(translatorKey) ? [] : [{ name: 'TRANSLATOR_KEY', secretRef: 'translator-key' }]
)
var healthCheck = { path: '/api/health', port: 8000 }

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  tags: union(tags, { 'azd-service-name': 'api' })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identity.id}': {} }
  }
  dependsOn: [pull]
  properties: {
    managedEnvironmentId: environment.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        { server: registry.properties.loginServer, identity: identity.id }
      ]
      secrets: concat([
        { name: 'ingest-token', value: ingestToken }
        { name: 'appinsights-connection', value: appInsightsConnectionString }
      ], keySecrets)
    }
    template: {
      containers: [
        {
          name: 'api'
          image: empty(fetchImage.outputs.image) ? placeholderImage : fetchImage.outputs.image
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: concat([
            { name: 'JAHBADH_LIVE_MODE', value: 'on' }
            { name: 'JAHBADH_AZURE_IDENTITY', value: 'on' }
            { name: 'AZURE_CLIENT_ID', value: identity.properties.clientId }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'appinsights-connection' }
            { name: 'JAHBADH_INGEST_TOKEN', secretRef: 'ingest-token' }
            { name: 'JAHBADH_SELF_URL', value: 'http://127.0.0.1:8000' }
            { name: 'FOUNDRY_OPENAI_BASE_URL', value: foundryBaseUrl }
            { name: 'TRANSLATOR_RESOURCE_ID', value: translatorResourceId }
            { name: 'TRANSLATOR_REGION', value: translatorRegion }
          ], keyEnv)
          probes: [
            { type: 'Startup', httpGet: healthCheck, initialDelaySeconds: 5, periodSeconds: 10, failureThreshold: 10, timeoutSeconds: 5 }
            { type: 'Readiness', httpGet: healthCheck, periodSeconds: 30, failureThreshold: 3, timeoutSeconds: 5 }
            { type: 'Liveness', httpGet: healthCheck, periodSeconds: 30, failureThreshold: 3, timeoutSeconds: 5 }
          ]
          volumeMounts: [
            { volumeName: 'state', mountPath: '/data/state' }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: 1
      }
      volumes: [
        { name: 'state', storageType: 'AzureFile', storageName: stateStorage.name }
      ]
    }
  }
}

output registryEndpoint string = registry.properties.loginServer
output uri string = 'https://${app.properties.configuration.ingress.fqdn}'
output identityPrincipalId string = identity.properties.principalId
output deployClientId string = deployIdentity.properties.clientId
