package dev.p2pkit.sample.rpc

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse

class RpcApplicationFormTest {
    @Test
    fun onlyRelevantFieldsAreParsedAndBusinessValidationIsLeftToTheHost() {
        val user = RpcApplicationInput.parse(RpcApplicationProcedure.GetUser, "-1", "invalid", "invalid", "unused")
        assertEquals(-1, user.userId)
        assertEquals("", user.message)
        val items = RpcApplicationInput.parse(RpcApplicationProcedure.ListItems, "invalid", "0", "51", "unused")
        assertEquals(51, items.limit)
        val message = RpcApplicationInput.parse(RpcApplicationProcedure.SendMessage, "123", "invalid", "invalid", "")
        assertEquals("", message.message)
        assertEquals(123, message.userId)
    }

    @Test
    fun malformedOverflowAndUnboundedFormsFailBeforeAnRpcCanBeStarted() {
        for (number in listOf("", "+1", " 1", "1\n", "01", "2147483648", "-2147483649", "1".repeat(12))) {
            assertFailsWith<IllegalArgumentException> {
                RpcApplicationInput.parse(RpcApplicationProcedure.GetUser, number, "0", "20", "")
            }
        }
        assertFailsWith<IllegalArgumentException> {
            RpcApplicationInput.parse(RpcApplicationProcedure.SendMessage, "123", "0", "20", "x".repeat(1_025))
        }
        val message = RpcApplicationInput.parse(RpcApplicationProcedure.SendMessage, "123", "0", "20", "private-body")
        assertFalse(message.toString().contains("private-body"))
    }

    @Test
    fun discoveryLabelsAreBoundedAndCannotCarryControlOrDirectionalOverrides() {
        assertEquals("Unnamed device", rpcDeviceLabel("\n\u202e\u2066"))
        assertEquals("Phone", rpcDeviceLabel("\u202ePho\r\nne\u2069"))
        assertEquals(80, rpcDeviceLabel("x".repeat(5_000)).length)
    }
}
