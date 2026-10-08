package dev.p2pkit.sample.android.rpclab

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp

/** English developer application; appearance never changes trust, operation ownership or live observers. */
@Composable
internal fun RpcLabTheme(content: @Composable () -> Unit) {
    val colors = rpcLabColors(isSystemInDarkTheme())
    MaterialTheme(colorScheme = colors) {
        Surface(Modifier.fillMaxSize(), color = colors.background, content = content)
    }
}

internal fun rpcLabColors(dark: Boolean): ColorScheme = if (dark) {
    darkColorScheme(
        primary = Color(0xFF9DC7FF), primaryContainer = Color(0xFF153E6E),
        secondary = Color(0xFF80D5C6), background = Color(0xFF101820), surface = Color(0xFF17212B),
    )
} else {
    lightColorScheme(
        primary = Color(0xFF205EA6), primaryContainer = Color(0xFFEAF3FF),
        onPrimaryContainer = Color(0xFF12385F), secondary = Color(0xFF176C60),
        background = Color(0xFFF3F6FA), surface = Color.White,
    )
}

@Composable
internal fun RpcLabPage(content: @Composable ColumnScope.() -> Unit) {
    Column(Modifier.fillMaxSize().safeDrawingPadding().imePadding().verticalScroll(rememberScrollState())
        .padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp), content = content)
}

@Composable
internal fun RpcLabHero(status: String, role: String) {
    Card(Modifier.fillMaxWidth(), shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer,
            contentColor = MaterialTheme.colorScheme.onPrimaryContainer)) {
        Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("LOCAL API WORKSPACE", style = MaterialTheme.typography.labelMedium)
            Text("P2pKit RPC", style = MaterialTheme.typography.headlineLarge)
            Text(role, style = MaterialTheme.typography.titleMedium)
            Text(status, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@Composable
internal fun RpcLabSectionHeading(title: String, subtitle: String) {
    Column(Modifier.padding(top = 16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(title, Modifier.semantics { heading() }, style = MaterialTheme.typography.titleLarge)
        Text(subtitle, style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
internal fun RpcLabEmptyState(title: String, description: String) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            Text(description, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

/** Disclosure owns visibility only. It never owns a role, approval presenter, observer or request data. */
@Composable
internal fun RpcLabDisclosure(title: String, content: @Composable () -> Unit) {
    val visibility = remember { RpcLabDisclosureState() }
    val expanded = visibility.expanded
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        TextButton(visibility::toggle, Modifier.fillMaxWidth().semantics {
            stateDescription = if (expanded) "Expanded" else "Collapsed"
        }) { Text(if (expanded) "Hide $title" else title) }
        if (expanded) content()
    }
}

internal class RpcLabDisclosureState {
    var expanded by mutableStateOf(false)
        private set
    fun toggle() { expanded = !expanded }
}
