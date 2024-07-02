param location string = resourceGroup().location
param tags object = {}
param deployments array = []

resource onlineEndpoints 'Microsoft.MachineLearningServices/workspaces/onlineEndpoints@2024-04-01' = [for deployment in deployments: {
  name: deployment.name
  location: location
  tags: tags
  properties: {
    authMode: 'Key'
  }
}]

resource onlineEndpointDeployments 'Microsoft.MachineLearningServices/workspaces/onlineEndpoints/deployments@2024-04-01' = [for (deployment, i) in deployments: {
  name: '${deployment.name}-deployment'
  location: location
  tags: tags
  parent: onlineEndpoints[i]
  sku: contains(deployment, 'sku') ? deployment.sku : {
    name: 'Standard'
    capacity: 20
  }
  properties: {
    appInsightsEnabled: true
    endpointComputeType: 'Managed'
    scaleSettings: {
      scaleType: 'Default'
    }
    model: deployment.model
  }
}]

output endpoints array = [for i in range(0, length(deployments)): {
  id: onlineEndpoints[i].id
  name: onlineEndpoints[i].name
}]

// resource onlineEndpoints 'Microsoft.MachineLearningServices/workspaces/onlineEndpoints@2024-04-01' = [for deployment in deployments: {
//   name: onlineEndpointName
//   location: location
//   tags: tags
//   sku: {
//     name: 'S1'
//   }
//   properties: {
//     authMode: 'Key'
//   }

//   resource onlineEndpointDeployment 'deployments@2024-04-01' = {
//     name: '${onlineEndpointName}-deployment'
//     location: location
//     tags: tags
//     sku: {
//       name: 'S1'
//     }
//     properties: {
//       appInsightsEnabled: true
//       endpointComputeType: 'Managed'
//       scaleSettings: {
//         scaleType: 'Default'
//       }
//     }
//   }
// }]

// resource onlineEndpoint 'Microsoft.MachineLearningServices/workspaces/onlineEndpoints@2024-04-01' = {
//   name: onlineEndpointName
//   location: location
//   tags: tags
//   sku: {
//     name: 'S1'
//   }
//   properties: {
//     authMode: 'Key'
//   }

//   resource onlineEndpointDeployment 'deployments@2024-04-01' = {
//     name: '${onlineEndpointName}-deployment'
//     location: location
//     tags: tags
//     sku: {
//       name: 'S1'
//     }
//     properties: {
//       appInsightsEnabled: true
//       endpointComputeType: 'Managed'
//       scaleSettings: {
//         scaleType: 'Default'
//       }
//     }
//   }
// }

// output endpoint string = onlineEndpoint.properties.endpoint
// output id string = onlineEndpoint.id
