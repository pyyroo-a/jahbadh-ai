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

// Logs and traces. The daily cap keeps the month under the free 5 GB.
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

// Agent traces land here, and Foundry's Tracing page reads them once it is connected.
resource insights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-jahbadh-${suffix}'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logs.id
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

// Only the Consumption profile: pay for what runs, no plan management fee.
resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-jahbadh-${suffix}'
  location: location
  tags: tags
  properties: {
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

resource stateStorage 'Microsoft.App/managedEnvironments/storages@2024-03-01' = {
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

// Keys only go in if the role assignments were refused (docs/deploy.md step 11). A key always wins in the app.
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
        { name: 'appinsights-connection', value: insights.properties.ConnectionString }
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
output appInsightsName string = insights.name
output identityPrincipalId string = identity.properties.principalId
