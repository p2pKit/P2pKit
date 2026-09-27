package dev.p2pkit.sample.rpc

import dev.p2pkit.core.PeerIdentity
import dev.p2pkit.rpc.RpcCallContext
import dev.p2pkit.rpc.RpcHostConfiguration
import dev.p2pkit.rpc.RpcNotification
import dev.p2pkit.rpc.RpcProcedure
import dev.p2pkit.rpc.RpcReply
import dev.p2pkit.rpc.RpcRetrySafety
import kotlinx.serialization.Serializable

@Serializable
public data class StockQuery(public val sku: String)

@Serializable
public data class StockReply(public val available: Int)

@Serializable
public data class StockReservation(public val sku: String, public val quantity: Int)

@Serializable
public data class ReservationReply(public val applicationReceipt: String)

@Serializable
public enum class StockProblem { NotFound, InsufficientStock, InvalidQuantity }

@Serializable
public data class StockChanged(public val sku: String)

public object InventoryContract {
    public val readStock: RpcProcedure<StockQuery, StockReply, StockProblem> = RpcProcedure(
        "inventory.read-stock", 1, StockQuery.serializer(), StockReply.serializer(), StockProblem.serializer(),
        retrySafety = RpcRetrySafety.Idempotent,
    )
    // Not idempotent: no automatic invocation after an ambiguous send, even after reconnect.
    public val reserveStock: RpcProcedure<StockReservation, ReservationReply, StockProblem> = RpcProcedure(
        "inventory.reserve-stock", 1, StockReservation.serializer(), ReservationReply.serializer(),
        StockProblem.serializer(),
    )
    public val stockChanged: RpcNotification<StockChanged> = RpcNotification(
        "inventory.stock-changed", 1, StockChanged.serializer(),
    )
}

/** All authorization, validation, transactions and storage remain inside the application. */
public interface InventoryApplication {
    public suspend fun mayRead(peer: PeerIdentity): Boolean
    public suspend fun mayReserve(peer: PeerIdentity): Boolean
    public suspend fun read(context: RpcCallContext, query: StockQuery): RpcReply<StockReply, StockProblem>
    public suspend fun reserve(
        context: RpcCallContext, request: StockReservation,
    ): RpcReply<ReservationReply, StockProblem>
}

public fun RpcHostConfiguration.inventory(application: InventoryApplication) {
    register(InventoryContract.readStock, authorize = application::mayRead, handler = application::read)
    register(InventoryContract.reserveStock, authorize = application::mayReserve, handler = application::reserve)
    notification(InventoryContract.stockChanged)
}
