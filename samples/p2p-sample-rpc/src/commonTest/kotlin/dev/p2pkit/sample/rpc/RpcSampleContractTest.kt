package dev.p2pkit.sample.rpc

import dev.p2pkit.rpc.RpcLimits
import dev.p2pkit.rpc.RpcRetrySafety
import kotlinx.serialization.builtins.serializer
import kotlinx.serialization.json.Json
import kotlin.test.Test
import kotlin.test.assertEquals

class RpcSampleContractTest {
    @Test
    fun qualificationPayloadsHaveTheExactEncodedSizes() {
        assertEquals(
            1024, Json.encodeToString(String.serializer(), RpcCapacityContract.payload).encodeToByteArray().size,
        )
        val maximum = "a".repeat(RpcCapacityContract.MAXIMUM_BODY_BYTES - 2)
        assertEquals(1_048_576, Json.encodeToString(String.serializer(), maximum).encodeToByteArray().size)
    }

    @Test
    fun unsafeBusinessExampleNeverPromisesIdempotentExecution() {
        assertEquals(RpcRetrySafety.NeverReinvoke, InventoryContract.reserveStock.retrySafety)
        assertEquals(RpcRetrySafety.Idempotent, InventoryContract.readStock.retrySafety)
    }

    @Test
    fun targetIsNotSilentlyReducedToFitAnUnqualifiedHost() {
        assertEquals(128, RpcCapacityContract.CLIENTS)
        assertEquals(RpcLimits.host128().trustedClients, RpcCapacityContract.CLIENTS)
        assertEquals(2_304_000, RpcCapacityContract.CLIENTS * RpcCapacityContract.CALLS_PER_SECOND_PER_CLIENT *
            RpcCapacityContract.STEADY_SECONDS)
    }
}
