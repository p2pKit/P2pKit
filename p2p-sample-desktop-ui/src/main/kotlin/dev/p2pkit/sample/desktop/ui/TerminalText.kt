package dev.p2pkit.sample.desktop.ui

/** Strip ANSI/OSC control bytes before writing SDK or peer data to a terminal. */
internal fun String.sanitizedForTerminal(): String = filterNot { it.isISOControl() }
