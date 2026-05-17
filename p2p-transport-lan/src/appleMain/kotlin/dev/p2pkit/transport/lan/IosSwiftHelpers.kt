package dev.p2pkit.transport.lan

import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.Peer

/**
 * Swift-friendly snapshot accessors for the kit's reactive state.
 *
 * **Why:** Kotlin/Native erases generic type arguments when crossing the
 * ObjC bridge for `id`-typed properties. `kit.peers.value` (a
 * `StateFlow<Set<Peer>>`) is exposed to Swift as `Any?` — the runtime
 * payload is a Kotlin `Set<Peer>` that is NOT auto-converted to `NSSet`.
 * From Swift the `as? NSSet` / `as? Set<Peer>` casts both return nil, so
 * the consumer cannot iterate the discovered peers.
 *
 * These extension functions return a concrete `List<T>`. Direct function
 * return types are not generic-erased; Kotlin/Native bridges `List<T>`
 * to `NSArray<T *>`, which Swift consumes as `[T]` without any cast
 * gymnastics. Use these from Swift for every poll/refresh:
 *
 * ```swift
 * let peers: [Peer] = kit.peersSnapshot() as? [Peer] ?? []
 * let sessions: [P2pSession] = kit.sessionsSnapshot() as? [P2pSession] ?? []
 * ```
 *
 * The helpers are pure read operations — no caching, no side effects.
 * They live in `:p2p-transport-lan`'s `appleMain` so the iOS framework
 * exports them as part of `P2pKitShared`; this avoids polluting
 * `:p2p-core`'s commonMain with iOS-shaped APIs.
 */
public fun P2pKit.peersSnapshot(): List<Peer> = peers.value.toList()

public fun P2pKit.sessionsSnapshot(): List<P2pSession> = sessions.value.toList()
