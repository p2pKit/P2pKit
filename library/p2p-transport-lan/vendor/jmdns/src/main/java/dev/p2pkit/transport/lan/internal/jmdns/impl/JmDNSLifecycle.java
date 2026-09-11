/*
 * Copyright 2026 P2pKit contributors.
 * Licensed under the Apache License, Version 2.0.
 * P2pKit lifecycle bookkeeping for the privately relocated JmDNS implementation.
 * See the accompanying PROVENANCE.json and MODIFICATIONS.txt.
 */
package dev.p2pkit.transport.lan.internal.jmdns.impl;

import java.net.MulticastSocket;
import java.util.ArrayList;
import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.TimeUnit;

import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSConstants;

/**
 * Per-instance lifetime ownership, deliberately independent of DNS protocol state.
 * Mutable fields are protected by this object's monitor. No user code or blocking
 * resource operation is called with that monitor held.
 */
final class JmDNSLifecycle {
    boolean terminalRequested;
    boolean startupInProgress;
    Thread startupOwner;
    boolean dispatchSealed;
    boolean generalTimerDisposed;
    boolean stateTimerDisposed;
    boolean starterDetached;
    int mutations;
    int tasks;
    int callbacks;
    int submissions;
    long nextAttempt;
    long socketPublications;
    long normalTaskStarts;
    Attempt attempt;
    Recovery recovery;
    final Set<MulticastSocket> sockets = Collections.newSetFromMap(
            new IdentityHashMap<MulticastSocket, Boolean>());
    final List<OwnedThread> listeners = new ArrayList<>();
    final List<Recovery> recoveries = new ArrayList<>();

    // ThreadLocal.withInitial is API 26 on Android; this library also runs on 24.
    private final ThreadLocal<Integer> dependentDepth = new ThreadLocal<Integer>() {
        @Override
        protected Integer initialValue() {
            return 0;
        }
    };

    void enterDependent() {
        dependentDepth.set(dependentDepth.get() + 1);
    }

    void exitDependent() {
        int depth = dependentDepth.get() - 1;
        if (depth == 0) {
            dependentDepth.remove();
        } else {
            dependentDepth.set(depth);
        }
    }

    boolean isDependent() {
        return dependentDepth.get() != 0;
    }

    synchronized boolean beginMutation(boolean cancellation) {
        if (dispatchSealed || (terminalRequested && !cancellation)) {
            return false;
        }
        mutations++;
        enterDependent();
        return true;
    }

    synchronized void endMutation() {
        exitDependent();
        mutations--;
        notifyAll();
    }

    synchronized boolean enterTask(boolean cancellation) {
        if (dispatchSealed || (terminalRequested && !cancellation)) {
            return false;
        }
        tasks++;
        enterDependent();
        return true;
    }

    synchronized void exitTask() {
        exitDependent();
        tasks--;
        notifyAll();
    }

    synchronized boolean reserveCallback(boolean submission) {
        if (terminalRequested) {
            return false;
        }
        callbacks++;
        if (submission) {
            submissions++;
        }
        return true;
    }

    synchronized void endSubmission() {
        submissions--;
        notifyAll();
    }

    synchronized void endCallback() {
        callbacks--;
        notifyAll();
    }

    static class OwnedThread {
        Thread thread;
        boolean launchResolved;
        boolean started;
    }

    static final class Recovery extends OwnedThread {
        boolean mutating = true;
    }

    static final class Attempt {
        final long id;
        final WaitBudget budget;
        final boolean nativeRequest;
        final OwnedThread helper;
        Thread owner;
        int joinedCallers;
        Outcome outcome;

        Attempt(long id, Thread owner, boolean nativeRequest, WaitBudget budget) {
            this.id = id;
            this.owner = owner;
            this.nativeRequest = nativeRequest;
            this.budget = budget;
            this.helper = nativeRequest ? new OwnedThread() : null;
        }
    }

    /** Published exactly once. A later retry never changes a joined result. */
    static final class Outcome {
        final Throwable failure;

        Outcome(long attemptId, List<Throwable> failures) {
            if (failures.isEmpty()) {
                failure = null;
            } else {
                CloseIncompleteException combined = new CloseIncompleteException(
                        "JmDNS close attempt " + attemptId + " did not dispose all owned resources",
                        failures.get(0));
                for (int index = 1; index < failures.size(); index++) {
                    combined.addSuppressed(failures.get(index));
                }
                failure = combined;
            }
        }

        void report() {
            if (failure != null) {
                // Do not change the shared outcome or another caller's interrupt status.
                throw new CloseIncompleteException(failure.getMessage(), failure);
            }
        }
    }

    static final class CloseIncompleteException extends IllegalStateException {
        private static final long serialVersionUID = 1L;

        CloseIncompleteException(String message) {
            super(message);
        }

        CloseIncompleteException(String message, Throwable cause) {
            super(message, cause);
        }
    }

    /**
     * One 5000ms new-drain budget. The monotonic origin is caller/attempt admission.
     * Remaining time is budget minus nanoTime elapsed, never a new per-resource
     * timeout. Only the existing bounded, non-overridable goodbye waits pause the
     * owner's clock; they retain their own original CLOSE_TIMEOUT allowance.
     * Joiners never pause their clock. Retry carries its remaining budget across
     * the old helper barrier into the new attempt.
     */
    static final class WaitBudget {
        private long remaining = TimeUnit.MILLISECONDS.toNanos(DNSConstants.CLOSE_TIMEOUT);
        private long origin = System.nanoTime();
        private boolean paused;

        long remainingNanos() {
            if (!paused) {
                long now = System.nanoTime();
                remaining = Math.max(0L, remaining - Math.max(0L, now - origin));
                origin = now;
            }
            return remaining;
        }

        void pauseForGoodbyeWait() {
            remainingNanos();
            paused = true;
        }

        void resumeAfterGoodbyeWait() {
            origin = System.nanoTime();
            paused = false;
        }

        void await(Object monitor, String obligation) throws InterruptedException {
            long nanos = remainingNanos();
            if (nanos == 0L) {
                throw new CloseIncompleteException("Timed out waiting for " + obligation);
            }
            TimeUnit.NANOSECONDS.timedWait(monitor, nanos);
        }

        void join(Thread thread, String obligation) throws InterruptedException {
            while (thread.isAlive()) {
                long nanos = remainingNanos();
                if (nanos == 0L) {
                    throw new CloseIncompleteException("Timed out waiting for " + obligation);
                }
                TimeUnit.NANOSECONDS.timedJoin(thread, nanos);
            }
        }
    }

    /** Read-only fixture observations; identities are never obtained by allocation. */
    static final class Snapshot {
        final boolean terminalRequested;
        final long attemptId;
        final Thread owner;
        final Thread helper;
        final boolean helperLaunchResolved;
        final boolean helperStarted;
        final boolean workComplete;
        final Throwable failure;
        final int joinedCallers;
        final int activeMutations;
        final int activeTasks;
        final int activeCallbacks;
        final int submissionsInFlight;
        final boolean recoveryMutationActive;
        final Thread recoveryWorker;
        final DNSTaskStarter retainedStarter;
        final ExecutorService executor;
        final int dnsListenerCount;
        final long socketPublications;
        final long normalTaskStarts;
        final List<MulticastSocket> ownedSockets;
        final List<Thread> socketListeners;

        Snapshot(JmDNSLifecycle life, DNSTaskStarter starter, ExecutorService executor, int listenerCount) {
            terminalRequested = life.terminalRequested;
            Attempt current = life.attempt;
            attemptId = current == null ? 0L : current.id;
            owner = current == null ? null : current.owner;
            helper = current == null || current.helper == null ? null : current.helper.thread;
            helperLaunchResolved = current == null || current.helper == null || current.helper.launchResolved;
            helperStarted = current != null && current.helper != null && current.helper.started;
            workComplete = current != null && current.outcome != null;
            failure = !workComplete ? null : current.outcome.failure;
            joinedCallers = current == null ? 0 : current.joinedCallers;
            activeMutations = life.mutations;
            activeTasks = life.tasks;
            activeCallbacks = life.callbacks;
            submissionsInFlight = life.submissions;
            recoveryMutationActive = life.recovery != null && life.recovery.mutating;
            recoveryWorker = life.recovery == null ? null : life.recovery.thread;
            retainedStarter = starter;
            this.executor = executor;
            dnsListenerCount = listenerCount;
            socketPublications = life.socketPublications;
            normalTaskStarts = life.normalTaskStarts;
            ownedSockets = Collections.unmodifiableList(new ArrayList<>(life.sockets));
            List<Thread> threads = new ArrayList<>();
            for (OwnedThread listener : life.listeners) {
                threads.add(listener.thread);
            }
            socketListeners = Collections.unmodifiableList(threads);
        }
    }
}
