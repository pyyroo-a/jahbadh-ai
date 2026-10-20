// The image the app runs right now, so running provision again (say, for MIN_REPLICAS) never swaps it back
// to the placeholder. Empty before the first deploy.
param exists bool
param name string

resource existingApp 'Microsoft.App/containerApps@2024-03-01' existing = if (exists) {
  name: name
}

output image string = exists ? existingApp!.properties.template.containers[0].image : ''
