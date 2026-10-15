/* Candidate-only closed-envelope/math decisions. No application launch, process
 * control, native admission or product execution. "--clock" exposes only the
 * read-only shared clock for private cross-language comparison, not gate proof. */
#define P2PKIT_APPLE_CI_CANDIDATE 1
#define main terminal_candidate_main_not_invoked_by_fixture
#include "../../diagnostics/apple-terminal-context.m"
#undef main
#include <stdio.h>
#include <string.h>
#include <float.h>

static unsigned controls = 0;
static int check(BOOL passed, const char *name) {
    controls++;
    if (!passed) fprintf(stderr, "FAIL: apple-ci-envelope/%s\n", name);
    return passed ? 0 : 1;
}

static NSDictionary *envelope(void) {
    return @{@"schema":@1, @"scope":@"ORDINARY_CI_APPLE_TERMINAL_CANDIDATE", @"clock":ciClock,
        @"source":@{@"commit":@"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", @"tree":@"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},
        @"profile":@"platform-full", @"runId":@123, @"runAttempt":@1,
        @"jobId":@"cccccccccccccccccccccccccccccccc", @"invocationId":@"dddddddddddddddddddddddddddddddd",
        @"bootSession":@"12345678-1234-1234-1234-123456789abc", @"boundAtMonotonicNs":@(100 * ciSecond),
        @"boundAtWallNs":@(10000 * ciSecond), @"boundSampleSpanNs":@0, @"productCutoffMonotonicNs":@(120 * ciSecond),
        @"executorEndMonotonicNs":@(150 * ciSecond), @"nativeFinalizerEndMonotonicNs":@(180 * ciSecond),
        @"finalizationCutoffMonotonicNs":@(190 * ciSecond), @"jobCutoffMonotonicNs":@(200 * ciSecond)};
}

static NSDictionary *configuration(void) {
    return @{@"source":envelope()[@"source"], @"ciProfile":@"platform-full",
        @"environment":@{@"GITHUB_SHA":envelope()[@"source"][@"commit"], @"GITHUB_RUN_ID":@"123",
            @"GITHUB_RUN_ATTEMPT":@"1", @"RUNNER_TRACKING_ID":@"fixture-only", @"PATH":@"/usr/bin:/bin"}};
}

static NSDictionary *observation(uint64_t mono, uint64_t wall) {
    return @{@"clock":ciClock, @"bootSession":envelope()[@"bootSession"], @"monotonicNs":@(mono),
        @"wallNs":@(wall), @"sampleSpanNs":@0};
}

static NSDictionary *changing(NSDictionary *base, NSString *key, id value) {
    NSMutableDictionary *copy = [base mutableCopy];
    if (value) copy[key] = value;
    else [copy removeObjectForKey:key];
    return copy;
}

/* Compare seconds * 1e9 with ns EXACTLY, without a floating reference or an
 * integer-to-double conversion. Apple ARM long double is only binary64, so it
 * can mask the same defect as the implementation. Decode the IEEE754 rational
 * into a significand and power of two, then compare scaled integers. */
static int exactSecondsComparison(double seconds, uint64_t ns) {
    _Static_assert(sizeof(double) == sizeof(uint64_t) && DBL_MANT_DIG == 53 && DBL_MAX_EXP == 1024,
        "Controls require IEEE754 binary64");
    uint64_t bits;
    memcpy(&bits, &seconds, sizeof(bits));
    uint64_t exponent = (bits >> 52) & 0x7ff, significand = bits & UINT64_C(0x000fffffffffffff);
    if (exponent == 0x7ff || (bits >> 63)) return 2; /* Invalid for nonnegative timestamps. */
    int shift = exponent ? (int)exponent - 1023 - 52 : -1074;
    if (exponent) significand |= UINT64_C(1) << 52;
    __uint128_t left = (__uint128_t)significand * UINT64_C(1000000000), right = ns;
    const __uint128_t maximum = ~(__uint128_t)0;
    if (!left) return ns ? -1 : 0;
    if (shift >= 0) {
        if (shift >= 128 || left > (maximum >> shift)) return 1;
        left <<= shift;
    } else if (right) {
        if (-shift >= 128 || right > (maximum >> -shift)) return -1;
        right <<= -shift;
    }
    return left < right ? -1 : left > right ? 1 : 0;
}

static BOOL conversionBounds(uint64_t ns) {
    int low = exactSecondsComparison(ciDeadlineSeconds(ns), ns);
    int high = exactSecondsComparison(ciNowSeconds(ns), ns);
    return (low == -1 || low == 0) && (high == 0 || high == 1);
}

static BOOL conversionMatrix(void) {
    /* Exact-rational comparison at integer and second boundaries, not an
     * empirical floating tolerance. The proof of direction is in the helper. */
    for (int bit = 0; bit < 63; bit++) {
        uint64_t value = UINT64_C(1) << bit;
        if (!conversionBounds(value - 1) || !conversionBounds(value) || !conversionBounds(value + 1)) return NO;
    }
    const uint64_t remainders[] = {0, 1, 2, 499999999, 500000000, 500000001, 999999998, 999999999};
    for (int bit = 0; bit < 34; bit++) {
        uint64_t quotient = UINT64_C(1) << bit;
        for (NSUInteger i = 0; i < sizeof(remainders) / sizeof(remainders[0]); i++) {
            uint64_t value = quotient * ciSecond + remainders[i];
            if (value <= INT64_MAX && !conversionBounds(value)) return NO;
        }
    }
    uint64_t state = UINT64_C(0x8d741b25c397ef61);
    for (int i = 0; i < 10000; i++) {
        state ^= state << 13; state ^= state >> 7; state ^= state << 17;
        if (!conversionBounds(state & INT64_MAX)) return NO;
    }
    return YES;
}

static int decisions(void) {
    int failures = 0;
    NSDictionary *base = envelope(), *config = configuration();
    BOOL (^valid)(NSDictionary *) = ^BOOL(NSDictionary *value) {
        return ciEnvelopeValid(value, config, @"fixture-only", @"/usr/bin:/bin");
    };
    failures += check(valid(base), "closed-envelope");
    for (NSString *key in base) failures += check(!valid(changing(base, key, nil)), "missing-envelope-key");
    failures += check(!valid(changing(base, @"extra", @YES)), "unknown-envelope-key");
    for (NSString *key in @[@"schema", @"runId", @"runAttempt", @"boundAtMonotonicNs", @"boundAtWallNs", @"boundSampleSpanNs",
            @"productCutoffMonotonicNs", @"executorEndMonotonicNs", @"nativeFinalizerEndMonotonicNs",
            @"finalizationCutoffMonotonicNs", @"jobCutoffMonotonicNs"]) {
        for (id invalid in @[@YES, @1.5, @(-1), @(UINT64_MAX), @"100", NSNull.null])
            failures += check(!valid(changing(base, key, invalid)), "non-integer-envelope");
    }
    NSArray *changes = @[
        @[@"schema", @2], @[@"clock", @"UPTIME"], @[@"scope", @"PRODUCT_PASS"], @[@"source", @{}],
        @[@"profile", @"platform-narrow"], @[@"profile", @"consumers-complete"],
        @[@"runId", @124], @[@"runAttempt", @2], @[@"runId", @0], @[@"runAttempt", @0],
        @[@"jobId", @"123"], @[@"invocationId", @"00000000000000000000000000000000"],
        @[@"bootSession", @"00000000-0000-0000-0000-000000000000"],
        @[@"bootSession", @"12345678-1234-1234-1234-123456789ABc"], @[@"boundAtWallNs", @0],
        @[@"boundSampleSpanNs", @50000001],
        @[@"boundAtMonotonicNs", base[@"productCutoffMonotonicNs"]],
        @[@"productCutoffMonotonicNs", base[@"executorEndMonotonicNs"]],
        @[@"nativeFinalizerEndMonotonicNs", @(180 * ciSecond - 1)],
        @[@"nativeFinalizerEndMonotonicNs", base[@"executorEndMonotonicNs"]],
        @[@"finalizationCutoffMonotonicNs", base[@"nativeFinalizerEndMonotonicNs"]],
        @[@"finalizationCutoffMonotonicNs", @(201 * ciSecond)],
        @[@"jobCutoffMonotonicNs", @(3700 * ciSecond + 1)]
    ];
    for (NSArray *change in changes) failures += check(!valid(changing(base, change[0], change[1])), "envelope-refusal");
    failures += check(valid(changing(base, @"jobCutoffMonotonicNs", @(3700 * ciSecond))), "original-one-hour-edge");
    failures += check(valid(changing(base, @"finalizationCutoffMonotonicNs", base[@"jobCutoffMonotonicNs"])), "outer-cutoff-equality");
    failures += check(ciEnvelopeValid(changing(base, @"profile", @"consumers-complete"),
        changing(config, @"ciProfile", @"consumers-complete"), @"fixture-only", @"/usr/bin:/bin"), "complete-consumers-profile");
    for (NSString *value in @[@"", @"changed", @"fixture-only\n"])
        failures += check(!ciEnvelopeValid(base, config, value, @"/usr/bin:/bin"), "tracking-continuity");
    for (NSString *value in @[@"", @"/bin:/usr/bin", @"/usr/bin:relative", @"/usr/bin:\n/bin"])
        failures += check(!ciEnvelopeValid(base, config, @"fixture-only", value), "path-continuity");
    for (NSString *key in @[@"GITHUB_SHA", @"GITHUB_RUN_ID", @"GITHUB_RUN_ATTEMPT", @"RUNNER_TRACKING_ID", @"PATH"])
        failures += check(!ciEnvelopeValid(base, changing(config, @"environment", changing(config[@"environment"], key, @"changed")),
            @"fixture-only", @"/usr/bin:/bin"), "environment-binding");
    failures += check(!ciEnvelopeValid(base, config, nil, @"/usr/bin:/bin"), "tracking-absent");
    failures += check(!ciEnvelopeValid(base, config, @"fixture-only", nil), "path-absent");

    NSDictionary *now = observation(110 * ciSecond, 10010 * ciSecond);
    uint64_t product = 120 * ciSecond, executor = 150 * ciSecond;
    failures += check(ciWaitDecision(base, now, product, NO) == 0, "wait-before-product");
    failures += check(ciWaitDecision(base, now, product, YES) == 1, "bounded-completion");
    failures += check(ciWaitDecision(base, now, 110 * ciSecond, YES) == -1, "completion-at-expiry-refused");
    failures += check(ciWaitDecision(base, now, 0, YES) == -1, "zero-cutoff-refused");
    failures += check(ciWaitDecision(base, now, UINT64_MAX, YES) == -1, "overflow-cutoff-refused");
    failures += check(ciWaitDecision(base, observation(125 * ciSecond, 10025 * ciSecond), product, YES) == -1,
        "product-cutoff-preserved");
    failures += check(ciWaitDecision(base, observation(125 * ciSecond, 10025 * ciSecond), executor, YES) == 1,
        "executor-reap-after-product");
    failures += check(ciWaitDecision(base, observation(executor, 10050 * ciSecond), executor, YES) == -1,
        "executor-expiry-refused");
    failures += check(ciProgress(base, observation(110 * ciSecond, 10011 * ciSecond)), "one-second-divergence-bound");
    failures += check(!ciProgress(base, observation(110 * ciSecond, 10011 * ciSecond + 1)), "sleep-divergence-refused");
    failures += check(!ciProgress(base, observation(110 * ciSecond, 10009 * ciSecond - 1)), "wall-lag-refused");
    failures += check(!ciProgress(changing(base, @"boundSampleSpanNs", @1), observation(110 * ciSecond, 10011 * ciSecond)),
        "anchor-span-charged-at-positive-drift");
    failures += check(!ciProgress(base, changing(observation(110 * ciSecond, 10009 * ciSecond), @"sampleSpanNs", @1)),
        "current-span-charged-at-negative-drift");
    failures += check(ciProgress(changing(base, @"boundSampleSpanNs", @50000000),
        observation(110 * ciSecond, 10011 * ciSecond - 50000000)), "anchor-span-within-fixed-margin");
    failures += check(ciProgress(base, changing(observation(110 * ciSecond, 10009 * ciSecond + 50000000), @"sampleSpanNs", @50000000)),
        "current-span-within-fixed-margin");
    failures += check(!ciProgress(base, observation(99 * ciSecond, 10000 * ciSecond)), "monotonic-reversal-refused");
    failures += check(!ciProgress(base, observation(100 * ciSecond, 9999 * ciSecond)), "wall-reversal-refused");
    failures += check(!ciProgress(base, changing(now, @"bootSession", @"22345678-1234-1234-1234-123456789abc")), "changed-boot-refused");
    failures += check(!ciProgress(base, changing(now, @"bootSession", nil)), "unknown-boot-refused");
    failures += check(!ciProgress(base, changing(now, @"clock", @"UPTIME")), "wrong-clock-refused");
    failures += check(!ciProgress(base, changing(now, @"sampleSpanNs", @50000001)), "unbounded-sample-refused");
    failures += check(ciWaitDecision(base, changing(now, @"sampleSpanNs", @50000000), 110 * ciSecond + 50000000, YES) == -1,
        "sample-crosses-cutoff-refused");
    failures += check(!ciProgress(base, changing(observation(INT64_MAX, INT64_MAX), @"sampleSpanNs", @1)), "sample-overflow-refused");
    for (NSString *key in @[@"monotonicNs", @"wallNs", @"sampleSpanNs"])
        for (id value in @[@YES, @1.5, @(-1), @(UINT64_MAX), @(NAN), @(INFINITY)])
            failures += check(!ciProgress(base, changing(now, key, value)), "non-integer-clock-refused");

    uint64_t ns = 0;
    failures += check(ciMachNanoseconds(101, 125, 3, &ns) && ns == 4208, "integer-mach-floor");
    failures += check(ciMachNanoseconds(INT64_MAX, 1, 1, &ns) && ns == INT64_MAX, "signed-ns-edge");
    failures += check(ciMachNanoseconds(UINT64_MAX, 1, 2, &ns) && ns == INT64_MAX, "wide-mach-math");
    failures += check(!ciMachNanoseconds(UINT64_MAX, UINT32_MAX, 1, &ns), "mach-overflow-refused");
    failures += check(!ciMachNanoseconds(1, 0, 1, &ns) && !ciMachNanoseconds(1, 1, 0, &ns), "invalid-timebase-refused");
    failures += check(ciCappedEnd(110 * ciSecond, 30 * ciSecond, product) == product, "setup-charged-to-product");
    failures += check(ciCappedEnd(160 * ciSecond, 30 * ciSecond, 180 * ciSecond) == 180 * ciSecond, "quit-charged-to-native-end");
    failures += check(ciCappedEnd(120 * ciSecond, 30 * ciSecond, 180 * ciSecond) == 150 * ciSecond, "quit-never-over-thirty");
    failures += check(ciCappedEnd(product, 30 * ciSecond, product) == 0, "expired-cap-not-renewed");
    failures += check(ciCappedEnd(INT64_MAX - 1, UINT64_MAX, INT64_MAX) == INT64_MAX, "capped-add-no-overflow");
    failures += check(exactSecondsComparison(0, 0) == 0 && exactSecondsComparison(0, 1) == -1, "exact-rational-zero");
    failures += check(exactSecondsComparison(1.5, 1500000000) == 0, "exact-rational-equality");
    failures += check(exactSecondsComparison(nextafter(1, -INFINITY), ciSecond) == -1 &&
        exactSecondsComparison(nextafter(1, INFINITY), ciSecond) == 1, "exact-rational-adjacent");
    failures += check(exactSecondsComparison(DBL_MIN, 1) == -1 && exactSecondsComparison(DBL_MAX, INT64_MAX) == 1,
        "exact-rational-large-shifts");
    failures += check(exactSecondsComparison(nextafter(0, INFINITY), 0) == 1 &&
        exactSecondsComparison(nextafter(0, INFINITY), 1) == -1, "exact-rational-subnormal");
    failures += check(exactSecondsComparison(NAN, 0) == 2 && exactSecondsComparison(INFINITY, 0) == 2 &&
        exactSecondsComparison(-1, 0) == 2, "exact-rational-invalid");
    const uint64_t floorCounterexample = UINT64_C(5466742631114575385);
    const uint64_t ceilCounterexample = UINT64_C(6265871966173738489);
    failures += check(exactSecondsComparison(nextafter((double)floorCounterexample / ciSecond, -INFINITY), floorCounterexample) == 1,
        "old-deadline-rounding-defect-reproduced");
    failures += check(exactSecondsComparison(nextafter((double)ceilCounterexample / ciSecond, INFINITY), ceilCounterexample) == -1,
        "old-now-rounding-defect-reproduced");
    failures += check(conversionBounds(floorCounterexample), "deadline-counterexample-repaired");
    failures += check(conversionBounds(ceilCounterexample), "now-counterexample-repaired");
    for (NSNumber *value in @[@0, @1, @(ciSecond - 1), @(ciSecond), @(ciSecond + 1), @(123456789012345), @(INT64_MAX)])
        failures += check(conversionBounds(value.unsignedLongLongValue), "conservative-finalizer-exact-rational");
    failures += check(conversionMatrix(), "exact-rational-boundary-and-10000-sample-matrix");
    return failures;
}

int main(int argc, const char **argv) {
    @autoreleasepool {
        if (argc == 2 && strcmp(argv[1], "--clock") == 0) {
            NSDictionary *sample = ciObserveClock();
            if (!sample) return 125;
            NSData *bytes = [NSJSONSerialization dataWithJSONObject:sample options:NSJSONWritingSortedKeys error:NULL];
            if (!bytes || fwrite(bytes.bytes, 1, bytes.length, stdout) != bytes.length || putchar('\n') == EOF) return 125;
            return 0;
        }
        if (argc != 1) return 125;
        if (decisions()) return 1;
        printf("PASS: apple-ci-envelope/%u deterministic controls; NOT_NATIVE_OR_RELEASE_QUALIFICATION\n", controls);
        return 0;
    }
}
