package dev.p2pkit.transport.lan

/** Private JNI ABI. Loading is explicit and verified by [MacLanNativeLoader], never by this class initializer. */
internal object MacLanNative : MacLanCalls {
    external fun abi(): Int
    external fun source(): String
    external fun constants(): IntArray
    override external fun open(index: Int, output: LongArray): Int
    override external fun bind(handle: Long, address: ByteArray, port: Int): Int
    override external fun listen(handle: Long, backlog: Int): Int
    override external fun accept(handle: Long, output: LongArray): Int
    override external fun connect(handle: Long, address: ByteArray, port: Int): Int
    override external fun connected(handle: Long): Int
    override external fun endpoint(handle: Long, remote: Int, address: ByteArray, port: IntArray): Int
    override external fun boundInterface(handle: Long, output: IntArray): Int
    override external fun option(handle: Long, option: Int, enabled: Int): Int
    override external fun read(handle: Long, bytes: ByteArray, offset: Int, length: Int): Int
    override external fun write(handle: Long, bytes: ByteArray, offset: Int, length: Int): Int
    override external fun poll(handle: Long, writable: Int, timeout: Int): Int
    override external fun close(handle: Long): Int
}

/** Deterministic internal test seam, never supplied by the public transport factory. */
internal interface MacLanCalls {
    fun open(index: Int, output: LongArray): Int
    fun bind(handle: Long, address: ByteArray, port: Int): Int
    fun listen(handle: Long, backlog: Int): Int
    fun accept(handle: Long, output: LongArray): Int
    fun connect(handle: Long, address: ByteArray, port: Int): Int
    fun connected(handle: Long): Int
    fun endpoint(handle: Long, remote: Int, address: ByteArray, port: IntArray): Int
    fun boundInterface(handle: Long, output: IntArray): Int
    fun option(handle: Long, option: Int, enabled: Int): Int
    fun read(handle: Long, bytes: ByteArray, offset: Int, length: Int): Int
    fun write(handle: Long, bytes: ByteArray, offset: Int, length: Int): Int
    fun poll(handle: Long, writable: Int, timeout: Int): Int
    fun close(handle: Long): Int
}
