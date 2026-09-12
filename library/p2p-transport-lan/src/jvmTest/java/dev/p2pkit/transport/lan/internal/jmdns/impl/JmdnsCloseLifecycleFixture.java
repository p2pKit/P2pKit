package dev.p2pkit.transport.lan.internal.jmdns.impl;

import java.io.IOException;
import java.lang.reflect.Field;
import java.net.DatagramPacket;
import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.MulticastSocket;
import java.net.NetworkInterface;
import java.net.NoRouteToHostException;
import java.net.StandardSocketOptions;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;
import java.util.function.BooleanSupplier;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import dev.p2pkit.transport.lan.internal.jmdns.ServiceEvent;
import dev.p2pkit.transport.lan.internal.jmdns.ServiceInfo;
import dev.p2pkit.transport.lan.internal.jmdns.ServiceTypeListener;
import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSConstants;
import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSRecordClass;
import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSRecordType;

/**
 * One real default-starter instance per child JVM. The launcher requires natural
 * exit in addition to these assertions: a PASS line cannot hide a surviving
 * non-daemon timer. Faults affect only the named send/cancel operation; no DNS
 * state, task, socket, executor, factory, or callback implementation is replaced.
 */
public final class JmdnsCloseLifecycleFixture {
    private static final long READY_MILLIS = 10_000;
    private static final long STEP_MILLIS = 5_000;
    private static final long JOIN_MILLIS = 1_000;
    private static final int RESPONDER_QUERY_ID = 0x410;
    private static final int LOCAL_QUERY_PORT = 45_002;
    private static final List<String> MODES = List.of(
            "control", "failed_recovery", "shared_close", "close_wins",
            "recovery_wins", "responder_close", "callback_executor", "cleanup_retry");
    // One fixture per child JVM. Initialize before constructor virtual dispatch
    // so an early native send failure cannot precede diagnostic ownership.
    private static final StartupTrace STARTUP = new StartupTrace();

    private JmdnsCloseLifecycleFixture() {
    }

    public static void main(String[] args) throws Throwable {
        String mode = args.length == 1 ? args[0] : "invalid";
        Fixture fixture = null;
        boolean ready = false;
        try {
            require(Runtime.version().feature() == 17, "jdk17_required");
            require(args.length == 1 && MODES.contains(mode), "unknown_fixture_mode");
            require(DNSTaskStarter.Factory.classDelegate() == null, "default_factory_required");
            Inet4Address address = localMulticastIpv4();
            FixtureDns dns = new FixtureDns(address, "close-fixture-" + UUID.randomUUID());
            fixture = new Fixture(mode, address, dns);
            fixture.captureOriginalResources();
            require(dns.waitForAnnounced(READY_MILLIS) && dns.isAnnounced(), "host_not_announced");
            ready = true;
            fixture.phase("ready");

            switch (mode) {
                case "control":
                    ordinaryClose(fixture);
                    break;
                case "failed_recovery":
                    failedRecovery(fixture);
                    break;
                case "shared_close":
                    sharedClose(fixture);
                    break;
                case "close_wins":
                    closeWins(fixture);
                    break;
                case "recovery_wins":
                    recoveryWins(fixture);
                    break;
                case "responder_close":
                    responderClose(fixture);
                    break;
                case "callback_executor":
                    callbackExecutor(fixture);
                    break;
                case "cleanup_retry":
                    cleanupRetry(fixture);
                    break;
                default:
                    throw new AssertionError("unknown_fixture_mode");
            }

            fixture.assertDisposed();
            for (CloseCall call : fixture.closeCalls) {
                require(call.thread.getState() == Thread.State.TERMINATED, "fixture_close_caller_retained");
            }
            fixture.control.checkAsyncFailure();
            System.out.println("PASS mode=" + mode);
        } catch (Throwable failure) {
            // The failure is recorded BEFORE any fixture assistance. Rescue can
            // never change the outcome or award natural-close success.
            System.out.println("FAIL mode=" + mode);
            System.out.flush();
            if (!ready) {
                try {
                    STARTUP.report();
                    if (fixture != null) {
                        fixture.reportStartupState();
                        StartupPrimitives.report(fixture);
                    }
                } catch (Throwable diagnosticFailure) {
                    // Diagnostics must not replace the original readiness
                    // failure or disclose native messages via suppressed errors.
                    System.out.println("startup diagnosticFailureClass=" + diagnosticFailure.getClass().getName());
                    StartupTrace.reportFrames("diagnostic_failure", diagnosticFailure.getStackTrace());
                }
            }
            if (fixture != null) {
                try {
                    fixture.rescueAfterFailure(failure);
                } catch (Throwable cleanupFailure) {
                    if (cleanupFailure != failure) {
                        failure.addSuppressed(cleanupFailure);
                    }
                }
            }
            throw failure;
        }
    }

    private static void ordinaryClose(Fixture f) throws Exception {
        f.announceService();
        f.control.observeGoodbyes = true;
        f.dns.close();
        f.assertGoodbyesUsedOriginalResources();
        f.assertDisposed();
        f.phase("original_resources_disposed_without_rescue");
    }

    private static void failedRecovery(Fixture f) throws Exception {
        CountDownLatch callback = new CountDownLatch(1);
        AtomicReference<Thread> callbackThread = new AtomicReference<>();
        AtomicInteger callbacks = new AtomicInteger();
        AtomicBoolean sameInstance = new AtomicBoolean();
        f.dns.setDelegate((origin, services) -> {
            sameInstance.set(origin == f.dns);
            callbackThread.set(Thread.currentThread());
            callbacks.incrementAndGet();
            callback.countDown();
        });

        // This is the approved mechanism: a real Canceler sends on the original
        // state timer, fails before advancing host state, and real recovery fails.
        f.control.failRecoverySend = true;
        f.dns.recover();
        await(callback, READY_MILLIS, "failed_recovery_delegate_missing");
        Thread recovery = callbackThread.get();
        require(recovery != null && sameInstance.get() && callbacks.get() == 1,
                "failed_recovery_delegate_identity");
        f.rememberThread(recovery);
        join(recovery, "failed_recovery_worker_retained");
        require(f.control.recoverySendFaults.get() == 1
                        && f.control.recoverySendThread.get() == f.stateTimer,
                "real_original_state_timer_failure_missing");
        require(f.dns.isCanceling() && !f.dns.isCanceled(), "failed_recovery_state_missing");
        require(f.originalSocket.isClosed() && f.dns.getSocket() == null,
                "recovery_should_already_have_closed_socket");
        require(f.generalTimer.isAlive() && f.stateTimer.isAlive(), "original_recovery_timers_missing");
        require(!f.snapshot().terminalRequested, "recovery_unexpectedly_admitted_terminal_close");
        f.phase("real_failed_recovery_socket_already_closed");

        f.dns.close();
        f.assertDisposed();
        require(callbacks.get() == 1, "failed_recovery_delegate_repeated");
        f.phase("failed_recovery_original_timers_disposed_without_rescue");
    }

    private static void sharedClose(Fixture f) throws Exception {
        Pause finalCancel = f.control.pause("final_state_timer_cancel");
        f.control.cancelPause = finalCancel;
        CloseCall owner = f.startClose("owner");
        finalCancel.awaitReached();
        Admission attempt = f.awaitAdmission(owner, true);
        require(f.stateTimer.isAlive() && !f.snapshot().workComplete, "owner_pause_not_before_disposal");

        CloseCall waiter = f.startClose("joined_waiter");
        require(f.awaitAdmission(waiter, false).id == attempt.id, "waiter_did_not_join_owner_attempt");
        assertWaitingOnAttempt(waiter);
        CloseCall interrupted = f.startClose("interrupted_waiter");
        require(f.awaitAdmission(interrupted, false).id == attempt.id,
                "interrupted_waiter_did_not_join_owner_attempt");
        assertWaitingOnAttempt(interrupted);
        require(f.snapshot().joinedCallers == 2, "both_waiters_not_observably_joined");

        interrupted.thread.interrupt();
        interrupted.awaitReturned(JOIN_MILLIS);
        require(!interrupted.succeeded && interrupted.failure != null && interrupted.interrupted,
                "waiter_interruption_not_reported_and_preserved");
        require(hasCause(interrupted.failure, InterruptedException.class), "waiter_interruption_cause_missing");
        JmDNSLifecycle.Snapshot held = f.snapshot();
        require(held.attemptId == attempt.id && held.owner == owner.thread && !held.workComplete,
                "interrupted_waiter_changed_owner_attempt");
        require(!waiter.returned() && !owner.returned(), "close_returned_while_final_disposal_held");
        f.phase("joined_waiter_interruption_left_owner_and_other_waiter_pending");

        finalCancel.release();
        owner.awaitSuccess();
        waiter.awaitSuccess();
        f.assertDisposed();
        require(f.snapshot().helper == null, "external_close_created_helper");
        f.dns.close();
        exerciseStaleHelpers(f, attempt.id);
        f.dns.close();
        require(f.snapshot().attemptId == attempt.id, "repeat_close_started_new_attempt");
        f.phase("repeat_and_stale_helpers_kept_original_disposed_resources");
    }

    private static void closeWins(Fixture f) throws Exception {
        long publicationsBeforeRecovery = f.snapshot().socketPublications;
        Pause candidatePause = f.control.pause("prepared_recovery_socket");
        f.control.candidatePause = candidatePause;
        f.dns.recover();
        candidatePause.awaitReached();

        MulticastSocket candidate = f.control.recoveryCandidate.get();
        JmDNSLifecycle.Snapshot prepared = f.snapshot();
        require(candidate != null && candidate != f.originalSocket && candidate.isBound() && !candidate.isClosed(),
                "real_prepared_candidate_missing");
        require(prepared.ownedSockets.contains(candidate) && f.dns.getSocket() != candidate,
                "candidate_not_privately_owned_before_publication");
        require(prepared.recoveryMutationActive && prepared.recoveryWorker == candidatePause.thread,
                "prepared_candidate_not_owned_by_real_recovery");
        require(prepared.socketPublications == publicationsBeforeRecovery, "candidate_already_published_at_pause");
        f.rememberSocket(candidate);
        f.rememberThread(candidatePause.thread);

        CloseCall owner = f.startClose("close_wins_owner");
        Admission attempt = f.awaitAdmission(owner, true);
        require(f.snapshot().terminalRequested && f.snapshot().attemptId == attempt.id,
                "close_not_admitted_before_candidate_release");
        require(!owner.returned() && !f.snapshot().workComplete, "close_ignored_recovery_mutation");
        candidatePause.release();
        owner.awaitSuccess();
        join(candidatePause.thread, "close_wins_recovery_worker_retained");
        require(candidate.isClosed(), "rejected_private_candidate_not_closed");
        require(f.snapshot().socketPublications == publicationsBeforeRecovery,
                "recovery_candidate_published_after_terminal_admission");
        require(f.control.recoveryProberCalls.get() == 0, "rejected_recovery_started_prober");
        f.assertDisposed();
        f.phase("close_won_at_actual_prepublication_fence");
    }

    private static void recoveryWins(Fixture f) throws Exception {
        long publicationsBeforeRecovery = f.snapshot().socketPublications;
        Pause proberPause = f.control.pause("published_recovery_start_prober");
        f.control.proberPause = proberPause;
        f.dns.recover();
        proberPause.awaitReached();

        MulticastSocket replacement = f.dns.getSocket();
        JmDNSLifecycle.Snapshot published = f.snapshot();
        require(replacement != null && replacement != f.originalSocket && !replacement.isClosed(),
                "replacement_socket_not_published");
        require(f.originalSocket.isClosed() && published.ownedSockets.contains(replacement),
                "recovery_socket_generations_not_owned");
        require(published.socketPublications == publicationsBeforeRecovery + 1,
                "replacement_publication_not_observed");
        require(published.recoveryMutationActive && published.recoveryWorker == proberPause.thread,
                "restart_pause_not_inside_recovery_mutation");
        require(published.socketListeners.stream().anyMatch(
                        thread -> thread != null && thread.isAlive() && !f.originalListeners.contains(thread)),
                "replacement_socket_listener_not_published");
        f.rememberSocket(replacement);
        f.rememberThread(proberPause.thread);

        CloseCall owner = f.startClose("recovery_wins_owner");
        f.awaitAdmission(owner, true);
        require(f.snapshot().terminalRequested && !owner.returned(), "close_not_admitted_during_restart_pause");
        proberPause.release();
        await(f.control.staleProberReturned, STEP_MILLIS, "stale_super_start_prober_not_reached");
        require(f.control.staleProberSawTerminal, "stale_super_start_prober_preceded_close_admission");
        require(f.control.staleProberStartsBefore == f.control.staleProberStartsAfter,
                "stale_super_start_prober_admitted_normal_task");
        owner.awaitSuccess();
        join(proberPause.thread, "recovery_wins_worker_retained");
        require(replacement.isClosed(), "published_replacement_socket_retained");
        require(f.snapshot().socketPublications == publicationsBeforeRecovery + 1,
                "close_or_stale_restart_opened_another_socket");
        f.assertDisposed();
        f.phase("published_restart_handed_both_generations_to_close");
    }

    private static void responderClose(Fixture f) throws Exception {
        ServiceInfoImpl service = f.announceService();
        f.control.observeGoodbyes = true;
        f.control.failResponderSend.set(true);

        // Parse a real DNS query and schedule the actual Responder on the default
        // general timer. Legacy-unicast preserves a nonzero query ID, unlike
        // multicast's mandatory zero, so another queued response cannot consume
        // this query's one fault. The query is never transmitted; its response
        // targets only the selected local address and fails before native send.
        DNSOutgoing query = new DNSOutgoing(DNSConstants.FLAGS_QR_QUERY, false);
        query.setId(RESPONDER_QUERY_ID);
        query.addQuestion(DNSQuestion.newQuestion(service.getQualifiedName(), DNSRecordType.TYPE_SRV,
                DNSRecordClass.CLASS_IN, DNSRecordClass.NOT_UNIQUE));
        byte[] bytes = query.data();
        DNSIncoming incoming = new DNSIncoming(new DatagramPacket(
                bytes, bytes.length, f.address, LOCAL_QUERY_PORT));
        require(incoming.getId() == RESPONDER_QUERY_ID && !incoming.isMulticast(),
                "real_query_discriminator_not_preserved");
        f.dns.startResponder(incoming, f.address, LOCAL_QUERY_PORT);
        await(f.control.responderSendFailed, STEP_MILLIS, "real_responder_send_failure_missing");
        awaitCondition(() -> {
            JmDNSLifecycle.Snapshot snapshot = f.snapshot();
            return snapshot.terminalRequested && snapshot.helper != null
                    && snapshot.helperLaunchResolved && snapshot.helperStarted;
        }, STEP_MILLIS, "responder_did_not_launch_owned_terminal_closer");

        JmDNSLifecycle.Snapshot admitted = f.snapshot();
        Thread helper = admitted.helper;
        require(helper != f.generalTimer && helper != f.stateTimer && helper == admitted.owner && !helper.isDaemon(),
                "responder_helper_not_distinct_owned_non_daemon_thread");
        require(f.control.nativeAdmissions.get() == 1 && f.control.responderSendFaults.get() == 1
                        && f.control.responderSendThread.get() == f.generalTimer,
                "responder_did_not_admit_exactly_one_native_attempt");
        require(f.closeCalls.isEmpty(), "external_close_initiated_responder_cleanup");
        f.rememberThread(helper);
        awaitCondition(() -> f.snapshot().workComplete, READY_MILLIS, "native_closer_did_not_finish_autonomously");
        join(helper, "native_closer_work_outcome_was_not_thread_exit");
        f.assertDisposed();
        f.assertGoodbyesUsedOriginalResources();
        f.phase("responder_autonomous_disposal_and_helper_exit_before_external_barrier");

        f.dns.close(); // Only a barrier/no-op: all native disposal was already observed above.
        JmDNSLifecycle.Snapshot barrier = f.snapshot();
        require(barrier.attemptId == admitted.attemptId && barrier.helper == helper && !helper.isAlive(),
                "late_external_barrier_replaced_native_attempt");
        require(f.control.nativeAdmissions.get() == 1, "native_request_spawned_another_owner");
    }

    private static void callbackExecutor(Fixture f) throws Exception {
        String type = uniqueType();
        CountDownLatch rejectedBefore = new CountDownLatch(1);
        CountDownLatch tryDuringClose = f.control.releaseLatch();
        CountDownLatch rejectedDuring = new CountDownLatch(1);
        CountDownLatch releaseCallback = f.control.releaseLatch();
        CountDownLatch callbackExited = new CountDownLatch(1);
        AtomicReference<Thread> callbackThread = new AtomicReference<>();
        AtomicInteger callbacks = new AtomicInteger();
        AtomicInteger rejections = new AtomicInteger();

        f.dns.addServiceTypeListener(new ServiceTypeListener() {
            @Override
            public void serviceTypeAdded(ServiceEvent event) {
                if (!type.equals(event.getType())) {
                    return;
                }
                callbacks.incrementAndGet();
                callbackThread.set(Thread.currentThread());
                try {
                    rejectBlockingCallbackClose(f.dns);
                    rejections.incrementAndGet();
                    JmDNSLifecycle.Snapshot before = f.snapshot();
                    require(!before.terminalRequested && before.attemptId == 0 && before.helper == null,
                            "unsupported_callback_close_admitted_terminal_intent");
                    rejectedBefore.countDown();
                    await(tryDuringClose, STEP_MILLIS, "external_close_not_released_to_callback");
                    JmDNSLifecycle.Snapshot external = f.snapshot();
                    require(external.terminalRequested && !external.workComplete, "external_attempt_missing_in_callback");
                    rejectBlockingCallbackClose(f.dns);
                    rejections.incrementAndGet();
                    JmDNSLifecycle.Snapshot after = f.snapshot();
                    require(after.attemptId == external.attemptId && after.owner == external.owner
                                    && after.helper == external.helper && !after.workComplete,
                            "callback_rejection_changed_external_attempt");
                    rejectedDuring.countDown();
                    await(releaseCallback, STEP_MILLIS, "callback_was_not_released");
                } catch (Throwable failure) {
                    f.control.asyncFailure.compareAndSet(null, failure);
                } finally {
                    rejectedBefore.countDown();
                    rejectedDuring.countDown();
                    callbackExited.countDown();
                }
            }

            @Override
            public void subTypeForServiceTypeAdded(ServiceEvent event) {
                // This fixture registers a type, not a subtype.
            }
        });
        require(f.dns.registerServiceType(type), "unique_callback_type_not_registered");
        await(rejectedBefore, STEP_MILLIS, "real_executor_callback_missing");
        f.control.checkAsyncFailure();
        Thread callback = callbackThread.get();
        require(callback != null && callback != Thread.currentThread()
                        && callback != f.generalTimer && callback != f.stateTimer,
                "type_callback_not_on_real_executor_worker");
        require(rejections.get() == 1 && !f.snapshot().terminalRequested && f.snapshot().activeCallbacks > 0,
                "first_callback_close_rejection_missing");
        f.rememberThread(callback);

        CloseCall owner = f.startClose("callback_owner");
        Admission attempt = f.awaitAdmission(owner, true);
        tryDuringClose.countDown();
        await(rejectedDuring, STEP_MILLIS, "callback_did_not_try_close_during_external_attempt");
        f.control.checkAsyncFailure();
        require(rejections.get() == 2 && f.snapshot().attemptId == attempt.id,
                "second_callback_close_rejection_missing");
        awaitCondition(() -> f.executor.isShutdown() || owner.returned(), READY_MILLIS,
                "external_close_did_not_reach_executor_shutdown");
        awaitCondition(() -> owner.returned() || waitingForActualCallbackDrain(f, owner), STEP_MILLIS,
                "external_close_did_not_wait_at_actual_callback_or_executor_drain");
        require(!owner.returned() && !f.snapshot().workComplete && !f.executor.isTerminated()
                        && f.snapshot().activeCallbacks > 0 && callbackExited.getCount() == 1,
                "external_close_completed_while_real_callback_still_running");
        f.phase("populated_executor_blocks_external_success_after_both_callback_rejections");

        releaseCallback.countDown();
        await(callbackExited, JOIN_MILLIS, "callback_body_retained");
        owner.awaitSuccess();
        join(callback, "callback_executor_thread_retained");
        f.control.checkAsyncFailure();
        require(callbacks.get() == 1 && rejections.get() == 2, "unexpected_type_callback_count");
        f.assertDisposed();
    }

    private static void cleanupRetry(Fixture f) throws Exception {
        Pause finalCancel = f.control.pause("faulted_final_state_timer_cancel");
        f.control.cancelPause = finalCancel;
        f.control.failStateCancelOnce.set(true);
        CloseCall owner = f.startClose("failed_attempt_owner");
        finalCancel.awaitReached();
        Admission attempt = f.awaitAdmission(owner, true);
        CloseCall waiter = f.startClose("old_attempt_waiter");
        require(f.awaitAdmission(waiter, false).id == attempt.id, "failure_waiter_joined_wrong_attempt");
        assertWaitingOnAttempt(waiter);
        Pause consumeOldOutcome = f.control.pause("old_attempt_outcome_consumption");
        f.control.outcomeConsumer = waiter.thread;
        f.control.outcomePause = consumeOldOutcome;

        finalCancel.release();
        owner.awaitReturned(READY_MILLIS);
        consumeOldOutcome.awaitReached();
        require(f.control.outcomeAttemptId == attempt.id, "old_waiter_paused_on_wrong_attempt_outcome");
        JmDNSLifecycle.Snapshot failed = f.snapshot();
        require(!owner.succeeded && owner.failure != null && failed.workComplete && failed.failure != null,
                "failed_resource_cleanup_reported_success");
        require(failed.attemptId == attempt.id && failed.terminalRequested && !f.dns.isClosed(),
                "failed_disposal_published_terminal_success_or_reopened_admission");
        require(f.control.stateCancelFaults.get() == 1 && f.stateTimer.isAlive(),
                "fault_did_not_precede_real_original_state_timer_cancel");
        require(hasIdentityCause(owner.failure, failed.failure)
                        && hasIdentityCause(failed.failure, f.control.stateCancelFailure),
                "owner_lost_immutable_attempt_failure");
        join(f.generalTimer, "independent_general_timer_disposal_not_attempted");
        require(f.originalSocket.isClosed() && f.dns.getSocket() == null && failed.ownedSockets.isEmpty(),
                "independent_socket_disposal_not_attempted");
        require(f.executor.isShutdown() && f.executor.awaitTermination(JOIN_MILLIS, TimeUnit.MILLISECONDS),
                "independent_executor_disposal_not_attempted");
        for (Thread listener : f.originalListeners) {
            join(listener, "independent_listener_disposal_not_attempted");
        }
        require(failed.retainedStarter == f.starter && f.factoryEntries.get(f.dns) == f.starter,
                "failed_timer_lost_its_original_starter_ownership");
        require(!waiter.returned(), "old_waiter_not_held_before_outcome_consumption");
        f.phase("failed_attempt_kept_original_state_timer_and_disposed_independent_resources");

        CloseCall retry = f.startClose("explicit_retry_owner");
        Admission retryAttempt = f.awaitAdmission(retry, true);
        require(retryAttempt.id > attempt.id, "explicit_retry_not_a_new_attempt");
        retry.awaitSuccess();
        f.assertDisposed();
        JmDNSLifecycle.Snapshot retried = f.snapshot();
        require(retried.attemptId == retryAttempt.id && retried.failure == null
                        && retried.retainedStarter == f.starter,
                "retry_did_not_dispose_retained_original_resources");
        require(retried.socketPublications == failed.socketPublications
                        && retried.normalTaskStarts == failed.normalTaskStarts,
                "retry_reopened_normal_work_or_resources");

        consumeOldOutcome.release();
        waiter.awaitReturned(JOIN_MILLIS);
        require(!waiter.succeeded && waiter.failure != null && !waiter.interrupted
                        && hasIdentityCause(waiter.failure, failed.failure),
                "old_waiter_observed_successful_retry_instead_of_its_failed_attempt");
        require(f.snapshot().attemptId == retryAttempt.id && f.snapshot().failure == null,
                "old_waiter_rewrote_retry_outcome");
        f.phase("successful_retry_cannot_rewrite_old_joined_failure");
    }

    private static void exerciseStaleHelpers(Fixture f, long attemptId) throws Exception {
        JmDNSLifecycle.Snapshot before = f.snapshot();
        ServiceInfoImpl stale = newService(uniqueType());
        allowTerminalRejection(() -> f.dns.startServiceInfoResolver(stale));
        allowTerminalRejection(() -> f.starter.startServiceInfoResolver(stale));
        allowTerminalRejection(f.dns::startProber);
        allowTerminalRejection(f.starter::startProber);
        allowTerminalRejection(f.dns::startAnnouncer);
        allowTerminalRejection(f.dns::startRenewer);
        allowTerminalRejection(f.dns::startReaper);
        allowTerminalRejection(f.dns::startTypeResolver);
        allowTerminalRejection(() -> f.dns.startServiceResolver(stale.getType()));
        allowTerminalRejection(f.dns::recover);
        f.dns.purgeTimer();
        f.dns.purgeStateTimer();
        JmDNSLifecycle.Snapshot after = f.snapshot();
        require(after.terminalRequested && after.workComplete && after.failure == null && after.attemptId == attemptId,
                "stale_helper_changed_terminal_attempt");
        require(after.retainedStarter == f.starter && after.executor == f.executor
                        && f.factoryEntries.get(f.dns) == null,
                "stale_helper_replaced_or_reinstalled_starter");
        require(after.dnsListenerCount == before.dnsListenerCount,
                "stale_resolver_constructor_inserted_listener");
        require(after.normalTaskStarts == before.normalTaskStarts
                        && after.socketPublications == before.socketPublications,
                "stale_helper_admitted_constructor_or_opened_socket");
        f.assertDisposed();
    }

    private static void rejectBlockingCallbackClose(FixtureDns dns) {
        Throwable rejection = null;
        try {
            dns.close();
        } catch (Throwable failure) {
            rejection = failure;
        }
        require(rejection instanceof IllegalStateException
                        && !(rejection instanceof JmDNSLifecycle.CloseIncompleteException),
                "dependent_blocking_close_not_explicitly_rejected_before_waiting");
    }

    private static void allowTerminalRejection(Runnable operation) {
        try {
            operation.run();
        } catch (IllegalStateException expected) {
            // A terminal helper may reject or do nothing. Neither may construct
            // new native work or leave a resolver listener behind (checked above).
        }
    }

    private static final class FixtureDns extends JmDNSImpl {
        // Null during constructor virtual dispatch; test controls are armed only
        // after the real constructor has installed its starter and resources.
        volatile Controls control;

        FixtureDns(InetAddress address, String name) throws IOException {
            super(address, name);
        }

        @Override
        public void send(DNSOutgoing outgoing) throws IOException {
            Controls c = control;
            if (c == null) {
                observedNativeSend(outgoing);
                return;
            }
            if (c.failRecoverySend && Thread.currentThread() == c.stateTimer) {
                c.recoverySendFaults.incrementAndGet();
                c.recoverySendThread.set(Thread.currentThread());
                throw new IOException("fixture_injected_recovery_send_failure");
            }
            if (Thread.currentThread() == c.generalTimer && outgoing.isResponse() && !outgoing.isMulticast()
                    && outgoing.getId() == RESPONDER_QUERY_ID
                    && outgoing.getAllAnswers().stream().anyMatch(record -> record.getName().equals(c.serviceName))
                    && c.failResponderSend.compareAndSet(true, false)) {
                c.responderSendFaults.incrementAndGet();
                c.responderSendThread.set(Thread.currentThread());
                c.responderSendFailed.countDown();
                throw new IOException("fixture_injected_general_timer_responder_send_failure");
            }

            int hostGoodbyes = 0;
            int serviceGoodbyes = 0;
            if (c.observeGoodbyes) {
                for (DNSRecord record : outgoing.getAllAnswers()) {
                    if (record.getTTL() == 0) {
                        if (record.getName().equals(c.hostName)) {
                            hostGoodbyes++;
                        }
                        if (record.getName().equals(c.serviceName)) {
                            serviceGoodbyes++;
                        }
                    }
                }
            }
            if (hostGoodbyes + serviceGoodbyes > 0) {
                if (Thread.currentThread() != c.stateTimer || !c.stateTimer.isAlive()
                        || getSocket() != c.originalSocket || c.originalSocket.isClosed()) {
                    c.asyncFailure.compareAndSet(null, new AssertionError("goodbye_did_not_use_original_live_resources"));
                }
            }
            observedNativeSend(outgoing);
            // Count only records which actually reached the native send with a
            // usable socket/state timer, never inferred peer delivery.
            c.hostGoodbyes.addAndGet(hostGoodbyes);
            c.serviceGoodbyes.addAndGet(serviceGoodbyes);
        }

        private void observedNativeSend(DNSOutgoing outgoing) throws IOException {
            Boolean ipv4Mdns = null;
            try {
                InetSocketAddress explicit = outgoing.getDestination();
                InetAddress destination = explicit == null ? getGroup() : explicit.getAddress();
                int port = explicit == null ? DNSConstants.MDNS_PORT : explicit.getPort();
                if (destination != null) {
                    ipv4Mdns = !outgoing.isEmpty() && port == DNSConstants.MDNS_PORT
                            && Arrays.equals(destination.getAddress(), new byte[] {(byte) 224, 0, 0, (byte) 251});
                }
            } catch (Throwable ignored) {
                // Observation failure must not change the real send operation.
            }
            STARTUP.sendCalls.incrementAndGet();
            try {
                super.send(outgoing);
                STARTUP.sendReturns.incrementAndGet();
            } catch (IOException | RuntimeException | Error failure) {
                try {
                    STARTUP.firstSendFailure.compareAndSet(null, new SendFailure(failure, ipv4Mdns));
                } catch (Throwable ignored) {
                    // Even failure-record allocation must not replace the send failure.
                }
                throw failure;
            }
        }

        @Override
        public void recover() {
            STARTUP.recoveryCalls.incrementAndGet();
            super.recover();
        }

        @Override
        public void startAnnouncer() {
            STARTUP.announcerCalls.incrementAndGet();
            super.startAnnouncer();
        }

        @Override
        public void cancelStateTimer() {
            Controls c = control;
            if (c != null) {
                c.enter(c.cancelPause);
                if (c.failStateCancelOnce.compareAndSet(true, false)) {
                    c.stateCancelFaults.incrementAndGet();
                    throw c.stateCancelFailure;
                }
            }
            super.cancelStateTimer();
        }

        @Override
        void beforeRecoverySocketPublication(MulticastSocket candidate) {
            Controls c = control;
            if (c != null) {
                c.recoveryCandidate.set(candidate);
                c.enter(c.candidatePause);
            }
        }

        @Override
        public void startProber() {
            STARTUP.proberCalls.incrementAndGet();
            Controls c = control;
            if (c != null && lifecycleSnapshot().recoveryWorker == Thread.currentThread()) {
                c.recoveryProberCalls.incrementAndGet();
                Pause pause = c.proberPause;
                if (pause != null) {
                    c.enter(pause);
                    JmDNSLifecycle.Snapshot before = lifecycleSnapshot();
                    c.staleProberSawTerminal = before.terminalRequested;
                    c.staleProberStartsBefore = before.normalTaskStarts;
                    try {
                        super.startProber();
                    } finally {
                        c.staleProberStartsAfter = lifecycleSnapshot().normalTaskStarts;
                        c.staleProberReturned.countDown();
                    }
                    return;
                }
            }
            super.startProber();
        }

        @Override
        void afterCloseAttemptAdmission(long attemptId, boolean owner) {
            Controls c = control;
            if (c != null) {
                c.admissions.put(Thread.currentThread(), new Admission(attemptId, owner));
                if (owner && Thread.currentThread() == c.generalTimer) {
                    c.nativeAdmissions.incrementAndGet();
                }
            }
        }

        @Override
        void beforeCloseOutcomeConsumption(long attemptId) {
            Controls c = control;
            if (c != null && Thread.currentThread() == c.outcomeConsumer) {
                c.outcomeAttemptId = attemptId;
                c.enter(c.outcomePause);
            }
        }
    }

    private static final class StartupTrace {
        final long started = System.nanoTime();
        final AtomicInteger sendCalls = new AtomicInteger();
        final AtomicInteger sendReturns = new AtomicInteger();
        final AtomicInteger recoveryCalls = new AtomicInteger();
        final AtomicInteger proberCalls = new AtomicInteger();
        final AtomicInteger announcerCalls = new AtomicInteger();
        final AtomicReference<SendFailure> firstSendFailure = new AtomicReference<>();

        void report() {
            System.out.println("startup elapsedMillis="
                    + TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - started)
                    + " sendCalls=" + sendCalls.get() + " sendReturns=" + sendReturns.get()
                    + " recoveryCalls=" + recoveryCalls.get() + " proberCalls=" + proberCalls.get()
                    + " announcerCalls=" + announcerCalls.get());
            SendFailure failure = firstSendFailure.get();
            if (failure != null) {
                System.out.println("startup firstSendFailureClass=" + failure.cause.getClass().getName()
                        + " firstSendDestinationIpv4Mdns=" + known(failure.ipv4Mdns));
                reportFrames("send_failure", failure.cause.getStackTrace());
            }
        }

        static void reportThread(String role, Thread thread) {
            System.out.println("startup threadRole=" + role + " state="
                    + (thread == null ? "NOT_CAPTURED" : thread.getState())
                    + " alive=" + (thread != null && thread.isAlive()));
            if (thread != null) {
                reportFrames(role, thread.getStackTrace());
            }
        }

        private static void reportFrames(String role, StackTraceElement[] frames) {
            for (int index = 0; index < Math.min(frames.length, 8); index++) {
                // No exception messages, thread names, file paths, addresses,
                // host/service identities, or packet contents in diagnostics.
                System.out.println("startup frameRole=" + role + " frame="
                        + frames[index].getClassName() + "." + frames[index].getMethodName());
            }
        }
    }

    private record SendFailure(Throwable cause, Boolean ipv4Mdns) {
    }

    private record InterfaceIdentity(int index, String name) {
        static InterfaceIdentity capture(InterfaceQuery query) {
            try {
                NetworkInterface network = query.get();
                if (network != null && network.getIndex() > 0 && network.getName() != null) {
                    return new InterfaceIdentity(network.getIndex(), network.getName());
                }
            } catch (Throwable ignored) {
                // An unavailable accessor is UNKNOWN, not a readiness failure.
            }
            return null;
        }
    }

    private interface InterfaceQuery {
        NetworkInterface get() throws IOException;
    }

    private static final class StartupNetwork {
        private static final int ROUTE_OUTPUT_LIMIT = 8_192;
        private static final Pattern ROUTE_INTERFACE = Pattern.compile("^\\s*interface:\\s*(\\S+)\\s*$");
        private static final Pattern ROUTE_FLAGS = Pattern.compile("^\\s*flags:\\s*<([A-Z0-9_,]+)>\\s*$");
        InterfaceIdentity selected;
        InterfaceIdentity host;
        InterfaceIdentity socket;

        void report() {
            System.out.println("startup interfaceSnapshot=BEFORE_WAIT selectedKnown=" + (selected != null)
                    + " hostKnown=" + (host != null) + " socketKnown=" + (socket != null)
                    + " selectedHostMatch=" + same(selected, host)
                    + " selectedSocketMatch=" + same(selected, socket)
                    + " hostSocketMatch=" + same(host, socket));
            if (!"Mac OS X".equals(System.getProperty("os.name"))) {
                return;
            }
            SendFailure firstSend = STARTUP.firstSendFailure.get();
            if (firstSend == null || !Boolean.TRUE.equals(firstSend.ipv4Mdns)) {
                System.out.println("startup route queryStarted=false reason=FIRST_SEND_DESTINATION_NOT_MATCHED");
                return;
            }
            // Read-only, selected-interface scope only: a differing default
            // route would not disprove an explicitly configured multicast NIC.
            // This observes POST-failure state, not packet delivery or policy
            // at the original send. No route/interface/address text is emitted.
            if (selected == null || !selected.name.matches("[A-Za-z0-9_.:-]{1,64}")) {
                System.out.println("startup route queryStarted=false reason=SELECTED_INTERFACE_UNKNOWN");
                return;
            }
            Process process = null;
            boolean interrupted = false;
            try {
                ProcessBuilder builder = new ProcessBuilder("/sbin/route", "-n", "get", "-inet", "-ifscope",
                        selected.name, "224.0.0.251").redirectErrorStream(true);
                builder.environment().put("LC_ALL", "C");
                process = builder.start();
                process.getOutputStream().close();
                boolean completed = process.waitFor(2, TimeUnit.SECONDS);
                System.out.println("startup route observation=POST_FAILURE scope=SELECTED_IPV4_MDNS"
                        + " queryStarted=true queryCompleted=" + completed
                        + " exitZero=" + (completed ? process.exitValue() == 0 : "UNKNOWN"));
                if (completed && process.exitValue() == 0) {
                    byte[] output = process.getInputStream().readNBytes(ROUTE_OUTPUT_LIMIT + 1);
                    System.out.println("startup route outputWithinBound=" + (output.length <= ROUTE_OUTPUT_LIMIT));
                    if (output.length <= ROUTE_OUTPUT_LIMIT) {
                        reportRouteDetails(new String(output, StandardCharsets.UTF_8));
                    }
                }
            } catch (InterruptedException failure) {
                interrupted = true;
                System.out.println("startup route queryFailureClass=java.lang.InterruptedException");
            } catch (Throwable failure) {
                System.out.println("startup route queryFailureClass=" + failure.getClass().getName());
            } finally {
                if (process != null) {
                    if (process.isAlive()) {
                        process.destroyForcibly();
                        try {
                            process.waitFor(1, TimeUnit.SECONDS);
                        } catch (InterruptedException failure) {
                            interrupted = true;
                        }
                    }
                    System.out.println("startup route processReaped=" + !process.isAlive());
                    try {
                        process.getInputStream().close();
                        process.getErrorStream().close();
                        process.getOutputStream().close();
                    } catch (IOException ignored) {
                        // Original readiness failure is preserved; no raw text.
                    }
                }
                if (interrupted) {
                    Thread.currentThread().interrupt();
                }
            }
        }

        private void reportRouteDetails(String output) {
            List<String> interfaces = new ArrayList<>();
            List<String> flags = new ArrayList<>();
            for (String line : output.split("\\R")) {
                Matcher routeInterface = ROUTE_INTERFACE.matcher(line);
                if (routeInterface.matches()) {
                    interfaces.add(routeInterface.group(1));
                }
                Matcher routeFlags = ROUTE_FLAGS.matcher(line);
                if (routeFlags.matches()) {
                    flags.add(routeFlags.group(1));
                }
            }
            System.out.println("startup route interfaceParsed=" + (interfaces.size() == 1)
                    + " selectedInterfaceMatch="
                    + (interfaces.size() == 1 ? selected.name.equals(interfaces.get(0)) : "UNKNOWN")
                    + " flagsParsed=" + (flags.size() == 1));
            if (flags.size() == 1) {
                List<String> values = Arrays.asList(flags.get(0).split(","));
                for (String flag : List.of("UP", "REJECT", "BLACKHOLE", "GATEWAY", "IFSCOPE")) {
                    System.out.println("startup routeFlag=" + flag + " present=" + values.contains(flag));
                }
            }
        }

        private static String same(InterfaceIdentity first, InterfaceIdentity second) {
            return first == null || second == null ? "UNKNOWN" : Boolean.toString(first.equals(second));
        }
    }

    private static String known(Boolean value) {
        return value == null ? "UNKNOWN" : value.toString();
    }

    private static final class StartupPrimitives {
        // Fixed 42-byte, zero-ID A/IN query for p2pkit-audit-probe.local.; no real host/service data.
        private static final String QUERY_HEX = "000000000001000000000000"
                + "127032706b69742d61756469742d70726f6265056c6f63616c0000010001";
        private static final Pattern NATIVE_REPORT = Pattern.compile(
                "P2PKIT_PRIMITIVE_V1\\|(ADMISSION|IDENTITY|SOCKET|REUSE|BIND|INTERFACE|JOIN|TTL|SEND)"
                        + "\\|(KERNEL_ACCEPTED|FAIL)\\|([A-Za-z][A-Za-z0-9_]{0,63})"
                        + "\\|(UNKNOWN|-?[0-9]{1,10})\\|([0-9]{1,3})\\|(true|false|NOT_CREATED)"
                        + "\\|([A-Za-z][A-Za-z0-9_]{0,63})\\n");
        private static final String PYTHON = """
                import socket, struct, sys
                stage, result, failure, error, sent = "ADMISSION", "FAIL", "NONE", "UNKNOWN", 0
                sock, closed, close_failure = None, "NOT_CREATED", "NONE"
                try:
                    frame = sys.stdin.buffer.read(74)
                    if not 10 <= len(frame) <= 73 or len(frame) != 9 + frame[8]:
                        raise ValueError()
                    index, address, name = struct.unpack("!I", frame[:4])[0], frame[4:8], frame[9:].decode("ascii")
                    stage = "IDENTITY"
                    if socket.if_nametoindex(name) != index or socket.if_indextoname(index) != name:
                        raise ValueError()
                    stage = "SOCKET"
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    stage = "REUSE"
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    # Darwin's JDK UDP reuse-address path also enables reuse-port before bind.
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                    if (not sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR)
                            or not sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT)):
                        raise ValueError()
                    stage = "BIND"
                    sock.bind(("", 5353))
                    stage = "INTERFACE"
                    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, address)
                    if sock.getsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, 4) != address:
                        raise ValueError()
                    stage = "JOIN"
                    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                                    socket.inet_aton("224.0.0.251") + address)
                    stage = "TTL"
                    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)
                    stage = "SEND"
                    sent = sock.sendto(bytes.fromhex("%s"), ("224.0.0.251", 5353))
                    if sent != 42:
                        raise ValueError()
                    result = "KERNEL_ACCEPTED"
                except BaseException as cause:
                    failure = type(cause).__name__
                    error = cause.errno if isinstance(cause, OSError) and cause.errno is not None else "UNKNOWN"
                finally:
                    if sock is not None:
                        try:
                            sock.close()
                        except BaseException as cause:
                            close_failure = type(cause).__name__
                        closed = str(sock.fileno() == -1).lower()
                print("|".join(map(str, ("P2PKIT_PRIMITIVE_V1", stage, result, failure, error,
                                         sent, closed, close_failure))))
                """.formatted(QUERY_HEX);

        static void report(Fixture fixture) throws IOException {
            // Only the audit workflow opts in. Normal JUnit/product operation needs no Python.
            if (!"true".equals(System.getProperty("p2pkit.audit.jmdnsStartupPrimitives"))) {
                return;
            }
            StartupNetwork snapshot = fixture.startupNetwork;
            SendFailure first = STARTUP.firstSendFailure.get();
            if (!"Mac OS X".equals(System.getProperty("os.name")) || !"control".equals(fixture.mode)
                    || Thread.currentThread().isInterrupted() || first == null
                    || !(first.cause instanceof NoRouteToHostException) || !Boolean.TRUE.equals(first.ipv4Mdns)
                    || snapshot.selected == null || !snapshot.selected.equals(snapshot.host)
                    || !snapshot.selected.equals(snapshot.socket)
                    || !snapshot.selected.name.matches("[A-Za-z0-9_.:-]{1,64}")) {
                System.out.println("startup primitivePair attempted=false reason=CONTEXT_OR_CAPTURE_NOT_MATCHED");
                return;
            }
            Path python = Path.of(System.getProperty("p2pkit.audit.pythonExecutable", ""));
            if (!python.isAbsolute() || !Files.isRegularFile(python) || !Files.isExecutable(python)
                    || !python.equals(python.toRealPath())) {
                System.out.println("startup primitivePair attempted=false reason=CANONICAL_INTERPRETER_REQUIRED");
                return;
            }
            NetworkInterface network = matchedNetwork(fixture);
            if (network == null) {
                System.out.println("startup primitivePair attempted=false reason=CURRENT_INTERFACE_NOT_MATCHED");
                return;
            }
            // Post-failure observations only. Kernel acceptance is not delivery, readiness,
            // interoperability, a policy diagnosis, or a reason to change the original FAIL.
            System.out.println("startup primitivePair observation=POST_FAILURE scope=CAPTURED_IPV4_MDNS"
                    + " interpretation=KERNEL_ACCEPTANCE_ONLY");
            jdkSend(network);
            if (matchedNetwork(fixture) == null) {
                System.out.println("startup primitive=PYTHON_IPV4 attempted=false reason=CURRENT_INTERFACE_NOT_MATCHED");
                return;
            }
            nativeSend(python, snapshot.selected, fixture.address);
        }

        private static NetworkInterface matchedNetwork(Fixture fixture) throws IOException {
            NetworkInterface network = NetworkInterface.getByInetAddress(fixture.address);
            return usable(network, fixture.address) && fixture.startupNetwork.selected.equals(
                    InterfaceIdentity.capture(() -> network)) ? network : null;
        }

        private static void jdkSend(NetworkInterface network) {
            MulticastSocket socket = null;
            String stage = "SOCKET", result = "FAIL", failureClass = "NONE", closeFailure = "NONE";
            int sent = 0;
            try {
                // Ordinary JDK multicast reuse/family defaults, matching the product's macOS bind/options.
                socket = new MulticastSocket(null);
                stage = "REUSE";
                System.out.println("startup primitive=JDK_MULTICAST reuseAddress=" + socket.getReuseAddress()
                        + " reusePort=" + socket.getOption(StandardSocketOptions.SO_REUSEPORT));
                stage = "BIND";
                socket.bind(new InetSocketAddress(DNSConstants.MDNS_PORT));
                stage = "INTERFACE";
                socket.setNetworkInterface(network);
                InetAddress group = InetAddress.getByAddress(new byte[] {(byte) 224, 0, 0, (byte) 251});
                stage = "JOIN";
                socket.joinGroup(new InetSocketAddress(group, DNSConstants.MDNS_PORT), network);
                stage = "TTL";
                socket.setTimeToLive(255);
                byte[] query = HexFormat.of().parseHex(QUERY_HEX);
                stage = "SEND";
                socket.send(new DatagramPacket(query, query.length, group, DNSConstants.MDNS_PORT));
                sent = query.length;
                result = "KERNEL_ACCEPTED";
            } catch (Throwable failure) {
                failureClass = failure.getClass().getName();
            } finally {
                if (socket != null) {
                    try {
                        socket.close();
                    } catch (Throwable failure) {
                        closeFailure = failure.getClass().getName();
                    }
                }
                System.out.println("startup primitive=JDK_MULTICAST stage=" + stage + " result=" + result
                        + " failureClass=" + failureClass + " errno=UNKNOWN sentBytes=" + sent
                        + " socketClosed=" + (socket == null ? "NOT_CREATED" : socket.isClosed())
                        + " closeFailureClass=" + closeFailure);
            }
        }

        private static void nativeSend(Path python, InterfaceIdentity network, Inet4Address address) {
            Process process = null;
            boolean interrupted = false;
            try {
                // No shell, PATH search, site packages, bytecode cache, address argv or raw stderr forwarding.
                process = new ProcessBuilder(python.toString(), "-I", "-S", "-B", "-c", PYTHON)
                        .redirectError(ProcessBuilder.Redirect.DISCARD).start();
                byte[] name = network.name.getBytes(StandardCharsets.US_ASCII);
                byte[] frame = ByteBuffer.allocate(9 + name.length).putInt(network.index)
                        .put(address.getAddress()).put((byte) name.length).put(name).array();
                process.getOutputStream().write(frame);
                process.getOutputStream().close();
                boolean completed = process.waitFor(2, TimeUnit.SECONDS);
                System.out.println("startup primitive=PYTHON_IPV4 processCompleted=" + completed
                        + " exitZero=" + (completed ? process.exitValue() == 0 : "UNKNOWN"));
                if (completed && process.exitValue() == 0) {
                    byte[] output = process.getInputStream().readNBytes(513);
                    Matcher report = NATIVE_REPORT.matcher(new String(output, StandardCharsets.US_ASCII));
                    boolean valid = output.length <= 512 && report.matches()
                            && Integer.parseInt(report.group(5)) <= 42
                            && (!"KERNEL_ACCEPTED".equals(report.group(2)) || ("SEND".equals(report.group(1))
                            && "NONE".equals(report.group(3)) && "UNKNOWN".equals(report.group(4))
                            && "42".equals(report.group(5))));
                    System.out.println("startup primitive=PYTHON_IPV4 reportValid=" + valid);
                    if (valid) {
                        System.out.println("startup primitive=PYTHON_IPV4 stage=" + report.group(1)
                                + " result=" + report.group(2) + " failureClass=" + report.group(3)
                                + " errno=" + report.group(4) + " sentBytes=" + report.group(5)
                                + " socketClosed=" + report.group(6) + " closeFailureClass=" + report.group(7));
                    }
                }
            } catch (InterruptedException failure) {
                interrupted = true;
                System.out.println("startup primitive=PYTHON_IPV4 processFailureClass=java.lang.InterruptedException");
            } catch (Throwable failure) {
                System.out.println("startup primitive=PYTHON_IPV4 processFailureClass=" + failure.getClass().getName());
            } finally {
                if (process != null) {
                    if (process.isAlive()) {
                        process.destroyForcibly();
                        try {
                            process.waitFor(1, TimeUnit.SECONDS);
                        } catch (InterruptedException failure) {
                            interrupted = true;
                        }
                    }
                    System.out.println("startup primitive=PYTHON_IPV4 processReaped=" + !process.isAlive());
                    try {
                        process.getInputStream().close();
                        process.getErrorStream().close();
                        process.getOutputStream().close();
                    } catch (IOException ignored) {
                        // Preserve the original readiness failure; never emit native text.
                    }
                }
                if (interrupted) {
                    Thread.currentThread().interrupt();
                }
            }
        }
    }

    private static final class Controls {
        final AtomicReference<Throwable> asyncFailure = new AtomicReference<>();
        final Map<Thread, Admission> admissions = new ConcurrentHashMap<>();
        final List<Pause> pauses = new CopyOnWriteArrayList<>();
        final List<CountDownLatch> releaseLatches = new CopyOnWriteArrayList<>();
        final AtomicInteger recoverySendFaults = new AtomicInteger();
        final AtomicReference<Thread> recoverySendThread = new AtomicReference<>();
        final AtomicBoolean failResponderSend = new AtomicBoolean();
        final AtomicInteger responderSendFaults = new AtomicInteger();
        final AtomicReference<Thread> responderSendThread = new AtomicReference<>();
        final CountDownLatch responderSendFailed = new CountDownLatch(1);
        final AtomicInteger nativeAdmissions = new AtomicInteger();
        final AtomicInteger hostGoodbyes = new AtomicInteger();
        final AtomicInteger serviceGoodbyes = new AtomicInteger();
        final AtomicBoolean failStateCancelOnce = new AtomicBoolean();
        final AtomicInteger stateCancelFaults = new AtomicInteger();
        final IllegalStateException stateCancelFailure = new IllegalStateException("fixture_state_timer_cancel_fault");
        final AtomicReference<MulticastSocket> recoveryCandidate = new AtomicReference<>();
        final AtomicInteger recoveryProberCalls = new AtomicInteger();
        final CountDownLatch staleProberReturned = new CountDownLatch(1);
        volatile Thread generalTimer;
        volatile Thread stateTimer;
        volatile MulticastSocket originalSocket;
        volatile String hostName;
        volatile String serviceName;
        volatile boolean failRecoverySend;
        volatile boolean observeGoodbyes;
        volatile Pause cancelPause;
        volatile Pause candidatePause;
        volatile Pause proberPause;
        volatile Pause outcomePause;
        volatile Thread outcomeConsumer;
        volatile long outcomeAttemptId;
        volatile boolean staleProberSawTerminal;
        volatile long staleProberStartsBefore;
        volatile long staleProberStartsAfter;

        Pause pause(String name) {
            Pause pause = new Pause(name);
            pauses.add(pause);
            return pause;
        }

        CountDownLatch releaseLatch() {
            CountDownLatch latch = new CountDownLatch(1);
            releaseLatches.add(latch);
            return latch;
        }

        void enter(Pause pause) {
            if (pause != null) {
                try {
                    pause.enter();
                } catch (Throwable failure) {
                    asyncFailure.compareAndSet(null, failure);
                    throw failure;
                }
            }
        }

        void checkAsyncFailure() {
            Throwable failure = asyncFailure.get();
            if (failure != null) {
                throw new AssertionError("fixture_async_observation_failed", failure);
            }
        }

        void releaseAll() {
            pauses.forEach(Pause::release);
            releaseLatches.forEach(CountDownLatch::countDown);
        }
    }

    private static final class Fixture {
        final String mode;
        final Inet4Address address;
        final FixtureDns dns;
        final Controls control = new Controls();
        final StartupNetwork startupNetwork = new StartupNetwork();
        final List<CloseCall> closeCalls = new ArrayList<>();
        final List<Thread> originalListeners = new ArrayList<>();
        final Set<Thread> observedThreads = Collections.newSetFromMap(new IdentityHashMap<>());
        final Set<MulticastSocket> observedSockets = Collections.newSetFromMap(new IdentityHashMap<>());
        DNSTaskStarter.Factory factory;
        Map<?, ?> factoryEntries;
        DNSTaskStarter starter;
        ExecutorService executor;
        MulticastSocket originalSocket;
        Thread generalTimer;
        Thread stateTimer;

        Fixture(String mode, Inet4Address address, FixtureDns dns) {
            this.mode = mode;
            this.address = address;
            this.dns = dns;
            dns.control = control;
        }

        void captureOriginalResources() throws Exception {
            JmDNSLifecycle.Snapshot initial = snapshot();
            starter = initial.retainedStarter;
            executor = initial.executor;
            originalSocket = dns.getSocket();
            startupNetwork.selected = InterfaceIdentity.capture(() -> NetworkInterface.getByInetAddress(address));
            startupNetwork.host = InterfaceIdentity.capture(() -> dns.getLocalHost().getInterface());
            startupNetwork.socket = InterfaceIdentity.capture(() -> originalSocket == null
                    ? null : originalSocket.getNetworkInterface());
            factory = DNSTaskStarter.Factory.getInstance();
            Field entries = DNSTaskStarter.Factory.class.getDeclaredField("_instances");
            require(entries.trySetAccessible(), "factory_read_only_capture_unavailable");
            factoryEntries = (Map<?, ?>) entries.get(factory);
            // No getStarter call, even for assertions after close. Inspect only
            // the already-installed owner; this never manufactures fresh timers.
            require(starter != null && starter.getClass() == DNSTaskStarter.DNSTaskStarterImpl.class
                            && factoryEntries.get(dns) == starter,
                    "real_default_installed_starter_required");
            generalTimer = captureTimer("JmDNS(" + dns.getName() + ").Timer");
            stateTimer = captureTimer("JmDNS(" + dns.getName() + ").State.Timer");
            require(generalTimer.isDaemon() && !stateTimer.isDaemon() && originalSocket != null
                            && !originalSocket.isClosed() && executor != null && !executor.isShutdown(),
                    "original_live_resources_missing");
            require(!initial.terminalRequested && initial.attemptId == 0 && initial.socketPublications == 1,
                    "fresh_instance_lifetime_not_open");
            originalListeners.addAll(initial.socketListeners);
            require(originalListeners.size() == 1 && originalListeners.get(0).isAlive(),
                    "real_original_socket_listener_missing");
            control.generalTimer = generalTimer;
            control.stateTimer = stateTimer;
            control.originalSocket = originalSocket;
            control.hostName = dns.getLocalHost().getName();
            rememberSocket(originalSocket);
        }

        ServiceInfoImpl announceService() throws Exception {
            ServiceInfoImpl service = newService(uniqueType());
            dns.registerService(service);
            require(service.waitForAnnounced(READY_MILLIS) && service.isAnnounced() && dns.isAnnounced(),
                    "real_service_not_announced");
            control.serviceName = service.getQualifiedName();
            return service;
        }

        synchronized JmDNSLifecycle.Snapshot snapshot() {
            JmDNSLifecycle.Snapshot snapshot = dns.lifecycleSnapshot();
            observedSockets.addAll(snapshot.ownedSockets);
            observedThreads.addAll(snapshot.socketListeners);
            if (snapshot.recoveryWorker != null) {
                observedThreads.add(snapshot.recoveryWorker);
            }
            if (snapshot.helper != null && snapshot.helperLaunchResolved && snapshot.helperStarted) {
                observedThreads.add(snapshot.helper);
            }
            return snapshot;
        }

        synchronized void rememberSocket(MulticastSocket socket) {
            observedSockets.add(socket);
        }

        synchronized void rememberThread(Thread thread) {
            observedThreads.add(thread);
        }

        CloseCall startClose(String label) {
            CloseCall call = new CloseCall(dns, label);
            closeCalls.add(call);
            call.thread.start();
            return call;
        }

        Admission awaitAdmission(CloseCall call, boolean owner) throws Exception {
            awaitCondition(() -> control.admissions.containsKey(call.thread) || call.returned(), STEP_MILLIS,
                    "close_attempt_admission_not_observed");
            Admission admission = control.admissions.get(call.thread);
            require(admission != null && admission.id > 0 && admission.owner == owner,
                    "wrong_close_attempt_admission");
            JmDNSLifecycle.Snapshot snapshot = snapshot();
            require(snapshot.terminalRequested && snapshot.attemptId == admission.id,
                    "admission_did_not_reference_current_attempt");
            if (owner) {
                require(snapshot.owner == call.thread && snapshot.helper == null,
                        "external_caller_did_not_own_its_cleanup");
            }
            return admission;
        }

        void assertGoodbyesUsedOriginalResources() {
            control.checkAsyncFailure();
            require(control.hostGoodbyes.get() > 0 && control.serviceGoodbyes.get() > 0,
                    "real_host_and_announced_service_ttl_zero_sends_missing");
        }

        void assertDisposed() throws Exception {
            JmDNSLifecycle.Snapshot snapshot = snapshot();
            require(snapshot.terminalRequested && snapshot.workComplete && snapshot.failure == null,
                    "close_did_not_establish_successful_terminal_outcome");
            require(snapshot.retainedStarter == starter && snapshot.executor == executor,
                    "close_replaced_original_starter_or_executor");
            require(snapshot.helper == null || (snapshot.helperLaunchResolved && snapshot.helperStarted),
                    "helper_launch_unresolved_or_unstarted");
            // Passive joins only: cancellation assistance is forbidden on PASS.
            join(generalTimer, "original_general_timer_retained");
            join(stateTimer, "original_non_daemon_state_timer_retained");
            List<Thread> threads;
            List<MulticastSocket> sockets;
            synchronized (this) {
                threads = new ArrayList<>(observedThreads);
                sockets = new ArrayList<>(observedSockets);
            }
            for (Thread thread : threads) {
                join(thread, "owned_native_worker_retained");
            }
            for (MulticastSocket socket : sockets) {
                require(socket.isClosed(), "owned_socket_generation_retained");
            }
            require(originalSocket.isClosed() && dns.getSocket() == null && snapshot.ownedSockets.isEmpty(),
                    "owned_or_current_socket_retained");
            require(executor.isShutdown() && executor.awaitTermination(JOIN_MILLIS, TimeUnit.MILLISECONDS),
                    "same_original_executor_not_terminated");
            require(snapshot.activeMutations == 0 && snapshot.activeTasks == 0 && snapshot.activeCallbacks == 0
                            && snapshot.submissionsInFlight == 0 && !snapshot.recoveryMutationActive,
                    "terminal_outcome_preceded_owned_work_drain");
            require(factoryEntries.get(dns) == null, "disposed_starter_still_registered");
            for (Thread thread : Thread.getAllStackTraces().keySet()) {
                require(!thread.getName().equals(generalTimer.getName())
                                && !thread.getName().equals(stateTimer.getName()),
                        "replacement_timer_survived_close");
            }
            control.checkAsyncFailure();
        }

        void phase(String phase) {
            // Deliberately omit addresses, interface names, host/service names,
            // packet contents, and private filesystem paths from fixture output.
            System.out.println("phase=" + phase + " mode=" + mode);
        }

        void reportStartupState() throws IOException {
            JmDNSLifecycle.Snapshot current = dns.lifecycleSnapshot();
            MulticastSocket socket = dns.getSocket();
            System.out.println("startup probing=" + dns.isProbing() + " announcing=" + dns.isAnnouncing()
                    + " announced=" + dns.isAnnounced() + " canceling=" + dns.isCanceling()
                    + " canceled=" + dns.isCanceled() + " closing=" + dns.isClosing() + " closed=" + dns.isClosed());
            System.out.println("startup terminal=" + current.terminalRequested + " attempt=" + current.attemptId
                    + " mutations=" + current.activeMutations + " tasks=" + current.activeTasks
                    + " recoveryMutation=" + current.recoveryMutationActive
                    + " socketPublications=" + current.socketPublications
                    + " originalSocketClosed=" + (originalSocket != null && originalSocket.isClosed())
                    + " currentSocketAbsent=" + (socket == null)
                    + " currentSocketClosed=" + (socket != null && socket.isClosed()));
            StartupTrace.reportThread("general_timer", generalTimer);
            StartupTrace.reportThread("state_timer", stateTimer);
            startupNetwork.report();
            NetworkInterface network = NetworkInterface.getByInetAddress(address);
            System.out.println("startup explicitAddress=" + (System.getenv("P2PKIT_JMDNS_FIXTURE_IPV4") != null)
                    + " linkLocal=" + address.isLinkLocalAddress()
                    + " virtualInterface=" + (network != null && network.isVirtual())
                    + " pointToPoint=" + (network != null && network.isPointToPoint()));
        }

        void rescueAfterFailure(Throwable originalFailure) {
            phase("fixture_rescue_begin");
            control.releaseAll();
            control.failRecoverySend = false;
            control.failResponderSend.set(false);
            control.failStateCancelOnce.set(false);
            // A best-effort terminal fence is allowed ONLY after FAIL, including
            // when an assertion failed before the intended first close. Its
            // result cannot replace the original assertion or become a PASS.
            rescueStep(originalFailure, dns::close);
            JmDNSLifecycle.Snapshot current = snapshot();
            DNSTaskStarter retained = starter != null ? starter : current.retainedStarter;
            if (retained != null) {
                rescueStep(originalFailure, retained::cancelTimer);
                rescueStep(originalFailure, retained::cancelStateTimer);
            }
            MulticastSocket candidate = control.recoveryCandidate.get();
            if (candidate != null) {
                rememberSocket(candidate);
            }
            MulticastSocket socket = dns.getSocket();
            if (socket != null) {
                rememberSocket(socket);
            }
            List<MulticastSocket> sockets;
            synchronized (this) {
                sockets = new ArrayList<>(observedSockets);
            }
            for (MulticastSocket owned : sockets) {
                rescueStep(originalFailure, owned::close);
            }
            ExecutorService retainedExecutor = executor != null ? executor : current.executor;
            if (retainedExecutor != null) {
                rescueStep(originalFailure, retainedExecutor::shutdownNow);
            }
            if (factory != null) {
                rescueStep(originalFailure, () -> factory.disposeStarter(dns));
            }
            for (CloseCall call : closeCalls) {
                rescueStep(originalFailure, () -> join(call.thread, "fixture_close_caller_survived_rescue"));
            }
            if (generalTimer != null) {
                rescueStep(originalFailure, () -> join(generalTimer, "general_timer_survived_rescue"));
            }
            if (stateTimer != null) {
                rescueStep(originalFailure, () -> join(stateTimer, "state_timer_survived_rescue"));
            }
            phase("fixture_rescue_finished_original_failure_preserved");
        }
    }

    private static final class Admission {
        final long id;
        final boolean owner;

        Admission(long id, boolean owner) {
            this.id = id;
            this.owner = owner;
        }
    }

    private static final class CloseCall {
        final Thread thread;
        final CountDownLatch done = new CountDownLatch(1);
        volatile boolean succeeded;
        volatile boolean interrupted;
        volatile Throwable failure;

        CloseCall(FixtureDns dns, String label) {
            thread = new Thread(() -> {
                try {
                    dns.close();
                    succeeded = true;
                } catch (Throwable thrown) {
                    failure = thrown;
                } finally {
                    interrupted = Thread.currentThread().isInterrupted();
                    done.countDown();
                }
            }, "fixture-close-" + label);
        }

        boolean returned() {
            return done.getCount() == 0;
        }

        void awaitReturned(long millis) throws InterruptedException {
            await(done, millis, "external_close_caller_did_not_return");
            join(thread, "external_close_caller_thread_retained");
        }

        void awaitSuccess() throws InterruptedException {
            awaitReturned(READY_MILLIS);
            if (!succeeded || failure != null || interrupted) {
                throw new AssertionError("external_close_did_not_succeed", failure);
            }
        }
    }

    private static final class Pause {
        final String name;
        final CountDownLatch reached = new CountDownLatch(1);
        final CountDownLatch released = new CountDownLatch(1);
        final AtomicBoolean used = new AtomicBoolean();
        volatile Thread thread;

        Pause(String name) {
            this.name = name;
        }

        void enter() {
            if (!used.compareAndSet(false, true)) {
                return;
            }
            thread = Thread.currentThread();
            reached.countDown();
            try {
                await(released, STEP_MILLIS, name + "_not_released");
            } catch (InterruptedException failure) {
                Thread.currentThread().interrupt();
                throw new AssertionError(name + "_interrupted", failure);
            }
        }

        void awaitReached() throws InterruptedException {
            await(reached, READY_MILLIS, name + "_not_reached");
        }

        void release() {
            released.countDown();
        }
    }

    private static void assertWaitingOnAttempt(CloseCall call) throws Exception {
        // Admission is observed separately from scheduling this thread. Wait for
        // its real blocking wait or an incorrect return, rather than sleep and
        // hope the caller has run. No fixture pause is installed on these calls.
        awaitCondition(() -> call.returned() || call.thread.getState() == Thread.State.WAITING
                        || call.thread.getState() == Thread.State.TIMED_WAITING,
                STEP_MILLIS, "admitted_external_caller_did_not_wait");
        require(!call.returned(), "external_caller_returned_before_owned_work_finished");
    }

    private static boolean waitingForActualCallbackDrain(Fixture f, CloseCall owner) {
        JmDNSLifecycle.Snapshot snapshot = f.snapshot();
        if (!f.executor.isShutdown() || snapshot.activeCallbacks == 0 || snapshot.activeMutations != 0
                || snapshot.activeTasks != 0 || snapshot.submissionsInFlight != 0) {
            return false;
        }
        Thread.State state = owner.thread.getState();
        if (state != Thread.State.WAITING && state != Thread.State.TIMED_WAITING) {
            return false;
        }
        StackTraceElement[] stack = owner.thread.getStackTrace();
        boolean executorDrain = false;
        boolean realExecutorWait = false;
        for (int index = 0; index < stack.length; index++) {
            StackTraceElement frame = stack[index];
            if (frame.getClassName().equals(JmDNSLifecycle.WaitBudget.class.getName())
                    && frame.getMethodName().equals("await") && index + 1 < stack.length) {
                StackTraceElement caller = stack[index + 1];
                if (caller.getClassName().equals(JmDNSImpl.class.getName())
                        && caller.getMethodName().equals("disposeOwnedResources")) {
                    // The original executor has been shut down, so the earlier
                    // mutation-handoff wait is past. All other admitted-work
                    // counts are zero: this direct wait is on held callbacks.
                    // Nested socket/listener/recovery joins do not match it.
                    return true;
                }
            }
            executorDrain |= frame.getClassName().equals(JmDNSImpl.class.getName())
                    && frame.getMethodName().equals("awaitExecutor");
            realExecutorWait |= frame.getClassName().equals("java.util.concurrent.ThreadPoolExecutor")
                    && frame.getMethodName().equals("awaitTermination");
        }
        // Either actual callback accounting or the same real executor's drain
        // is a returning-close barrier; an unrelated WAITING frame is not.
        return executorDrain && realExecutorWait;
    }

    private static ServiceInfoImpl newService(String type) {
        return (ServiceInfoImpl) ServiceInfo.create(type, "close-service-" + UUID.randomUUID(),
                45_001, 0, 0, "fixture=close-lifecycle");
    }

    private static String uniqueType() {
        return "_cl" + UUID.randomUUID().toString().replace("-", "").substring(0, 10) + "._tcp.local.";
    }

    private static Inet4Address localMulticastIpv4() throws Exception {
        String explicit = System.getenv("P2PKIT_JMDNS_FIXTURE_IPV4");
        if (explicit != null) {
            String[] parts = explicit.split("\\.", -1);
            require(parts.length == 4, "fixture_address_must_be_literal_ipv4");
            byte[] bytes = new byte[4];
            for (int index = 0; index < bytes.length; index++) {
                require(parts[index].matches("[0-9]{1,3}"), "fixture_address_must_be_literal_ipv4");
                int octet = Integer.parseInt(parts[index]);
                require(octet <= 255, "fixture_address_octet_out_of_range");
                bytes[index] = (byte) octet;
            }
            Inet4Address address = localAddressWithoutReverseLookup(bytes);
            NetworkInterface network = NetworkInterface.getByInetAddress(address);
            require(usable(network, address), "explicit_fixture_address_not_local_up_multicast_ipv4");
            return address;
        }

        List<NetworkInterface> networks = Collections.list(NetworkInterface.getNetworkInterfaces());
        networks.sort(Comparator.comparingInt(NetworkInterface::getIndex).thenComparing(NetworkInterface::getName));
        for (NetworkInterface network : networks) {
            for (InetAddress candidate : Collections.list(network.getInetAddresses())) {
                if (candidate instanceof Inet4Address && usable(network, candidate)) {
                    return localAddressWithoutReverseLookup(candidate.getAddress());
                }
            }
        }
        throw new AssertionError("local_up_multicast_ipv4_required_set_P2PKIT_JMDNS_FIXTURE_IPV4_if_needed");
    }

    private static Inet4Address localAddressWithoutReverseLookup(byte[] bytes) throws IOException {
        // HostInfo also reads InetAddress.getHostName when given an explicit
        // JmDNS name. Supply a synthetic label with the real local address bytes
        // so the fixture never performs a reverse lookup against an external DNS.
        return (Inet4Address) InetAddress.getByAddress("close-fixture-address", bytes);
    }

    private static boolean usable(NetworkInterface network, InetAddress address) throws IOException {
        return network != null && network.isUp() && network.supportsMulticast()
                && address instanceof Inet4Address && !address.isAnyLocalAddress()
                && !address.isLoopbackAddress() && !address.isMulticastAddress();
    }

    private static Thread captureTimer(String name) {
        List<Thread> matches = new ArrayList<>();
        for (Thread thread : Thread.getAllStackTraces().keySet()) {
            if (name.equals(thread.getName())) {
                matches.add(thread);
            }
        }
        require(matches.size() == 1, "timer_identity_ambiguous_or_absent");
        Thread timer = matches.get(0);
        require(timer.isAlive() && timer.getClass().getName().equals("java.util.TimerThread"),
                "real_original_timer_thread_required");
        return timer;
    }

    private static void join(Thread thread, String failure) throws InterruptedException {
        require(thread != null && thread != Thread.currentThread(), "invalid_passive_join_target");
        thread.join(JOIN_MILLIS);
        // NEW is also !isAlive(): only an actual terminated identity proves a
        // launched worker exited, independently of lifecycle launch metadata.
        require(!thread.isAlive() && thread.getState() == Thread.State.TERMINATED, failure);
    }

    private static void await(CountDownLatch latch, long millis, String failure) throws InterruptedException {
        require(latch.await(millis, TimeUnit.MILLISECONDS), failure);
    }

    private static void awaitCondition(BooleanSupplier condition, long millis, String failure)
            throws InterruptedException {
        long deadline = System.nanoTime() + TimeUnit.MILLISECONDS.toNanos(millis);
        while (!condition.getAsBoolean()) {
            require(System.nanoTime() < deadline, failure);
            TimeUnit.MILLISECONDS.sleep(1);
        }
    }

    private static boolean hasCause(Throwable throwable, Class<? extends Throwable> type) {
        for (Throwable current = throwable; current != null; current = current.getCause()) {
            if (type.isInstance(current)) {
                return true;
            }
        }
        return false;
    }

    private static boolean hasIdentityCause(Throwable throwable, Throwable expected) {
        if (throwable == expected) {
            return true;
        }
        if (throwable == null) {
            return false;
        }
        if (hasIdentityCause(throwable.getCause(), expected)) {
            return true;
        }
        for (Throwable suppressed : throwable.getSuppressed()) {
            if (hasIdentityCause(suppressed, expected)) {
                return true;
            }
        }
        return false;
    }

    private interface RescueAction {
        void run() throws Exception;
    }

    private static void rescueStep(Throwable originalFailure, RescueAction action) {
        try {
            action.run();
        } catch (Throwable failure) {
            if (failure != originalFailure) {
                originalFailure.addSuppressed(failure);
            }
        }
    }

    private static void require(boolean condition, String message) {
        if (!condition) {
            throw new AssertionError(message);
        }
    }
}
