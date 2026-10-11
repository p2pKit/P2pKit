/* Real JNI C translation unit + real bounded-buffer controller, mocked JNI/backend only.
 * Neither a JVM execution nor a Windows/SRWLOCK/NTFS simulation or runtime qualification. */
#include "../profile_win32.h"
#include <jni.h>
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

#define JNI_NAME(name) Java_dev_p2pkit_sample_rpc_profile_WindowsProfileCustodyJni_##name
JNIEXPORT jlong JNICALL JNI_NAME(stageRecord)(JNIEnv *, jobject, jlong, jstring, jbyteArray);
JNIEXPORT jbyteArray JNICALL JNI_NAME(read)(JNIEnv *, jobject, jlong, jstring, jint);
JNIEXPORT jobjectArray JNICALL JNI_NAME(names)(JNIEnv *, jobject, jlong);
#define REF(n) ((jobject)(uintptr_t)(n))
static const struct JNINativeInterface_ table;
static unsigned allocations, outside_allocations, releases, copies, results, throws, mutations, calls;
static int admitted, exception, fail_allocation, fault, nested, nesting, malformed, empty_names;
static pwp_result rejected, storage_result;
static jsize array_size = 8;
static unsigned char *live;
static size_t live_count;
static unsigned array_refs, string_refs, class_refs;
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
static jsize JNICALL string_length(JNIEnv *env, jstring value) { (void)env; (void)value; return 42; }
static const jchar *JNICALL string_chars(JNIEnv *env, jstring value, jboolean *copy) {
    (void)env; (void)value; (void)copy; return name;
}
static void JNICALL release_string(JNIEnv *env, jstring value, const jchar *chars) {
    (void)env; (void)value; assert(chars == name);
}
static jsize JNICALL array_length(JNIEnv *env, jarray value) { (void)env; (void)value; return array_size; }
static void JNICALL byte_region(JNIEnv *env, jbyteArray value, jsize start, jsize count, jbyte *bytes) {
    (void)env; (void)value; assert(admitted && start == 0 && count == array_size);
    ++copies; memset(bytes, 7, (size_t)count); nested_call(); if (fault == 1) exception = 99;
}
static jboolean JNICALL exception_check(JNIEnv *env) { (void)env; return exception ? JNI_TRUE : JNI_FALSE; }
static jclass JNICALL find_class(JNIEnv *env, const char *value) {
    (void)env;
    if (!strcmp(value, "java/io/IOException")) return (jclass)REF(20);
    assert(admitted && !exception && !strcmp(value, "java/lang/String"));
    if (fault == 4) { exception = 99; return NULL; }
    ++class_refs; return (jclass)REF(14);
}
static jint JNICALL throw_new(JNIEnv *env, jclass type, const char *message) {
    (void)env; assert(type == (jclass)REF(20) && strstr(message, "code ") && !exception);
    ++throws; exception = 1; return 0;
}
static void JNICALL delete_ref(JNIEnv *env, jobject value) {
    (void)env;
    if (value == REF(20)) return;
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
static const struct JNINativeInterface_ table = {
    .GetStringLength = string_length, .GetStringChars = string_chars, .ReleaseStringChars = release_string,
    .GetArrayLength = array_length, .GetByteArrayRegion = byte_region, .ExceptionCheck = exception_check,
    .FindClass = find_class, .ThrowNew = throw_new, .DeleteLocalRef = delete_ref,
    .NewByteArray = new_bytes, .NewObjectArray = new_objects, .SetByteArrayRegion = set_bytes,
    .NewString = new_string, .SetObjectArrayElement = set_object
};
/* Ordinary unrelated native symbols are linked only because this is the complete real JNI C file. */
pwp_result pwp_win_open_root(uint64_t *out) { (void)out; return PWP_UNIMPLEMENTED; }
pwp_result pwp_win_child(uint64_t p, const uint16_t *n, size_t l, uint64_t *out) {
    (void)p; (void)n; (void)l; (void)out; return PWP_UNIMPLEMENTED;
}
pwp_result pwp_win_identity(uint64_t h, uint64_t w[6]) { (void)h; (void)w; return PWP_UNIMPLEMENTED; }
pwp_result pwp_win_file_identity(uint64_t d, const uint16_t *n, size_t l, uint64_t w[6]) {
    (void)d; (void)n; (void)l; (void)w; return PWP_UNIMPLEMENTED;
}
pwp_result pwp_win_exists(uint64_t d, const uint16_t *n, size_t l, int *out) {
    (void)d; (void)n; (void)l; (void)out; return PWP_UNIMPLEMENTED;
}
pwp_result pwp_win_lock(uint64_t d, const uint16_t *n, size_t l, uint64_t *out) {
    (void)d; (void)n; (void)l; (void)out; return PWP_UNIMPLEMENTED;
}
pwp_result pwp_win_create_profile_lock(uint64_t h, uint64_t *out) { (void)h; (void)out; return PWP_UNIMPLEMENTED; }
pwp_result pwp_win_discard_stage(uint64_t h) { (void)h; return PWP_UNIMPLEMENTED; }
pwp_result pwp_win_close(uint64_t h) { (void)h; return PWP_UNIMPLEMENTED; }
pwp_result pwp_win_request_delete(uint64_t d, const uint16_t *n, size_t l, const uint64_t *w, size_t c) {
    (void)d; (void)n; (void)l; (void)w; (void)c; return PWP_UNIMPLEMENTED;
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
    assert(!admitted && !live && !string_refs && !class_refs);
    /* Successful returned Java arrays now belong to the caller; the fake caller retires its reference here. */
    array_refs = 0; exception = 0; allocations = 0; outside_allocations = 0; releases = 0;
    copies = 0; results = 0; throws = 0; mutations = 0; calls = 0;
    rejected = PWP_OK; storage_result = PWP_OK; fail_allocation = 0; fault = 0; nested = 0;
    nesting = 0; malformed = 0; empty_names = 0; array_size = 8;
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
int main(void) {
    rejected_admission_never_copies(); accepted_copy_stays_owned(); jni_exceptions_clear_before_gate_release();
    allocation_failure_never_copies(); storage_failure_never_publishes(); empty_results_and_payloads();
    callback_bounds_reject_before_java_copy(); busy_reentry_cannot_copy_inside_owner(); entry_bounds_reject_before_backend();
    reset(); puts("9 actual-JNI mocked-backend buffer groups PASS; NOT JVM/Windows runtime qualification"); return 0;
}
