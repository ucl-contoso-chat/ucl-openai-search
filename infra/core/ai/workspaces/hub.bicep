// Creates an Azure AI resource with proxied endpoints for the Azure AI services provider

@description('Azure region of the deployment')
param location string

@description('Tags to add to the resources')
param tags object

@description('AI hub name')
param aiHubName string

@description('AI project name')
param aiProjectName string

@description('ID of the application insights resource for storing diagnostics logs')
param applicationInsightsId string = ''

@description('ID of the container registry resource for storing docker images')
param containerRegistryId string = ''

@description('ID of the key vault resource for storing connection strings')
param keyVaultId string

@description('Is managed identity enabled')
param managedIdentity bool = true

@description('ID of the storage account resource for storing experimentation outputs')
param storageAccountId string

@description('ID of the AI Services resource')
param aiServicesId string

@description('AI Services endpoint')
param aiServicesTarget string

@description('ID of the AI Search resource')
param aiSearchId string

@description('AI Search endpoint')
param aiSearchTarget string

resource aiHub 'Microsoft.MachineLearningServices/workspaces@2024-04-01' = {
  name: aiHubName
  location: location
  tags: tags
  identity: { type: managedIdentity ? 'SystemAssigned' : 'None' }
  properties: {
    keyVault: keyVaultId
    storageAccount: storageAccountId
    containerRegistry: containerRegistryId
    applicationInsights: applicationInsightsId
  }
  kind: 'hub'

  resource aiServicesConnection 'connections' = {
    name: '${aiHubName}-connection-oai'
    properties: {
      category: 'AzureOpenAI'
      target: aiServicesTarget
      authType: 'AAD'
      isSharedToAll: false
      metadata: {
        ApiType: 'Azure'
        ResourceId: aiServicesId
      }
    }
  }

  resource aiSearchConnection 'connections' = {
    name: '${aiHubName}-connection-search'
    properties: {
      category: 'CognitiveSearch'
      target: aiSearchTarget
      authType: 'AAD'
      isSharedToAll: false
      metadata: {
        ApiType: 'Azure'
        ResourceId: aiSearchId
      }

    }
  }
}

resource aiProject 'Microsoft.MachineLearningServices/workspaces@2024-04-01' = {
  name: aiProjectName
  location: location
  tags: tags
  identity: { type: managedIdentity ? 'SystemAssigned' : 'None' }
  properties: {
    hubResourceId: aiHub.id
  }
  kind: 'project'
}

output aiHubID string = aiHub.id
output aiProjectID string = aiProject.id
