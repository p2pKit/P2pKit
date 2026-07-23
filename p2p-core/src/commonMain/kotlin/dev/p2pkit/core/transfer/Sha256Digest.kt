package dev.p2pkit.core.transfer

/**
 * A SHA-256 digest used by the authenticated file-transfer protocol.
 *
 * The 32 input bytes are copied on construction and every [bytes] access
 * returns a new copy, so callers cannot mutate a prepared source contract
 * after it has been offered to a peer.
 */
public class Sha256Digest(bytes: ByteArray) {
    private val value: ByteArray = bytes.copyOf()

    init {
        require(value.size == SIZE_BYTES) {
            "SHA-256 digest must be $SIZE_BYTES bytes, got ${value.size}"
        }
    }

    /** Defensive copy of the 32 digest bytes. */
    public val bytes: ByteArray get() = value.copyOf()

    override fun equals(other: Any?): Boolean =
        this === other || other is Sha256Digest && value.contentEquals(other.value)

    override fun hashCode(): Int = value.contentHashCode()

    override fun toString(): String = buildString(SIZE_BYTES * 2) {
        for (byte in value) {
            val unsigned = byte.toInt() and 0xff
            append(HEX[unsigned ushr 4])
            append(HEX[unsigned and 0x0f])
        }
    }

    internal fun copyBytes(): ByteArray = value.copyOf()

    public companion object {
        /** Number of bytes in a SHA-256 digest. */
        public const val SIZE_BYTES: Int = 32
        private const val HEX: String = "0123456789abcdef"
    }
}
