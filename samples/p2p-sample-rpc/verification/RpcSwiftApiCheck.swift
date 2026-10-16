import Foundation
import P2pKitRpcExample

// Compile-only public-consumer fixture. Nothing here is invoked by validation.
// Applications construct/configure the shared Kotlin facade and own permissions,
// trust, authorization, foreground lifecycle and dispatch onto their UI actor.

func pairAndConnect(client: InventoryClient, trustedLocalQr: String) async throws -> RpcSelectedHost {
    let host = try await client.pairFromTrustedQr(qr: trustedLocalQr)
    try await client.connect(host: host)
    return host
}

func inspectStock(client: InventoryClient, sku: String) async throws -> StockViewResult {
    let result = try await client.readStock(sku: sku)
    // Business errors and infrastructure/execution evidence are distinct fields.
    _ = result.available
    _ = result.businessError
    _ = result.infrastructureError
    _ = result.executionEvidence
    return result
}

func reserveWithoutAutomaticReplay(client: InventoryClient, sku: String, quantity: Int32) async throws {
    // An error/timeout after transmission is not permission to repeat a reservation.
    _ = try await client.reserveStock(sku: sku, quantity: quantity)
}

func observeStock(client: InventoryClient, onChange: @escaping (String) -> Void) -> InventoryObservation {
    client.observeChanges { changed in onChange(changed.sku) }
}

func stopStockClient(client: InventoryClient, observation: InventoryObservation) async throws {
    observation.cancel()
    try await client.close()
}

func recoverInfrastructureFailure(_ error: Error) -> RpcFailure? {
    // Never classify by localizedDescription or log untrusted exception/payload text.
    (error as NSError).kotlinException as? RpcFailure
}
