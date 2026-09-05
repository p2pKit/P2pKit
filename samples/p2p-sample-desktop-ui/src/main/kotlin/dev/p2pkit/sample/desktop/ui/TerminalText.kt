package dev.p2pkit.sample.desktop.ui

/** Injection defence only: strips ANSI/OSC control bytes; does not redact private content. */
internal fun String.sanitizedForTerminal(): String = filterNot { it.isISOControl() }
