package dev.p2pkit.sample.rpc

import dev.p2pkit.core.AppId
import dev.p2pkit.rpc.RpcClient
import dev.p2pkit.rpc.RpcExecutionEvidence
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcFailureKind
import dev.p2pkit.rpc.RpcInvitation
import dev.p2pkit.rpc.RpcPlatform
import dev.p2pkit.rpc.RpcReply
import dev.p2pkit.rpc.RpcRetry
import dev.p2pkit.rpc.RpcSelectedHost
import dev.p2pkit.rpc.RpcTrustStore
import dev.p2pkit.transport.lan.OrganizationLan
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach

/** Concrete DTO facade for Swift: no serializers or generic handler registration at the Swift boundary. */
public class StockViewResult internal constructor(
    public val available: Int?,
    public val businessError: StockProblem?,
    public val infrastructureError: RpcFailureKind?,
    public val executionEvidence: RpcExecutionEvidence?,
)

public class InventoryObservation internal constructor(private val job: Job) {
    public fun cancel() { job.cancel() }
}

public class InventoryClient private constructor(private val client: RpcClient, private val scope: CoroutineScope) {
    @Throws(Exception::class)
    public suspend fun pairFromTrustedQr(qr: String): RpcSelectedHost {
        val invitation = RpcInvitation.parse(qr)
        return try { client.pair(invitation) } finally { invitation.clear() }
    }

    @Throws(Exception::class)
    public suspend fun connect(host: RpcSelectedHost) { client.connect(host) }

    @Throws(Exception::class)
    public suspend fun readStock(sku: String): StockViewResult = try {
        when (val reply = client.call(InventoryContract.readStock, StockQuery(sku), retry = RpcRetry.Idempotent())) {
            is RpcReply.Success -> StockViewResult(reply.value.available, null, null, null)
            is RpcReply.ApplicationError -> StockViewResult(null, reply.error, null, null)
        }
    } catch (cancelled: CancellationException) {
        throw cancelled
    } catch (failure: RpcFailure) {
        StockViewResult(null, null, failure.kind, failure.executionEvidence)
    }

    /** The UI must reconcile uncertain reservations with the application; never resubmit automatically. */
    @Throws(Exception::class)
    public suspend fun reserveStock(sku: String, quantity: Int): RpcReply<ReservationReply, StockProblem> =
        client.call(InventoryContract.reserveStock, StockReservation(sku, quantity), retry = RpcRetry.RecoverOnly())

    public fun observeChanges(onChange: (StockChanged) -> Unit): InventoryObservation = InventoryObservation(
        client.notifications(InventoryContract.stockChanged).onEach(onChange).launchIn(scope),
    )

    @Throws(Exception::class)
    public suspend fun close() { client.close() }

    public companion object {
        @Throws(Exception::class)
        public suspend fun create(
            platform: RpcPlatform, applicationScope: CoroutineScope, appId: AppId,
            lan: OrganizationLan, trustStore: RpcTrustStore,
        ): InventoryClient {
            val client = RpcClient.create(platform, applicationScope) {
                this.appId = appId
                this.lan = lan
                this.trustStore = trustStore
                notification(InventoryContract.stockChanged)
            }
            return InventoryClient(client, applicationScope)
        }
    }
}
