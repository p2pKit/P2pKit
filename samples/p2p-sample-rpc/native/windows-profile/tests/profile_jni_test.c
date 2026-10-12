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
JNIEXPORT jlong JNICALL JNI_NAME(prepareRecord)(JNIEnv *, jobject, jlong, jstring, jbyteArray);
JNIEXPORT void JNICALL JNI_NAME(renameCandidate)(JNIEnv *, jobject, jlong, jstring);
JNIEXPORT jbyteArray JNICALL JNI_NAME(read)(JNIEnv *, jobject, jlong, jstring, jint);
JNIEXPORT jobjectArray JNICALL JNI_NAME(names)(JNIEnv *, jobject, jlong);
JNIEXPORT jlong JNICALL JNI_NAME(createChildDirectory)(JNIEnv *, jobject, jlong, jstring);
JNIEXPORT void JNICALL JNI_NAME(syncDirectory)(JNIEnv *, jobject, jlong);
JNIEXPORT void JNICALL JNI_NAME(discardStage)(JNIEnv *, jobject, jlong);
JNIEXPORT void JNICALL JNI_NAME(requestExpectedFileDeletion)(JNIEnv *, jobject, jlong, jstring, jlongArray);
JNIEXPORT void JNICALL JNI_NAME(close)(JNIEnv *, jobject, jlong);
JNIEXPORT jint JNICALL JNI_NAME(abi)(JNIEnv *, jobject);
JNIEXPORT jlong JNICALL JNI_NAME(capabilities)(JNIEnv *, jobject);
#define REF(n) ((jobject)(uintptr_t)(n))
#define PENDING_STRING ((jstring)REF(40))
#define TARGET_STRING ((jstring)REF(41))
#define CIPHER_ARRAY ((jbyteArray)REF(42))
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
static unsigned prepare_calls, rename_calls, sync_calls;
static uint64_t sync_token;
static uint64_t prepare_directory, rename_token;
static jbyteArray active_ciphertext;
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
static const char pending_text[] = "pwp-pending-0123456789abcdef0123456789abcdef";
static const char identity_target[] = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef.aesgcm";
static jchar pending_name[PWP_COMPONENT_LIMIT+1], target_name[PWP_COMPONENT_LIMIT+1];
static jsize pending_size, target_size;
static void set_name(jchar *output, jsize *length, const char *input) {
    size_t count = strlen(input); assert(count <= PWP_COMPONENT_LIMIT);
    memset(output, 0, (PWP_COMPONENT_LIMIT+1)*sizeof(*output));
    for (size_t i = 0; i < count; ++i) output[i] = (unsigned char)input[i];
    *length = (jsize)count;
}
static const jchar *string_storage(jstring value) {
    if (value == PENDING_STRING) return pending_name;
    if (value == TARGET_STRING) return target_name;
    assert(value == (jstring)REF(1)); return name;
}
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
    (void)env; ++string_lengths;
    if (input_fault == 1) exception = 99;
    if (value == PENDING_STRING) return pending_size;
    if (value == TARGET_STRING) return target_size;
    return string_size;
}
static const jchar *JNICALL string_chars(JNIEnv *env, jstring value, jboolean *copy) {
    (void)env; (void)copy;
    if (unavailable_string) { if (unavailable_string == 1) exception = 99; return NULL; }
    ++string_acquires;
    if (input_fault == 2) exception = 99;
    return string_storage(value);
}
static void JNICALL release_string(JNIEnv *env, jstring value, const jchar *chars) {
    (void)env; assert(chars == string_storage(value)); ++string_releases;
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
    (void)env; assert(admitted && value == active_ciphertext && start == 0 && count == array_size);
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
pwp_result pwp_win_sync_directory(uint64_t directory) {
    ++sync_calls;
    assert(directory == sync_token && !exception);
    return storage_result;
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
    active_ciphertext = (jbyteArray)REF(1);
    buffer_operation op = {copy, context, out};
    return end(pwp_buffer_apply(count, stage_copy, &op));
}
static pwp_result prepare_copy(unsigned char *bytes, size_t count, void *opaque) {
    buffer_operation *op = opaque;
    size_t reported = malformed == 1 ? count+1 : malformed == 3 ? count-1 : malformed == 4 ? SIZE_MAX : count;
    pwp_result r = op->callback(malformed == 2 ? NULL : bytes, reported, op->context);
    if (r != PWP_OK) return r;
    if (storage_result != PWP_OK) return storage_result;
    for (size_t i = 0; i < count; ++i) assert(bytes[i] == 7);
    ++mutations; *op->out = 13; return PWP_OK;
}
pwp_result pwp_win_prepare_record(uint64_t d, const uint16_t *n, size_t l,
                                  size_t count, pwp_buffer_action copy, void *context, uint64_t *out) {
    ++prepare_calls;
    assert(d == prepare_directory && n == pending_name && l == 44 && pwp_candidate_name(n, l));
    assert(count == (size_t)array_size && copy && out && *out == 0 && !exception);
    pwp_result r = begin(); if (r != PWP_OK) return r;
    active_ciphertext = CIPHER_ARRAY;
    buffer_operation op = {copy, context, out};
    /* Only forwarding and real buffer ownership are exercised; no fake OS candidate is claimed. */
    return end(pwp_buffer_apply(count, prepare_copy, &op));
}
pwp_result pwp_win_rename_candidate(uint64_t token, const uint16_t *n, size_t l) {
    ++rename_calls;
    assert(token == rename_token && n == target_name && l == (size_t)target_size && !exception);
    assert(pwp_candidate_target(n, l, 0) || pwp_candidate_target(n, l, 1));
    pwp_result r = begin(); if (r != PWP_OK) return r;
    /* storage_result can reject even valid syntax: only the real native ledger grants scope. */
    return end(storage_result);
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
    if (kind == 2) return JNI_NAME(names)(&env, NULL, 1) == (jobjectArray)REF(12);
    if (kind == 3) return JNI_NAME(prepareRecord)(&env, NULL, (jlong)prepare_directory,
        PENDING_STRING, CIPHER_ARRAY) == 13;
    assert(kind == 4);
    JNI_NAME(renameCandidate)(&env, NULL, (jlong)rename_token, TARGET_STRING);
    return !exception;
}
static void nested_call(void) {
    if (!nested || nesting) return;
    nesting = 1;
    unsigned copied = copies, allocated = allocations, created = results;
    jbyteArray original_source = active_ciphertext;
    assert(!exception && !invoke(nested-1) && exception == 1 && admitted);
    assert(copies == copied && allocations == allocated && results == created);
    assert(active_ciphertext == original_source);
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
    vault_calls = 0; sync_calls = 0; sync_token = 3;
    prepare_calls = 0; rename_calls = 0; prepare_directory = 3; rename_token = 13; active_ciphertext = NULL;
    unrelated_calls = 0; string_lengths = 0; array_lengths = 0; long_copies = 0;
    error_classes = 0; error_methods = 0; error_objects = 0; bridge_errors = 0; legacy_errors = 0;
    error_fault = 0; error_code = 0; input_fault = 0;
    string_size = 42; unavailable_string = 0;
    set_name(pending_name, &pending_size, pending_text);
    set_name(target_name, &target_size, "profile.header");
}
static void rejected_admission_never_copies(void) {
    const pwp_result reasons[] = {PWP_BUSY, PWP_CLOSED, PWP_POLICY, PWP_LIMIT, PWP_CLEANUP_UNKNOWN};
    for (int kind = 0; kind < 4; ++kind) for (size_t i = 0; i < sizeof(reasons)/sizeof(reasons[0]); ++i) {
        reset(); rejected = reasons[i]; assert(!invoke(kind));
        assert(exception && !allocations && !outside_allocations && !copies && !results && !mutations);
    }
}
static void accepted_copy_stays_owned(void) {
    for (int kind = 0; kind < 4; ++kind) {
        reset(); assert(invoke(kind));
        assert(!exception && allocations == 1 && releases == 1 && !outside_allocations && !admitted);
        assert(mutations == (kind == 0 || kind == 3 ? 1u : 0u));
        assert(array_refs == (kind == 1 || kind == 2 ? 1u : 0u));
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
    for (int kind = 0; kind < 4; ++kind) {
        reset(); fail_allocation = 1; assert(!invoke(kind));
        assert(exception && allocations == 1 && !releases && !copies && !results && !mutations);
    }
}
static void storage_failure_never_publishes(void) {
    for (int kind = 0; kind < 4; ++kind) {
        reset(); storage_result = PWP_CLEANUP_UNKNOWN; assert(!invoke(kind));
        assert(exception && releases == 1 && !results && !mutations);
        assert(copies == (kind == 0 || kind == 3 ? 1u : 0u));
    }
}
static void empty_results_and_payloads(void) {
    for (int kind = 0; kind < 4; ++kind) {
        reset(); array_size = 0; empty_names = 1; assert(invoke(kind));
        assert(!copies && !outside_allocations && allocations == (kind == 2 ? 1u : 0u));
    }
}
static void callback_bounds_reject_before_java_copy(void) {
    for (int kind = 0; kind < 4; ++kind) {
        reset(); malformed = 1; assert(!invoke(kind));
        assert(exception && !copies && !results && !mutations && releases == 1);
    }
    reset(); malformed = 2; assert(!invoke(2)); assert(exception && !copies && !results && releases == 1);
}
static void busy_reentry_cannot_copy_inside_owner(void) {
    for (int kind = 0; kind < 4; ++kind) for (int other = 1; other <= 5; ++other) {
        reset(); nested = other; assert(invoke(kind));
        assert(!exception && allocations == 1 && releases == 1 && !outside_allocations && calls == 2);
    }
}
static void entry_bounds_reject_before_backend(void) {
    const int kinds[] = {0, 1, 3};
    for (size_t i = 0; i < sizeof(kinds)/sizeof(kinds[0]); ++i) {
        reset(); array_size = PWP_RECORD_LIMIT+1; assert(!invoke(kinds[i]));
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
    assert(JNI_NAME(abi)(&env, NULL) == 9 && JNI_NAME(capabilities)(&env, NULL) == 0x43);
    assert(!child_calls && !calls && !allocations);
}
static void pending_exception_blocks_all_effectful_entries(void) {
    JNIEnv env = &table;
    for (int kind = 0; kind < 18; ++kind) {
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
            case 15: (void)JNI_NAME(prepareRecord)(&env, NULL, 3, PENDING_STRING, CIPHER_ARRAY); break;
            case 16: JNI_NAME(renameCandidate)(&env, NULL, 13, TARGET_STRING); break;
            case 17: JNI_NAME(syncDirectory)(&env, NULL, 3); break;
            default: assert(0);
        }
        assert(exception == 99 && !throws && !calls && !child_calls && !existing_child_calls && !unrelated_calls);
        assert(!vault_calls && !prepare_calls && !rename_calls && !sync_calls);
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
static void no_candidate_effects(void) {
    assert(!prepare_calls && !rename_calls && !calls && !unrelated_calls && !child_calls && !existing_child_calls);
    assert(!vault_calls && !allocations && !outside_allocations && !copies && !results && !mutations);
    assert(!admitted && !live && string_acquires == string_releases && !error_class_refs && !error_object_refs);
}
static void prepare_boundary_copies_use_exact_source(void) {
    const jsize sizes[] = {0, 1, 4095, 4096, 4097, 65535, 65536, 65537, PWP_RECORD_LIMIT-1, PWP_RECORD_LIMIT};
    const uint64_t directories[] = {1, 3, INT64_MAX};
    for (size_t d = 0; d < sizeof(directories)/sizeof(directories[0]); ++d)
        for (size_t i = 0; i < sizeof(sizes)/sizeof(sizes[0]); ++i) {
            reset(); prepare_directory = directories[d]; array_size = sizes[i];
            assert(invoke(3) && !exception && prepare_calls == 1 && calls == 1 && mutations == 1);
            assert(array_lengths == 1 && string_lengths == 1 && string_acquires == 1 && string_releases == 1);
            assert(allocations == (sizes[i] ? 1u : 0u) && releases == allocations && copies == allocations);
            assert(!outside_allocations && !admitted && !live && !results && !array_refs);
            assert(!rename_calls && !unrelated_calls && !child_calls && !existing_child_calls && !vault_calls);
            assert(!error_classes && !throws);
        }
}
static void candidate_invalid_tokens_reject_before_inputs(void) {
    const jlong tokens[] = {0, -1, INT64_MIN}; JNIEnv env = &table;
    for (size_t i = 0; i < sizeof(tokens)/sizeof(tokens[0]); ++i) for (int kind = 3; kind <= 4; ++kind) {
        reset();
        if (kind == 3) assert(!JNI_NAME(prepareRecord)(&env, NULL, tokens[i], PENDING_STRING, CIPHER_ARRAY));
        else JNI_NAME(renameCandidate)(&env, NULL, tokens[i], TARGET_STRING);
        assert(exception == 1 && error_code == PWP_ARGUMENT && !array_lengths && !string_lengths);
        no_candidate_effects();
    }
}
static void prepare_null_and_invalid_arrays_reject_before_copy(void) {
    const jsize sizes[] = {-1, INT32_MIN, PWP_RECORD_LIMIT+1, INT32_MAX}; JNIEnv env = &table;
    reset(); assert(!JNI_NAME(prepareRecord)(&env, NULL, 3, PENDING_STRING, NULL));
    assert(exception == 1 && error_code == PWP_ARGUMENT && !array_lengths && !string_lengths);
    no_candidate_effects();
    for (size_t i = 0; i < sizeof(sizes)/sizeof(sizes[0]); ++i) {
        reset(); array_size = sizes[i]; assert(!invoke(3));
        assert(exception == 1 && error_code == PWP_ARGUMENT && array_lengths == 1 && !string_lengths);
        no_candidate_effects();
    }
    reset(); assert(!JNI_NAME(prepareRecord)(&env, NULL, 3, NULL, CIPHER_ARRAY));
    assert(exception == 1 && error_code == PWP_ARGUMENT && array_lengths == 1 && !string_lengths);
    no_candidate_effects();
}
static void preparation_requires_exact_pending_names(void) {
    const char *invalid[] = {"pwp-stage-0123456789abcdef0123456789abcdef", "profile.header", "profile.lock",
        "Pwp-pending-0123456789abcdef0123456789abcdef", "pwp-pending-0123456789abcdef0123456789abcdeF",
        "pwp-pending-0123456789abcdef0123456789abcdeg", "../profile.header", "profile.header:stream"};
    for (size_t i = 0; i < sizeof(invalid)/sizeof(invalid[0]); ++i) {
        reset(); set_name(pending_name, &pending_size, invalid[i]); assert(!invoke(3));
        assert(exception == 1 && error_code == PWP_ARGUMENT && string_acquires == 1);
        no_candidate_effects();
    }
    const jsize lengths[] = {0, -1, 43, 45, PWP_COMPONENT_LIMIT+1, INT32_MAX};
    for (size_t i = 0; i < sizeof(lengths)/sizeof(lengths[0]); ++i) {
        reset(); pending_size = lengths[i]; assert(!invoke(3));
        assert(exception == 1 && error_code == PWP_ARGUMENT); no_candidate_effects();
    }
    const jchar changed[] = {0, '/', '\\', ':', 0xd800, 0xffff};
    for (size_t i = 0; i < sizeof(changed)/sizeof(changed[0]); ++i) {
        reset(); pending_name[20] = changed[i]; assert(!invoke(3));
        assert(exception == 1 && error_code == PWP_ARGUMENT); no_candidate_effects();
    }
}
static void stage_and_candidate_names_are_disjoint(void) {
    JNIEnv env = &table;
    reset(); assert(!JNI_NAME(stageRecord)(&env, NULL, 3, PENDING_STRING, CIPHER_ARRAY));
    assert(exception == 1 && error_code == PWP_ARGUMENT && string_acquires == 1); no_candidate_effects();
    reset(); assert(!JNI_NAME(prepareRecord)(&env, NULL, 3, (jstring)REF(1), CIPHER_ARRAY));
    assert(exception == 1 && error_code == PWP_ARGUMENT && string_acquires == 1); no_candidate_effects();
    reset(); assert(invoke(0) && mutations == 1 && copies == 1 && !prepare_calls && !rename_calls);
    assert(string_acquires == 1 && string_releases == 1 && releases == 1 && !exception);
}
static void prepare_copy_exception_is_retired_before_return(void) {
    const jsize sizes[] = {1, 4097, PWP_RECORD_LIMIT};
    for (size_t i = 0; i < sizeof(sizes)/sizeof(sizes[0]); ++i) {
        reset(); array_size = sizes[i]; fault = 1; assert(!invoke(3));
        assert(exception == 99 && prepare_calls == 1 && calls == 1 && copies == 1);
        assert(allocations == 1 && releases == 1 && !outside_allocations && !admitted && !live);
        assert(!throws && !error_classes && !mutations && !results && !unrelated_calls && !rename_calls);
        assert(string_acquires == 1 && string_releases == 1);
    }
}
static void prepare_callback_contract_rejects_before_copy(void) {
    const jsize sizes[] = {1, 4097, PWP_RECORD_LIMIT};
    for (size_t i = 0; i < sizeof(sizes)/sizeof(sizes[0]); ++i) for (int injected = 1; injected <= 4; ++injected) {
        reset(); array_size = sizes[i]; malformed = injected; assert(!invoke(3));
        assert(exception == 1 && error_code == PWP_ARGUMENT && prepare_calls == 1 && calls == 1);
        assert(allocations == 1 && releases == 1 && !outside_allocations && !admitted && !live);
        assert(!copies && !mutations && !results && !unrelated_calls && !rename_calls);
        assert(string_acquires == 1 && string_releases == 1);
    }
}
static void rename_forwards_only_exact_syntax_and_token(void) {
    const char *targets[] = {"profile.header", identity_target};
    const uint64_t tokens[] = {1, 13, INT64_MAX};
    for (size_t i = 0; i < sizeof(targets)/sizeof(targets[0]); ++i)
        for (size_t j = 0; j < sizeof(tokens)/sizeof(tokens[0]); ++j) {
            reset(); set_name(target_name, &target_size, targets[i]); rename_token = tokens[j];
            assert(invoke(4) && !exception && rename_calls == 1 && calls == 1);
            assert(string_lengths == 1 && string_acquires == 1 && string_releases == 1);
            assert(!array_lengths && !allocations && !copies && !results && !mutations && !admitted);
            assert(!prepare_calls && !unrelated_calls && !child_calls && !existing_child_calls && !vault_calls);
        }
}
static void rename_scope_remains_native_authority(void) {
    const char *targets[] = {"profile.header", identity_target};
    for (size_t i = 0; i < sizeof(targets)/sizeof(targets[0]); ++i) {
        reset(); set_name(target_name, &target_size, targets[i]); storage_result = PWP_POLICY;
        /* Valid syntax is deliberately refused by the mock ledger; JNI cannot convert that to success. */
        assert(!invoke(4) && exception == 1 && error_code == PWP_POLICY && rename_calls == 1 && calls == 1);
        assert(!prepare_calls && !unrelated_calls && !allocations && !copies && !mutations && !admitted);
        assert(string_acquires == 1 && string_releases == 1);
    }
}
static void rename_rejects_invalid_targets_before_backend(void) {
    const char *invalid[] = {"profile.lock", "vault.lock", "identity", "Profile.header", "profile.header.",
        "pwp-stage-0123456789abcdef0123456789abcdef", pending_text,
        "../profile.header", "profile.header:stream", "profile.header "};
    for (size_t i = 0; i < sizeof(invalid)/sizeof(invalid[0]); ++i) {
        reset(); set_name(target_name, &target_size, invalid[i]); assert(!invoke(4));
        assert(exception == 1 && error_code == PWP_ARGUMENT); no_candidate_effects();
    }
    const jsize lengths[] = {0, -1, 13, 15, PWP_COMPONENT_LIMIT+1, INT32_MAX};
    for (size_t i = 0; i < sizeof(lengths)/sizeof(lengths[0]); ++i) {
        reset(); target_size = lengths[i]; assert(!invoke(4));
        assert(exception == 1 && error_code == PWP_ARGUMENT); no_candidate_effects();
    }
    const jchar changed[] = {'A', 'g', 0, '/', '\\', ':', 0xd800, 0xffff};
    for (size_t i = 0; i < sizeof(changed)/sizeof(changed[0]); ++i) {
        reset(); set_name(target_name, &target_size, identity_target); target_name[20] = changed[i];
        assert(!invoke(4) && exception == 1 && error_code == PWP_ARGUMENT); no_candidate_effects();
    }
    reset(); JNIEnv env = &table; JNI_NAME(renameCandidate)(&env, NULL, 13, NULL);
    assert(exception == 1 && error_code == PWP_ARGUMENT && !string_lengths); no_candidate_effects();
}
static void candidate_observation_failures_preserve_exception(void) {
    for (int kind = 3; kind <= 4; ++kind) for (int injected = 1; injected <= 2; ++injected) {
        reset(); input_fault = injected; assert(!invoke(kind));
        assert(exception == 99 && !throws && !error_classes && string_lengths == 1);
        assert(string_acquires == (injected == 2 ? 1u : 0u)); no_candidate_effects();
    }
    reset(); input_fault = 3; assert(!invoke(3));
    assert(exception == 99 && array_lengths == 1 && !string_lengths && !error_classes && !throws);
    no_candidate_effects();
    for (int kind = 3; kind <= 4; ++kind) for (int injected = 1; injected <= 2; ++injected) {
        reset(); unavailable_string = injected; assert(!invoke(kind));
        assert(exception == (injected == 1 ? 99 : 88) && !throws && !error_classes);
        assert(bridge_errors == (injected == 2 ? 1u : 0u) && string_lengths == 1 && !string_acquires);
        no_candidate_effects();
    }
}
static void candidate_native_errors_are_exact_without_fallback(void) {
    const int codes[] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, -1, INT32_MIN, INT32_MAX};
    for (int kind = 3; kind <= 4; ++kind) for (size_t i = 0; i < sizeof(codes)/sizeof(codes[0]); ++i) {
        reset(); storage_result = (pwp_result)codes[i]; assert(!invoke(kind));
        assert(exception == 1 && error_code == codes[i] && throws == 1 && calls == 1);
        assert(prepare_calls == (kind == 3 ? 1u : 0u) && rename_calls == (kind == 4 ? 1u : 0u));
        assert(allocations == (kind == 3 ? 1u : 0u) && releases == allocations && copies == allocations);
        assert(!outside_allocations && !admitted && !live && !mutations && !results && !unrelated_calls);
        assert(!child_calls && !existing_child_calls && !vault_calls && !legacy_errors && !bridge_errors);
        assert(error_classes == 1 && error_methods == 1 && error_objects == 1);
        assert(!error_class_refs && !error_object_refs && string_acquires == 1 && string_releases == 1);
    }
}
static void candidate_error_reporting_failures_never_restart_native_work(void) {
    for (int kind = 3; kind <= 4; ++kind) for (int injected = 1; injected <= 12; ++injected) {
        reset(); storage_result = PWP_CLEANUP_UNKNOWN; error_fault = injected; assert(!invoke(kind));
        assert(exception == (injected <= 7 ? 99 : 88) && !throws && !legacy_errors);
        assert(bridge_errors == (injected <= 7 ? 0u : 1u) && !error_class_refs && !error_object_refs);
        assert(prepare_calls == (kind == 3 ? 1u : 0u) && rename_calls == (kind == 4 ? 1u : 0u) && calls == 1);
        assert(allocations == (kind == 3 ? 1u : 0u) && releases == allocations && !outside_allocations);
        assert(!admitted && !live && !unrelated_calls && !mutations && !results);
        assert(string_acquires == 1 && string_releases == 1);
    }
}
static void uncertain_rename_does_not_retry_or_retire_in_jni(void) {
    reset(); storage_result = PWP_CLEANUP_UNKNOWN; assert(!invoke(4));
    assert(exception == 1 && error_code == PWP_CLEANUP_UNKNOWN && rename_calls == 1 && calls == 1);
    assert(!unrelated_calls && !prepare_calls && !allocations && !copies && !mutations);
    unsigned observed = string_lengths;
    assert(!invoke(4) && rename_calls == 1 && calls == 1 && string_lengths == observed);
    assert(exception == 1 && throws == 1 && string_acquires == 1 && string_releases == 1);
    /* The second invocation was blocked by the original pending Java exception, not a simulated NTFS recovery. */
}
static void sync_forwards_only_the_exact_positive_token(void) {
    const jlong tokens[] = {1, 3, INT64_MAX}; JNIEnv env = &table;
    for (size_t i = 0; i < sizeof(tokens)/sizeof(tokens[0]); ++i) {
        reset(); sync_token = (uint64_t)tokens[i]; JNI_NAME(syncDirectory)(&env, NULL, tokens[i]);
        assert(sync_calls == 1 && !exception && !throws && !allocations && !copies);
        assert(!calls && !unrelated_calls && !string_lengths && !array_lengths && !mutations);
    }
}
static void sync_rejects_invalid_tokens_before_native_work(void) {
    const jlong tokens[] = {0, -1, INT64_MIN}; JNIEnv env = &table;
    for (size_t i = 0; i < sizeof(tokens)/sizeof(tokens[0]); ++i) {
        reset(); JNI_NAME(syncDirectory)(&env, NULL, tokens[i]);
        assert(exception == 1 && error_code == PWP_ARGUMENT && throws == 1 && !sync_calls);
        assert(!unrelated_calls && !allocations && !copies && !string_lengths && !array_lengths);
    }
}
static void sync_errors_never_retry_or_retire_native_ownership(void) {
    const int codes[] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, -1, INT32_MIN, INT32_MAX}; JNIEnv env = &table;
    for (size_t i = 0; i < sizeof(codes)/sizeof(codes[0]); ++i) {
        reset(); storage_result = (pwp_result)codes[i]; JNI_NAME(syncDirectory)(&env, NULL, 3);
        assert(exception == 1 && error_code == codes[i] && throws == 1 && sync_calls == 1);
        JNI_NAME(syncDirectory)(&env, NULL, 3);
        assert(exception == 1 && sync_calls == 1 && throws == 1 && !unrelated_calls && !allocations && !copies);
        assert(!error_class_refs && !error_object_refs && !legacy_errors && !bridge_errors);
    }
}
static void sync_reporting_failure_preserves_pending_exception(void) {
    JNIEnv env = &table;
    for (int injected = 1; injected <= 12; ++injected) {
        reset(); storage_result = PWP_CLEANUP_UNKNOWN; error_fault = injected;
        JNI_NAME(syncDirectory)(&env, NULL, 3);
        assert(exception == (injected <= 7 ? 99 : 88) && sync_calls == 1 && !throws);
        assert(bridge_errors == (injected <= 7 ? 0u : 1u) && !error_class_refs && !error_object_refs);
        assert(!allocations && !copies && !unrelated_calls && !mutations);
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
    prepare_boundary_copies_use_exact_source(); candidate_invalid_tokens_reject_before_inputs();
    prepare_null_and_invalid_arrays_reject_before_copy(); preparation_requires_exact_pending_names();
    stage_and_candidate_names_are_disjoint(); prepare_copy_exception_is_retired_before_return();
    prepare_callback_contract_rejects_before_copy(); rename_forwards_only_exact_syntax_and_token();
    rename_scope_remains_native_authority(); rename_rejects_invalid_targets_before_backend();
    candidate_observation_failures_preserve_exception(); candidate_native_errors_are_exact_without_fallback();
    candidate_error_reporting_failures_never_restart_native_work(); uncertain_rename_does_not_retry_or_retire_in_jni();
    sync_forwards_only_the_exact_positive_token(); sync_rejects_invalid_tokens_before_native_work();
    sync_errors_never_retry_or_retire_native_ownership(); sync_reporting_failure_preserves_pending_exception();
    reset(); puts("43 actual-JNI mocked-backend groups PASS; NOT JVM/Windows runtime qualification"); return 0;
}
