// Lets the app's identity call the model and Translator, and nothing more. You run this with its own command
// (docs/deploy.md step 8), so azd never deploys anything into the Foundry resource group.
param principalId string
param foundryName string = 'jahbadh-foundry'
param translatorName string

var openAiUser = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd' // Cognitive Services OpenAI User: call the model
var cognitiveServicesUser = 'a97b65f3-24c7-4388-baec-2e87135dc908' // Cognitive Services User: call Translator

resource foundry 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: foundryName
}

resource translator 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: translatorName
}

resource foundryRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, principalId, openAiUser)
  scope: foundry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', openAiUser)
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

resource translatorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(translator.id, principalId, cognitiveServicesUser)
  scope: translator
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesUser)
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}
