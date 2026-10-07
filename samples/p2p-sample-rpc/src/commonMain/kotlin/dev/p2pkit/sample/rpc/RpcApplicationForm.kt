package dev.p2pkit.sample.rpc

public enum class RpcApplicationProcedure { GetUser, ListItems, SendMessage }

/** Bounded editable form shared by all frontends. Only fields belonging to the chosen procedure are parsed. */
public class RpcApplicationInput private constructor(
    public val procedure: RpcApplicationProcedure,
    public val userId: Int,
    public val offset: Int,
    public val limit: Int,
    public val message: String,
) {
    override fun toString(): String = "RpcApplicationInput(application data omitted)"

    public companion object {
        @Throws(Exception::class)
        public fun parse(
            procedure: RpcApplicationProcedure, userId: String, offset: String, limit: String, message: String,
        ): RpcApplicationInput = when (procedure) {
            RpcApplicationProcedure.GetUser -> RpcApplicationInput(procedure, number(userId), 0, 20, "")
            RpcApplicationProcedure.ListItems -> RpcApplicationInput(procedure, 0, number(offset), number(limit), "")
            RpcApplicationProcedure.SendMessage -> {
                require(message.length <= 1_024) { "Message form exceeds its local bound" }
                RpcApplicationInput(procedure, number(userId), 0, 20, message)
            }
        }

        private fun number(value: String): Int {
            require(value.length in 1..11 && value.matches(Regex("-?(0|[1-9][0-9]{0,9})"))) {
                "Enter a whole decimal number"
            }
            return requireNotNull(value.toIntOrNull()) { "Number must fit a signed 32-bit integer" }
        }
    }
}
