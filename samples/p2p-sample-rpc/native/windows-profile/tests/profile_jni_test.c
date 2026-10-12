/* Real JNI C translation unit + real bounded-buffer controller, mocked JNI/backend only.
 * Neither a JVM execution nor a Windows/SRWLOCK/NTFS simulation or runtime qualification. */
#include "../profile_win32.h"
#include <jni.h>
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

#define JNI_NAME(name) Java_dev_p2pkit_sample_rpc_profile_WindowsProfileCustodyJni_##name
JNIEXPORT jlong JNICALL JNI_NAME(openRoot)(JNIEnv *, jobject);
JNIEXPORT jlong JNICALL JNI_NAME(child)(JNIEnv *, jobject, jlong, jstring);
JNIEXPORT jlongArray JNICALL JNI_NAME(identity)(JNIEnv *, jobject, jlong);
JNIEXPORT jlongArray JNICALL JNI_NAME(fileIdentity)(JNIEnv *, jobject, jlong, jstring);
JNIEXPORT jboolean JNICALL JNI_NAME(exists)(JNIEnv *, jobject, jlong, jstring);
JNIEXPORT jlong JNICALL JNI_NAME(lockExisting)(JNIEnv *, jobject, jlong, jstring);
JNIEXPORT jlong JNICALL JNI_NAME(createProfileLock)(JNIEnv *, jobject, jlong);
JNIEXPORT jlong JNICALL JNI_NAME(createVaultLock)(JNIEnv *, jobject, jlong);
JNIEXPORT jlong JNICALL JNI_NAME(stageRecord)(JNIEnv *, jobject, jlong, jstring, jbyteArray);
JNIEXPORT jbyteArray JNICALL JNI_NAME(read)(JNIEnv *, jobject, jlong, jstring, jint);
JNIEXPORT jobjectArray JNICALL JNI_NAME(names)(JNIEnv *, jobject, jlong);
JNIEXPORT jlong JNICALL JNI_NAME(createChildDirectory)(JNIEnv *, jobject, jlong, jstring);
JNIEXPORT void JNICALL JNI_NAME(discardStage)(JNIEnv *, jobject, jlong);
JNIEXPORT void JNICALL JNI_NAME(requestExpectedFileDeletion)(JNIEnv *, jobject, jlong, jstring, jlongArray);
JNIEXPORT void JNICALL JNI_NAME(close)(JNIEnv *, jobject, jlong);
JNIEXPORT jint JNICALL JNI_NAME(abi)(JNIEnv *, jobject);
JNIEXPORT jlong JNICALL JNI_NAME(capabilities)(JNIEnv *, jobject);
#define REF(n) ((jobject)(uintptr_t)(n))
static const struct JNINativeInterface_ table;
static unsigned allocations, outside_allocations, releases, copies, results, throws, mutations, calls;
static int admitted, exception, fail_allocation, fault, nested, nesting, malformed, empty_names;
static pwp_result rejected, storage_result;
static jsize array_size = 8;
static unsigned char *live;
static size_t live_count;
static unsigned array_refs, string_refs, class_refs;
static unsigned child_calls, existing_child_calls, string_acquires, string_releases;
static unsigned vault_calls;
static unsigned unrelated_calls, string_lengths, array_lengths, long_copies;
static unsigned error_class_refs, error_object_refs, error_classes, error_methods, error_objects, bridge_errors;
static unsigned legacy_errors;
static int error_fault, error_code, input_fault;
static int identity_success, identity_fault;
static unsigned identity_refs, identity_allocations, identity_copies;
static jlong identity_words[PWP_IDENTITY_WORDS];
static const uint64_t native_identity[PWP_IDENTITY_WORDS] = {1, UINT64_MAX, UINT64_C(0x8000000000000000),
                                                            UINT64_MAX, 0x2ff, 1};
static jsize string_size = 42;
static int unavailable_string;
static jchar name[] = {'p','w','p','-','s','t','a','g','e','-',
    '0','1','2','3','4','5','6','7','8','9','a','b','c','d','e','f',
    '0','1','2','3','4','5','6','7','8','9','a','b','c','d','e','f'};
static void nested_call(void);
void *pwp_test_malloc(size_t count) {
    if (!admitted) ++outside_allocations;
    ++allocations; assert(!live && count <= PWP_RECORD_LIMIT);
    if (fail_allocation) return NULL;
    live = malloc(count); live_count = count; assert(live); return live;
}
void *pwp_test_calloc(size_t count, size_t size) {
    assert(size == 1); void *bytes = pwp_test_malloc(count);
    if (bytes) memset(bytes, 0, count); return bytes;
}
void pwp_test_free(void *bytes) {
    assert(admitted);
    if (!bytes) { assert(!live); return; }
    assert(bytes == live);
    for (size_t i = 0; i < live_count; ++i) assert(live[i] == 0);
    ++releases; free(bytes); live = NULL; live_count = 0;
}
static jsize JNICALL string_length(JNIEnv *env, jstring value) {
    (void)env; (void)value; ++string_lengths;
    if (input_fault == 1) exception = 99;
    return string_size;
}
static const jchar *JNICALL string_chars(JNIEnv *env, jstring value, jboolean *copy) {
    (void)env; (void)value; (void)copy;
    if (unavailable_string) { exception = 99; return NULL; }
    ++string_acquires;
    if (input_fault == 2) exception = 99;
    return name;
}
static void JNICALL release_string(JNIEnv *env, jstring value, const jchar *chars) {
    (void)env; (void)value; assert(chars == name); ++string_releases;
}
static jsize JNICALL array_length(JNIEnv *env, jarray value) {
    (void)env; (void)value; ++array_lengths;
    if (input_fault == 3) exception = 99;
    return array_size;
}
static void JNICALL long_region(JNIEnv *env, jlongArray value, jsize start, jsize count, jlong *words) {
    (void)env; (void)value; assert(start == 0 && count == PWP_IDENTITY_WORDS); ++long_copies;
    const jlong expected[PWP_IDENTITY_WORDS] = {1, 2, 3, 4, 0x2ff, 1};
    memcpy(words, expected, sizeof(expected));
}
static void JNICALL byte_region(JNIEnv *env, jbyteArray value, jsize start, jsize count, jbyte *bytes) {
    (void)env; (void)value; assert(admitted && start == 0 && count == array_size);
    ++copies; memset(bytes, 7, (size_t)count); nested_call(); if (fault == 1) exception = 99;
}
static jboolean JNICALL exception_check(JNIEnv *env) { (void)env; return exception ? JNI_TRUE : JNI_FALSE; }
static jclass JNICALL find_class(JNIEnv *env, const char *value) {
    (void)env;
    /* Retained only so the failure-first old JNI completes far enough to fail exact typed assertions. */
    if (!strcmp(value, "java/io/IOException")) return (jclass)REF(20);
    if (!strcmp(value, "dev/p2pkit/sample/rpc/profile/WindowsProfileCustodyException")) {
        assert(!exception); ++error_classes;
        if (error_fault == 1) { exception = 99; return NULL; }
        if (error_fault == 8) return NULL; /* Impossible conforming result: test fail-closed fallback. */
        ++error_class_refs;
        if (error_fault == 4) exception = 99;
        return (jclass)REF(21);
    }
    if (!strcmp(value, "java/lang/LinkageError")) {
        assert(!exception); return (jclass)REF(23);
    }
    assert(admitted && !exception && !strcmp(value, "java/lang/String"));
    if (fault == 4) { exception = 99; return NULL; }
    ++class_refs; return (jclass)REF(14);
}
static jint JNICALL throw_new(JNIEnv *env, jclass type, const char *message) {
    (void)env; assert(!exception);
    if (type == (jclass)REF(20)) {
        assert(strstr(message, "code ")); ++legacy_errors; ++throws; exception = 1; return JNI_OK;
    }
    assert(type == (jclass)REF(23) && !strcmp(message, "Windows profile JNI error contract failed"));
    ++bridge_errors; exception = 88; return JNI_OK;
}
static jmethodID JNICALL method(JNIEnv *env, jclass type, const char *name_value, const char *signature) {
    (void)env; assert(!exception && type == (jclass)REF(21) && !strcmp(name_value, "<init>"));
    assert(!strcmp(signature, "(I)V")); ++error_methods;
    if (error_fault == 2) { exception = 99; return NULL; }
    if (error_fault == 9) return NULL;
    if (error_fault == 5) exception = 99;
    return (jmethodID)(uintptr_t)1;
}
static jobject JNICALL new_error(JNIEnv *env, jclass type, jmethodID constructor, const jvalue *arguments) {
    (void)env; assert(!exception && type == (jclass)REF(21) && constructor == (jmethodID)(uintptr_t)1 && arguments);
    ++error_objects; error_code = arguments[0].i;
    if (error_fault == 3) { exception = 99; return NULL; }
    if (error_fault == 10) return NULL;
    ++error_object_refs;
    if (error_fault == 6) exception = 99;
    return REF(22);
}
static jint JNICALL throw_error(JNIEnv *env, jthrowable throwable) {
    (void)env; assert(!exception && throwable == (jthrowable)REF(22));
    if (error_fault == 7) { exception = 99; return JNI_ERR; }
    if (error_fault == 11) return JNI_ERR;
    if (error_fault == 12) return JNI_OK;
    ++throws; exception = 1; return JNI_OK;
}
static void JNICALL fatal_error(JNIEnv *env, const char *message) {
    (void)env; (void)message;
    /* A conforming JVM never returns from FatalError. These fixtures preserve errors without invoking it. */
    assert(0 && "Unable to report even a JNI bridge failure"); abort();
}
static void JNICALL delete_ref(JNIEnv *env, jobject value) {
    (void)env;
    if (value == REF(20)) return;
    if (value == REF(21)) { assert(error_class_refs); --error_class_refs; return; }
    if (value == REF(22)) { assert(error_object_refs); --error_object_refs; return; }
    if (value == REF(23)) return;
    if (value == REF(31)) { assert(identity_refs); --identity_refs; return; }
    assert(admitted);
    if (value == REF(11) || value == REF(12)) { assert(array_refs); --array_refs; }
    else if (value == REF(13)) { assert(string_refs); --string_refs; }
    else { assert(value == REF(14) && class_refs); --class_refs; }
}
static jbyteArray JNICALL new_bytes(JNIEnv *env, jsize count) {
    (void)env; assert(admitted && !exception && count == array_size); ++results; nested_call();
    if (fault == 2) { exception = 99; return NULL; }
    ++array_refs; return (jbyteArray)REF(11);
}
static void JNICALL set_bytes(JNIEnv *env, jbyteArray array, jsize start, jsize count, const jbyte *bytes) {
    (void)env; assert(admitted && !exception && array == (jbyteArray)REF(11) && start == 0 && count == array_size);
    for (jsize i = 0; i < count; ++i) assert(bytes[i] == 7);
    ++copies; if (fault == 3) exception = 99;
}
static jobjectArray JNICALL new_objects(JNIEnv *env, jsize count, jclass type, jobject initial) {
    (void)env; assert(admitted && !exception && count == (empty_names ? 0 : 1));
    assert(type == (jclass)REF(14) && !initial); ++results; nested_call();
    if (fault == 5) { exception = 99; return NULL; }
    ++array_refs; return (jobjectArray)REF(12);
}
static jstring JNICALL new_string(JNIEnv *env, const jchar *chars, jsize count) {
    (void)env; assert(admitted && !exception && count == 5 && chars[0] == 'a'); ++copies;
    if (fault == 6) { exception = 99; return NULL; }
    ++string_refs; return (jstring)REF(13);
}
static void JNICALL set_object(JNIEnv *env, jobjectArray array, jsize index, jobject value) {
    (void)env; assert(admitted && !exception && array == (jobjectArray)REF(12) && !index && value == REF(13));
    if (fault == 7) exception = 99;
}
static jlongArray JNICALL new_longs(JNIEnv *env, jsize count) {
    (void)env; assert(!exception && count == PWP_IDENTITY_WORDS); ++identity_allocations;
    if (identity_fault == 1) { exception = 99; return NULL; }
    if (identity_fault == 4) return NULL;
    ++identity_refs;
    if (identity_fault == 2) exception = 99;
    return (jlongArray)REF(31);
}
static void JNICALL set_longs(JNIEnv *env, jlongArray array, jsize start, jsize count, const jlong *words) {
    (void)env; assert(!exception && array == (jlongArray)REF(31) && start == 0 && count == PWP_IDENTITY_WORDS);
    ++identity_copies; memcpy(identity_words, words, sizeof(identity_words));
    if (identity_fault == 3) exception = 99;
}
static const struct JNINativeInterface_ table = {
    .GetStringLength = string_length, .GetStringChars = string_chars, .ReleaseStringChars = release_string,
    .GetArrayLength = array_length, .GetByteArrayRegion = byte_region, .ExceptionCheck = exception_check,
    .GetLongArrayRegion = long_region,
    .FindClass = find_class, .ThrowNew = throw_new, .DeleteLocalRef = delete_ref, .GetMethodID = method,
    .NewObjectA = new_error, .Throw = throw_error, .FatalError = fatal_error,
    .NewLongArray = new_longs, .SetLongArrayRegion = set_longs,
    .NewByteArray = new_bytes, .NewObjectArray = new_objects, .SetByteArrayRegion = set_bytes,
    .NewString = new_string, .SetObjectArrayElement = set_object
};
/* Ordinary unrelated native symbols are linked only because this is the complete real JNI C file. */
pwp_result pwp_win_open_root(uint64_t *out) { (void)out; ++unrelated_calls; return PWP_UNIMPLEMENTED; }
pwp_result pwp_win_child(uint64_t p, const uint16_t *n, size_t l, uint64_t *out) {
    (void)p; (void)n; (void)l; (void)out; ++existing_child_calls; return PWP_UNIMPLEMENTED;
}
pwp_result pwp_win_create_child(uint64_t p, const uint16_t *n, size_t l, uint64_t *out) {
    ++child_calls; assert(p == 1 && n == name && l == 42 && out && *out == 0 && !exception);
    if (storage_result != PWP_OK) return storage_result;
    *out = 7; return PWP_OK;
}
pwp_result pwp_win_identity(uint64_t h, uint64_t w[6]) {
    (void)h; ++unrelated_calls;
    if (!identity_success) return PWP_UNIMPLEMENTED;
    memcpy(w, native_identity, sizeof(native_identity)); return PWP_OK;
}
pwp_result pwp_win_file_identity(uint64_t d, const uint16_t *n, size_t l, uint64_t w[6]) {
    (void)d; (void)n; (void)l;
    return pwp_win_identity(d, w);
}
pwp_result pwp_win_exists(uint64_t d, const uint16_t *n, size_t l, int *out) {
    (void)d; (void)n; (void)l; (void)out; ++unrelated_calls; return PWP_UNIMPLEMENTED;
}
pwp_result pwp_win_lock(uint64_t d, const uint16_t *n, size_t l, uint64_t *out) {
    (void)d; (void)n; (void)l; (void)out; ++unrelated_calls; return PWP_UNIMPLEMENTED;
}
pwp_result pwp_win_create_profile_lock(uint64_t h, uint64_t *out) {
    (void)h; (void)out; ++unrelated_calls; return PWP_UNIMPLEMENTED;
}
pwp_result pwp_win_create_vault_lock(uint64_t directory, uint64_t *out) {
    ++vault_calls; assert(directory == 3 && out && *out == 0 && !exception);
    if (storage_result != PWP_OK) return storage_result;
    *out = 11; return PWP_OK;
}
pwp_result pwp_win_discard_stage(uint64_t h) { (void)h; ++unrelated_calls; return PWP_UNIMPLEMENTED; }
pwp_result pwp_win_close(uint64_t h) { (void)h; ++unrelated_calls; return PWP_UNIMPLEMENTED; }
pwp_result pwp_win_request_delete(uint64_t d, const uint16_t *n, size_t l, const uint64_t *w, size_t c) {
    (void)d; (void)n; (void)l; (void)w; (void)c; ++unrelated_calls; return PWP_UNIMPLEMENTED;
}
/* Rejected mock admission never calls a source/sink or allocator; actual Win32 gate is source-reviewed only. */
static pwp_result begin(void) {
    ++calls; if (admitted) return PWP_BUSY;
    if (rejected != PWP_OK) return rejected;
    admitted = 1; return PWP_OK;
}
static pwp_result end(pwp_result result) {
    assert(admitted && !live && !string_refs && !class_refs);
    if (result != PWP_OK) assert(!array_refs);
    admitted = 0; return result;
}
typedef struct { pwp_buffer_action callback; void *context; uint64_t *out; } buffer_operation;
static pwp_result stage_copy(unsigned char *bytes, size_t count, void *opaque) {
    buffer_operation *op = opaque;
    pwp_result r = op->callback(bytes, malformed ? count+1 : count, op->context);
    if (r != PWP_OK) return r;
    if (storage_result != PWP_OK) return storage_result;
    for (size_t i = 0; i < count; ++i) assert(bytes[i] == 7);
    ++mutations; *op->out = 7; return PWP_OK;
}
pwp_result pwp_win_stage(uint64_t d, const uint16_t *n, size_t l,
                         size_t count, pwp_buffer_action copy, void *context, uint64_t *out) {
    assert(d && n == name && l == 42 && copy && out); *out = 0;
    pwp_result r = begin(); if (r != PWP_OK) return r;
    buffer_operation op = {copy, context, out};
    return end(pwp_buffer_apply(count, stage_copy, &op));
}
static pwp_result read_output(unsigned char *bytes, size_t count, void *opaque) {
    buffer_operation *op = opaque; if (count) memset(bytes, 7, count);
    if (storage_result != PWP_OK) return storage_result;
    return op->callback(bytes, malformed ? count+1 : count, op->context);
}
pwp_result pwp_win_read(uint64_t d, const uint16_t *n, size_t l,
                        size_t maximum, pwp_buffer_action receive, void *context) {
    assert(d && n == name && l == 42 && receive);
    pwp_result r = begin(); if (r != PWP_OK) return r;
    buffer_operation op = {receive, context, NULL};
    return end(pwp_buffer_apply(maximum, read_output, &op));
}
typedef struct { pwp_names_action receive; void *context; } names_operation;
static pwp_result names_output(unsigned char *bytes, size_t count, void *opaque) {
    names_operation *op = opaque; assert(count == sizeof(pwp_directory_names));
    pwp_directory_names *names = (pwp_directory_names *)bytes;
    if (!empty_names) {
        const uint16_t member[] = {'a','l','p','h','a',0};
        names->count = 1; names->lengths[0] = 5; memcpy(names->names[0], member, sizeof(member));
    }
    if (storage_result != PWP_OK) return storage_result;
    if (malformed == 1) names->count = PWP_DIRECTORY_LIMIT+1;
    if (malformed == 2) names->names[0][0] = '/';
    return op->receive(names, op->context);
}
pwp_result pwp_win_names(uint64_t d, pwp_names_action receive, void *context) {
    assert(d && receive); pwp_result r = begin(); if (r != PWP_OK) return r;
    names_operation op = {receive, context};
    return end(pwp_buffer_apply(sizeof(pwp_directory_names), names_output, &op));
}
static int invoke(int kind) {
    JNIEnv env = &table;
    if (kind == 0) return JNI_NAME(stageRecord)(&env, NULL, 1, (jstring)REF(1), (jbyteArray)REF(1)) == 7;
    if (kind == 1) return JNI_NAME(read)(&env, NULL, 1, (jstring)REF(1), array_size) == (jbyteArray)REF(11);
    return JNI_NAME(names)(&env, NULL, 1) == (jobjectArray)REF(12);
}
static void nested_call(void) {
    if (!nested || nesting) return;
    nesting = 1;
    unsigned copied = copies, allocated = allocations, created = results;
    assert(!exception && !invoke(nested-1) && exception == 1 && admitted);
    assert(copies == copied && allocations == allocated && results == created);
    exception = 0; nesting = 0;
}
static void reset(void) {
    assert(!admitted && !live && !string_refs && !class_refs && !error_class_refs && !error_object_refs && !identity_refs);
    /* Successful returned Java arrays now belong to the caller; the fake caller retires its reference here. */
    array_refs = 0; exception = 0; allocations = 0; outside_allocations = 0; releases = 0;
    identity_refs = 0; identity_success = 0; identity_fault = 0; identity_allocations = 0; identity_copies = 0;
    memset(identity_words, 0, sizeof(identity_words));
    copies = 0; results = 0; throws = 0; mutations = 0; calls = 0;
    rejected = PWP_OK; storage_result = PWP_OK; fail_allocation = 0; fault = 0; nested = 0;
    nesting = 0; malformed = 0; empty_names = 0; array_size = 8;
    child_calls = 0; existing_child_calls = 0; string_acquires = 0; string_releases = 0;
    vault_calls = 0;
    unrelated_calls = 0; string_lengths = 0; array_lengths = 0; long_copies = 0;
    error_classes = 0; error_methods = 0; error_objects = 0; bridge_errors = 0; legacy_errors = 0;
    error_fault = 0; error_code = 0; input_fault = 0;
    string_size = 42; unavailable_string = 0;
}
static void rejected_admission_never_copies(void) {
    const pwp_result reasons[] = {PWP_BUSY, PWP_CLOSED, PWP_POLICY, PWP_LIMIT, PWP_CLEANUP_UNKNOWN};
    for (int kind = 0; kind < 3; ++kind) for (size_t i = 0; i < sizeof(reasons)/sizeof(reasons[0]); ++i) {
        reset(); rejected = reasons[i]; assert(!invoke(kind));
        assert(exception && !allocations && !outside_allocations && !copies && !results && !mutations);
    }
}
static void accepted_copy_stays_owned(void) {
    for (int kind = 0; kind < 3; ++kind) {
        reset(); assert(invoke(kind));
        assert(!exception && allocations == 1 && releases == 1 && !outside_allocations && !admitted);
        assert(mutations == (kind == 0 ? 1u : 0u) && array_refs == (kind ? 1u : 0u));
    }
}
static void jni_exceptions_clear_before_gate_release(void) {
    for (int injected = 1; injected <= 7; ++injected) {
        reset(); fault = injected;
        assert(!invoke(injected == 1 ? 0 : injected <= 3 ? 1 : 2));
        assert(exception == 99 && !throws && releases == 1 && !mutations && !array_refs);
    }
}
static void allocation_failure_never_copies(void) {
    for (int kind = 0; kind < 3; ++kind) {
        reset(); fail_allocation = 1; assert(!invoke(kind));
        assert(exception && allocations == 1 && !releases && !copies && !results && !mutations);
    }
}
static void storage_failure_never_publishes(void) {
    for (int kind = 0; kind < 3; ++kind) {
        reset(); storage_result = PWP_CLEANUP_UNKNOWN; assert(!invoke(kind));
        assert(exception && releases == 1 && !results && !mutations);
        assert(copies == (kind == 0 ? 1u : 0u));
    }
}
static void empty_results_and_payloads(void) {
    for (int kind = 0; kind < 3; ++kind) {
        reset(); array_size = 0; empty_names = 1; assert(invoke(kind));
        assert(!copies && !outside_allocations && allocations == (kind == 2 ? 1u : 0u));
    }
}
static void callback_bounds_reject_before_java_copy(void) {
    for (int kind = 0; kind < 3; ++kind) {
        reset(); malformed = 1; assert(!invoke(kind));
        assert(exception && !copies && !results && !mutations && releases == 1);
    }
    reset(); malformed = 2; assert(!invoke(2)); assert(exception && !copies && !results && releases == 1);
}
static void busy_reentry_cannot_copy_inside_owner(void) {
    for (int kind = 0; kind < 3; ++kind) for (int other = 1; other <= 3; ++other) {
        reset(); nested = other; assert(invoke(kind));
        assert(!exception && allocations == 1 && releases == 1 && !outside_allocations && calls == 2);
    }
}
static void entry_bounds_reject_before_backend(void) {
    for (int kind = 0; kind < 2; ++kind) {
        reset(); array_size = PWP_RECORD_LIMIT+1; assert(!invoke(kind));
        assert(exception && !calls && !allocations && !copies);
    }
    reset(); JNIEnv env = &table;
    assert(!JNI_NAME(names)(&env, NULL, 0) && exception && !calls && !allocations);
}
static void child_forwards_exact_inputs_and_lease(void) {
    reset(); JNIEnv env = &table;
    assert(JNI_NAME(createChildDirectory)(&env, NULL, 1, (jstring)REF(1)) == 7);
    assert(!exception && child_calls == 1 && !existing_child_calls);
    assert(string_acquires == 1 && string_releases == 1 && !allocations);
    assert(!error_classes && !error_methods && !error_objects && !legacy_errors && !bridge_errors);
}
static void child_bounds_reject_before_backend(void) {
    const jlong parents[] = {0, -1, INT64_MIN}; JNIEnv env = &table;
    for (size_t i = 0; i < sizeof(parents)/sizeof(parents[0]); ++i) {
        reset(); assert(!JNI_NAME(createChildDirectory)(&env, NULL, parents[i], (jstring)REF(1)));
        assert(exception && !child_calls && !existing_child_calls && !string_acquires);
    }
    reset(); assert(!JNI_NAME(createChildDirectory)(&env, NULL, 1, NULL));
    assert(exception && !child_calls && !string_acquires);
    for (int mode = 0; mode < 3; ++mode) {
        reset();
        if (mode == 0) string_size = 0;
        if (mode == 1) string_size = PWP_COMPONENT_LIMIT+1;
        if (mode == 2) name[0] = '/';
        assert(!JNI_NAME(createChildDirectory)(&env, NULL, 1, (jstring)REF(1)));
        assert(exception && !child_calls && !existing_child_calls && string_acquires == string_releases);
        name[0] = 'p';
    }
}
static void child_backend_rejection_never_uses_open_fallback(void) {
    const pwp_result reasons[] = {PWP_BUSY, PWP_CLOSED, PWP_POLICY, PWP_LIMIT, PWP_OS, PWP_CLEANUP_UNKNOWN};
    JNIEnv env = &table;
    for (size_t i = 0; i < sizeof(reasons)/sizeof(reasons[0]); ++i) {
        reset(); storage_result = reasons[i];
        assert(!JNI_NAME(createChildDirectory)(&env, NULL, 1, (jstring)REF(1)));
        assert(exception && throws == 1 && child_calls == 1 && !existing_child_calls);
        assert(string_acquires == 1 && string_releases == 1 && !allocations);
    }
}
static void child_pending_exception_never_enters_backend(void) {
    JNIEnv env = &table;
    for (int mode = 0; mode < 2; ++mode) {
        reset(); if (mode == 0) exception = 99; else unavailable_string = 1;
        assert(!JNI_NAME(createChildDirectory)(&env, NULL, 1, (jstring)REF(1)));
        assert(exception == 99 && !throws && !child_calls && !existing_child_calls && !string_acquires);
    }
}
static void child_abi_does_not_enable_complete_provider(void) {
    reset(); JNIEnv env = &table;
    assert(JNI_NAME(abi)(&env, NULL) == 7 && JNI_NAME(capabilities)(&env, NULL) == 0x43);
    assert(!child_calls && !calls && !allocations);
}
static void pending_exception_blocks_all_effectful_entries(void) {
    JNIEnv env = &table;
    for (int kind = 0; kind < 15; ++kind) {
        reset(); exception = 99;
        switch (kind) {
            case 0: (void)JNI_NAME(openRoot)(&env, NULL); break;
            case 1: (void)JNI_NAME(child)(&env, NULL, 1, (jstring)REF(1)); break;
            case 2: (void)JNI_NAME(createChildDirectory)(&env, NULL, 1, (jstring)REF(1)); break;
            case 3: (void)JNI_NAME(identity)(&env, NULL, 1); break;
            case 4: (void)JNI_NAME(fileIdentity)(&env, NULL, 1, (jstring)REF(1)); break;
            case 5: (void)JNI_NAME(exists)(&env, NULL, 1, (jstring)REF(1)); break;
            case 6: (void)JNI_NAME(names)(&env, NULL, 1); break;
            case 7: (void)JNI_NAME(read)(&env, NULL, 1, (jstring)REF(1), 8); break;
            case 8: (void)JNI_NAME(lockExisting)(&env, NULL, 1, (jstring)REF(1)); break;
            case 9: (void)JNI_NAME(createProfileLock)(&env, NULL, 1); break;
            case 10: (void)JNI_NAME(stageRecord)(&env, NULL, 1, (jstring)REF(1), (jbyteArray)REF(1)); break;
            case 11: JNI_NAME(discardStage)(&env, NULL, 1); break;
            case 12:
                array_size = PWP_IDENTITY_WORDS;
                JNI_NAME(requestExpectedFileDeletion)(&env, NULL, 1, (jstring)REF(1), (jlongArray)REF(1)); break;
            case 13: JNI_NAME(close)(&env, NULL, 1); break;
            case 14: (void)JNI_NAME(createVaultLock)(&env, NULL, 3); break;
            default: assert(0);
        }
        assert(exception == 99 && !throws && !calls && !child_calls && !existing_child_calls && !unrelated_calls);
        assert(!vault_calls);
        assert(!allocations && !copies && !results && !mutations && !string_acquires && !string_lengths);
        assert(!array_lengths && !long_copies && !error_classes && !error_methods && !error_objects);
    }
}
static void exact_integer_errors_do_not_depend_on_message_parsing(void) {
    const int codes[] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, -1, INT32_MIN, INT32_MAX};
    JNIEnv env = &table;
    for (size_t i = 0; i < sizeof(codes)/sizeof(codes[0]); ++i) {
        reset(); storage_result = (pwp_result)codes[i];
        assert(!JNI_NAME(createChildDirectory)(&env, NULL, 1, (jstring)REF(1)));
        assert(exception == 1 && throws == 1 && error_classes == 1 && error_methods == 1 && error_objects == 1);
        assert(error_code == codes[i] && !legacy_errors && !bridge_errors && !error_class_refs && !error_object_refs);
        assert(child_calls == 1 && string_acquires == 1 && string_releases == 1 && !allocations);
    }
}
static void reporting_failures_preserve_pending_error_and_retire_local_refs(void) {
    JNIEnv env = &table;
    for (int injected = 1; injected <= 7; ++injected) {
        reset(); storage_result = PWP_CLEANUP_UNKNOWN; error_fault = injected;
        assert(!JNI_NAME(createChildDirectory)(&env, NULL, 1, (jstring)REF(1)));
        assert(exception == 99 && !throws && !legacy_errors && !bridge_errors);
        assert(!error_class_refs && !error_object_refs && string_acquires == 1 && string_releases == 1);
        assert(child_calls == 1 && !existing_child_calls && !allocations);
    }
}
static void broken_vm_results_cannot_silently_report_success_or_absence(void) {
    JNIEnv env = &table;
    for (int injected = 8; injected <= 12; ++injected) {
        reset(); storage_result = PWP_NOT_FOUND; error_fault = injected;
        assert(!JNI_NAME(createChildDirectory)(&env, NULL, 1, (jstring)REF(1)));
        assert(exception == 88 && bridge_errors == 1 && !legacy_errors && !throws);
        assert(!error_class_refs && !error_object_refs && child_calls == 1 && !existing_child_calls);
    }
}
static void failed_input_observation_never_enters_backend(void) {
    JNIEnv env = &table;
    for (int injected = 1; injected <= 2; ++injected) {
        reset(); input_fault = injected;
        assert(!JNI_NAME(createChildDirectory)(&env, NULL, 1, (jstring)REF(1)));
        assert(exception == 99 && !throws && !child_calls && string_lengths == 1);
        assert(string_acquires == (injected == 2 ? 1u : 0u) && string_acquires == string_releases);
    }
    reset(); input_fault = 3;
    assert(!JNI_NAME(stageRecord)(&env, NULL, 1, (jstring)REF(1), (jbyteArray)REF(1)));
    assert(exception == 99 && array_lengths == 1 && !calls && !copies && !string_lengths);
    reset(); input_fault = 3; array_size = PWP_IDENTITY_WORDS;
    JNI_NAME(requestExpectedFileDeletion)(&env, NULL, 1, (jstring)REF(1), (jlongArray)REF(1));
    assert(exception == 99 && array_lengths == 1 && !unrelated_calls && !long_copies && !string_lengths);
}
static void vault_forwards_only_identity_directory_and_live_lease(void) {
    reset(); JNIEnv env = &table;
    assert(JNI_NAME(createVaultLock)(&env, NULL, 3) == 11);
    assert(vault_calls == 1 && !exception && !unrelated_calls && !child_calls && !existing_child_calls);
    assert(!string_lengths && !array_lengths && !allocations && !error_classes);
}
static void vault_invalid_tokens_never_enter_backend(void) {
    const jlong tokens[] = {0, -1, INT64_MIN}; JNIEnv env = &table;
    for (size_t i = 0; i < sizeof(tokens)/sizeof(tokens[0]); ++i) {
        reset(); assert(!JNI_NAME(createVaultLock)(&env, NULL, tokens[i]));
        assert(exception == 1 && error_code == PWP_ARGUMENT && !vault_calls && !unrelated_calls);
        assert(!allocations && !string_acquires && !array_lengths);
    }
}
static void vault_rejection_never_falls_back_to_existing_or_root_lock(void) {
    const pwp_result reasons[] = {PWP_BUSY, PWP_CLOSED, PWP_POLICY, PWP_LIMIT, PWP_OS, PWP_NOT_FOUND,
                                  PWP_CLEANUP_UNKNOWN, PWP_UNIMPLEMENTED};
    JNIEnv env = &table;
    for (size_t i = 0; i < sizeof(reasons)/sizeof(reasons[0]); ++i) {
        reset(); storage_result = reasons[i];
        assert(!JNI_NAME(createVaultLock)(&env, NULL, 3));
        assert(exception == 1 && error_code == (int)reasons[i] && vault_calls == 1 && !unrelated_calls);
        assert(!child_calls && !existing_child_calls && !allocations && !legacy_errors);
    }
}
static jlongArray invoke_identity(int file) {
    JNIEnv env = &table;
    return file ? JNI_NAME(fileIdentity)(&env, NULL, 1, (jstring)REF(1)) : JNI_NAME(identity)(&env, NULL, 1);
}
static void identity_output_preserves_raw_unsigned_words(void) {
    for (int file = 0; file < 2; ++file) {
        reset(); identity_success = 1;
        assert(invoke_identity(file) == (jlongArray)REF(31));
        assert(!exception && unrelated_calls == 1 && identity_allocations == 1 && identity_copies == 1);
        assert(identity_refs == 1 && !memcmp(identity_words, native_identity, sizeof(identity_words)));
        assert(string_acquires == (unsigned)file && string_acquires == string_releases && !error_classes);
        identity_refs = 0; /* Successful returned array is caller-owned. */
    }
}
static void identity_output_failure_preserves_exceptions_and_retires_arrays(void) {
    for (int file = 0; file < 2; ++file) for (int injected = 1; injected <= 4; ++injected) {
        reset(); identity_success = 1; identity_fault = injected;
        assert(!invoke_identity(file));
        assert(exception == (injected == 4 ? 88 : 99) && !identity_refs && unrelated_calls == 1);
        assert(identity_allocations == 1 && identity_copies == (injected == 3 ? 1u : 0u));
        assert(!legacy_errors && !throws && !error_classes && bridge_errors == (injected == 4 ? 1u : 0u));
        assert(string_acquires == string_releases);
    }
}
static void rejected_identity_observation_never_allocates_an_output_array(void) {
    for (int file = 0; file < 2; ++file) {
        reset(); assert(!invoke_identity(file));
        assert(exception == 1 && error_code == PWP_UNIMPLEMENTED && unrelated_calls == 1);
        assert(!identity_refs && !identity_allocations && !identity_copies && string_acquires == string_releases);
    }
}
int main(int argc, char **argv) {
    /* Bounded isolated modes also run these regression controls against the earlier production JNI. */
    if (argc == 2 && !strcmp(argv[1], "--pending")) { pending_exception_blocks_all_effectful_entries(); return 0; }
    if (argc == 2 && !strcmp(argv[1], "--errors")) { exact_integer_errors_do_not_depend_on_message_parsing(); return 0; }
    assert(argc == 1);
    rejected_admission_never_copies(); accepted_copy_stays_owned(); jni_exceptions_clear_before_gate_release();
    allocation_failure_never_copies(); storage_failure_never_publishes(); empty_results_and_payloads();
    callback_bounds_reject_before_java_copy(); busy_reentry_cannot_copy_inside_owner(); entry_bounds_reject_before_backend();
    child_forwards_exact_inputs_and_lease(); child_bounds_reject_before_backend();
    child_backend_rejection_never_uses_open_fallback(); child_pending_exception_never_enters_backend();
    child_abi_does_not_enable_complete_provider();
    pending_exception_blocks_all_effectful_entries(); exact_integer_errors_do_not_depend_on_message_parsing();
    reporting_failures_preserve_pending_error_and_retire_local_refs();
    broken_vm_results_cannot_silently_report_success_or_absence(); failed_input_observation_never_enters_backend();
    vault_forwards_only_identity_directory_and_live_lease(); vault_invalid_tokens_never_enter_backend();
    vault_rejection_never_falls_back_to_existing_or_root_lock();
    identity_output_preserves_raw_unsigned_words(); identity_output_failure_preserves_exceptions_and_retires_arrays();
    rejected_identity_observation_never_allocates_an_output_array();
    reset(); puts("25 actual-JNI mocked-backend groups PASS; NOT JVM/Windows runtime qualification"); return 0;
}
