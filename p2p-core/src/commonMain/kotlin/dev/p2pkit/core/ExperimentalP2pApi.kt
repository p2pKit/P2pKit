package dev.p2pkit.core

/**
 * Marker for API surface that may change before stabilization.
 *
 * Anything annotated with [ExperimentalP2pApi] is subject to source-incompatible
 * change without a deprecation cycle. Apps must opt in explicitly.
 */
@RequiresOptIn(
    message = "This P2pKit API is experimental and may change in a future release.",
    level = RequiresOptIn.Level.WARNING
)
@Retention(AnnotationRetention.BINARY)
@Target(
    AnnotationTarget.CLASS,
    AnnotationTarget.FUNCTION,
    AnnotationTarget.PROPERTY,
    AnnotationTarget.TYPEALIAS
)
public annotation class ExperimentalP2pApi
