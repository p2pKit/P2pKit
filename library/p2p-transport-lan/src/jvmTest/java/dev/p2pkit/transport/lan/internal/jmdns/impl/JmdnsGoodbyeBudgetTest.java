package dev.p2pkit.transport.lan.internal.jmdns.impl;

import org.junit.Test;

import java.util.concurrent.TimeUnit;

import static org.junit.Assert.assertEquals;

/** Socket-free arithmetic checks; the real-resource lifecycle suite remains required. */
public class JmdnsGoodbyeBudgetTest {
    @Test
    public void participantsConsumeOneOriginalAllowance() {
        JmDNSLifecycle.GoodbyeBudget budget = new JmDNSLifecycle.GoodbyeBudget(0L);
        assertEquals(5_000L, budget.remainingMillis(0L));
        assertEquals(500L, budget.remainingMillis(TimeUnit.MILLISECONDS.toNanos(4_500L)));
        assertEquals(100L, budget.remainingMillis(TimeUnit.MILLISECONDS.toNanos(4_900L)));
    }

    @Test
    public void laterParticipantsCannotRestartExpiredGoodbyes() {
        JmDNSLifecycle.GoodbyeBudget budget = new JmDNSLifecycle.GoodbyeBudget(0L);
        for (int participant = 0; participant < 4; participant++) {
            assertEquals(0L, budget.remainingMillis(TimeUnit.MILLISECONDS.toNanos(5_000L + participant)));
        }
    }

    @Test
    public void fractionalRemainderDoesNotResetOrigin() {
        JmDNSLifecycle.GoodbyeBudget budget = new JmDNSLifecycle.GoodbyeBudget(0L);
        long end = TimeUnit.MILLISECONDS.toNanos(5_000L);
        assertEquals(1L, budget.remainingMillis(end - 1L));
        assertEquals(0L, budget.remainingMillis(end));
        assertEquals(0L, budget.remainingMillis(end + 1L));
    }

    @Test
    public void negativeMonotonicOriginIsValid() {
        long origin = -TimeUnit.SECONDS.toNanos(100L);
        JmDNSLifecycle.GoodbyeBudget budget = new JmDNSLifecycle.GoodbyeBudget(origin);
        assertEquals(500L, budget.remainingMillis(origin + TimeUnit.MILLISECONDS.toNanos(4_500L)));
    }

    @Test
    public void monotonicSignedWrapPreservesElapsedTime() {
        long origin = Long.MAX_VALUE - TimeUnit.SECONDS.toNanos(1L);
        JmDNSLifecycle.GoodbyeBudget budget = new JmDNSLifecycle.GoodbyeBudget(origin);
        assertEquals(500L, budget.remainingMillis(origin + TimeUnit.MILLISECONDS.toNanos(4_500L)));
        assertEquals(0L, budget.remainingMillis(origin + TimeUnit.SECONDS.toNanos(5L)));
    }

    @Test
    public void newHostBudgetDoesNotReviveOldGeneration() {
        JmDNSLifecycle.GoodbyeBudget old = new JmDNSLifecycle.GoodbyeBudget(0L);
        long next = TimeUnit.SECONDS.toNanos(10L);
        JmDNSLifecycle.GoodbyeBudget fresh = new JmDNSLifecycle.GoodbyeBudget(next);
        assertEquals(0L, old.remainingMillis(next));
        assertEquals(5_000L, fresh.remainingMillis(next));
        assertEquals(0L, old.remainingMillis(next + 1L));
    }
}
