#include "profile_win32.h"
#include <jni.h>
#include <stdlib.h>
#include <string.h>

_Static_assert(sizeof(jlong) == sizeof(uint64_t), "JNI identity words require exact 64-bit storage");

#define JNI_NAME(name) Java_dev_p2pkit_sample_rpc_profile_WindowsProfileCustodyJni_##name
static void bridge_failure(JNIEnv *env) {
    if ((*env)->ExceptionCheck(env)) return;
    jclass error = (*env)->FindClass(env, "java/lang/LinkageError");
    if (error) {
        if (!(*env)->ExceptionCheck(env))
            (void)(*env)->ThrowNew(env, error, "Windows profile JNI error contract failed");
        (*env)->DeleteLocalRef(env, error);
    }
    if (!(*env)->ExceptionCheck(env)) {
        /* A conforming JVM reports linkage/allocation/Throw failures with a pending exception.
         * Never turn a broken reporting contract into a successful zero/false result. */
        (*env)->FatalError(env, "Windows profile JNI error contract failed");
        abort(); /* FatalError cannot return; retain fail-closed behavior even for a broken JNI vtable. */
    }
}
static void fail(JNIEnv *env, pwp_result result) {
    if (result == PWP_OK || (*env)->ExceptionCheck(env)) return;
    jclass type = (*env)->FindClass(env, "dev/p2pkit/sample/rpc/profile/WindowsProfileCustodyException");
    jobject error = NULL;
    if (type && !(*env)->ExceptionCheck(env)) {
        jmethodID constructor = (*env)->GetMethodID(env, type, "<init>", "(I)V");
        if (constructor && !(*env)->ExceptionCheck(env)) {
            jvalue arguments[1]; arguments[0].i = (jint)result;
            error = (*env)->NewObjectA(env, type, constructor, arguments);
            if (error && !(*env)->ExceptionCheck(env)) (void)(*env)->Throw(env, (jthrowable)error);
        }
    }
    /* Deletion is legal with a pending exception. Keep the original OOM/linkage/constructor failure,
     * never clear it to rebuild a message or retry native work. Only fixed integer codes cross JNI. */
    if (error) (*env)->DeleteLocalRef(env, error);
    if (type) (*env)->DeleteLocalRef(env, type);
    if (!(*env)->ExceptionCheck(env)) bridge_failure(env);
}
static const jchar *component(JNIEnv *env, jstring name, jsize *length) {
    if ((*env)->ExceptionCheck(env)) return NULL;
    if (!name) { fail(env, PWP_ARGUMENT); return NULL; }
    *length = (*env)->GetStringLength(env, name);
    if ((*env)->ExceptionCheck(env)) return NULL;
    if (*length < 1 || *length > (jsize)PWP_COMPONENT_LIMIT) { fail(env, PWP_ARGUMENT); return NULL; }
    const jchar *chars = (*env)->GetStringChars(env, name, NULL);
    if (!chars) { bridge_failure(env); return NULL; }
    if ((*env)->ExceptionCheck(env)) { (*env)->ReleaseStringChars(env, name, chars); return NULL; }
    if (!pwp_component((const uint16_t *)chars, (size_t)*length)) {
        (*env)->ReleaseStringChars(env, name, chars); fail(env, PWP_ARGUMENT); return NULL;
    }
    return chars;
}
static jlongArray identity_array(JNIEnv *env, const uint64_t identity[PWP_IDENTITY_WORDS]) {
    if ((*env)->ExceptionCheck(env)) return NULL;
    jlongArray result = (*env)->NewLongArray(env, PWP_IDENTITY_WORDS);
    if (!result) { bridge_failure(env); return NULL; }
    if ((*env)->ExceptionCheck(env)) { (*env)->DeleteLocalRef(env, result); return NULL; }
    jlong words[PWP_IDENTITY_WORDS];
    memcpy(words, identity, sizeof(words)); /* Preserve unsigned/raw volume and file-ID bits exactly. */
    (*env)->SetLongArrayRegion(env, result, 0, PWP_IDENTITY_WORDS, words);
    pwp_clear(words, sizeof(words));
    if ((*env)->ExceptionCheck(env)) { (*env)->DeleteLocalRef(env, result); return NULL; }
    return result;
}
JNIEXPORT jint JNICALL JNI_NAME(abi)(JNIEnv *env, jobject instance) {
    (void)env; (void)instance; return PWP_CUSTODY_ABI;
}
JNIEXPORT jlong JNICALL JNI_NAME(capabilities)(JNIEnv *env, jobject instance) {
    /* Root custody, handle readback, cleanup only. No full lock/mutation/durability claims. */
    (void)env; (void)instance; return 0x43;
}
JNIEXPORT jlong JNICALL JNI_NAME(openRoot)(JNIEnv *env, jobject instance) {
    (void)instance;
    if ((*env)->ExceptionCheck(env)) return 0;
    uint64_t handle = 0;
    pwp_result r = pwp_win_open_root(&handle); fail(env, r); return r == PWP_OK ? (jlong)handle : 0;
}
JNIEXPORT jlong JNICALL JNI_NAME(child)(JNIEnv *env, jobject instance, jlong parent, jstring name) {
    (void)instance;
    if ((*env)->ExceptionCheck(env)) return 0;
    if (parent <= 0) { fail(env, PWP_ARGUMENT); return 0; }
    jsize length = 0; const jchar *chars = component(env, name, &length); if (!chars) return 0;
    uint64_t handle = 0;
    pwp_result r = pwp_win_child((uint64_t)parent, (const uint16_t *)chars, (size_t)length, &handle);
    (*env)->ReleaseStringChars(env, name, chars); fail(env, r); return r == PWP_OK ? (jlong)handle : 0;
}
JNIEXPORT jlong JNICALL JNI_NAME(createChildDirectory)(JNIEnv *env, jobject instance,
                                                       jlong parent, jstring name) {
    (void)instance;
    if ((*env)->ExceptionCheck(env)) return 0;
    if (parent <= 0) { fail(env, PWP_ARGUMENT); return 0; }
    jsize length = 0; const jchar *chars = component(env, name, &length); if (!chars) return 0;
    uint64_t handle = 0;
    pwp_result r = pwp_win_create_child((uint64_t)parent, (const uint16_t *)chars, (size_t)length, &handle);
    (*env)->ReleaseStringChars(env, name, chars); fail(env, r); return r == PWP_OK ? (jlong)handle : 0;
}
JNIEXPORT jlongArray JNICALL JNI_NAME(identity)(JNIEnv *env, jobject instance, jlong handle) {
    (void)instance;
    if ((*env)->ExceptionCheck(env)) return NULL;
    if (handle <= 0) { fail(env, PWP_ARGUMENT); return NULL; }
    uint64_t identity[PWP_IDENTITY_WORDS];
    pwp_result r = pwp_win_identity((uint64_t)handle, identity); fail(env, r); if (r != PWP_OK) return NULL;
    jlongArray result = identity_array(env, identity);
    pwp_clear(identity, sizeof(identity));
    return result;
}
JNIEXPORT jlongArray JNICALL JNI_NAME(fileIdentity)(JNIEnv *env, jobject instance,
                                                    jlong directory, jstring name) {
    (void)instance;
    if ((*env)->ExceptionCheck(env)) return NULL;
    if (directory <= 0) { fail(env, PWP_ARGUMENT); return NULL; }
    jsize length = 0; const jchar *chars = component(env, name, &length); if (!chars) return NULL;
    uint64_t identity[PWP_IDENTITY_WORDS];
    pwp_result r = pwp_win_file_identity((uint64_t)directory, (const uint16_t *)chars, (size_t)length, identity);
    (*env)->ReleaseStringChars(env, name, chars); fail(env, r); if (r != PWP_OK) return NULL;
    jlongArray result = identity_array(env, identity);
    pwp_clear(identity, sizeof(identity));
    return result;
}
JNIEXPORT jboolean JNICALL JNI_NAME(exists)(JNIEnv *env, jobject instance, jlong directory, jstring name) {
    (void)instance;
    if ((*env)->ExceptionCheck(env)) return JNI_FALSE;
    if (directory <= 0) { fail(env, PWP_ARGUMENT); return JNI_FALSE; }
    jsize length = 0; const jchar *chars = component(env, name, &length); if (!chars) return JNI_FALSE;
    int exists = 0;
    pwp_result r = pwp_win_exists((uint64_t)directory, (const uint16_t *)chars, (size_t)length, &exists);
    (*env)->ReleaseStringChars(env, name, chars); fail(env, r);
    return r == PWP_OK && exists == 1 ? JNI_TRUE : JNI_FALSE;
}
typedef struct { JNIEnv *env; jobjectArray result; } pwp_jni_names;
static pwp_result receive_names(const pwp_directory_names *names, void *opaque) {
    pwp_jni_names *output = opaque; JNIEnv *env = output->env;
    if (!names || names->count > PWP_DIRECTORY_LIMIT) return PWP_LIMIT;
    for (size_t i = 0; i < names->count; ++i)
        if (names->lengths[i] > PWP_COMPONENT_LIMIT || !pwp_component(names->names[i], names->lengths[i]))
            return PWP_POLICY;
    jclass string = (*env)->FindClass(env, "java/lang/String");
    if (!string) return PWP_OS;
    if ((*env)->ExceptionCheck(env)) { (*env)->DeleteLocalRef(env, string); return PWP_OS; }
    jobjectArray result = (*env)->NewObjectArray(env, (jsize)names->count, string, NULL);
    (*env)->DeleteLocalRef(env, string);
    if (!result) return PWP_OS;
    if ((*env)->ExceptionCheck(env)) goto failed;
    for (size_t i = 0; i < names->count; ++i) {
        jstring value = (*env)->NewString(env, (const jchar *)names->names[i], names->lengths[i]);
        if (!value) goto failed;
        if ((*env)->ExceptionCheck(env)) { (*env)->DeleteLocalRef(env, value); goto failed; }
        (*env)->SetObjectArrayElement(env, result, (jsize)i, value);
        (*env)->DeleteLocalRef(env, value);
        if ((*env)->ExceptionCheck(env)) goto failed;
    }
    output->result = result;
    return PWP_OK;
failed:
    (*env)->DeleteLocalRef(env, result);
    return PWP_OS;
}
JNIEXPORT jobjectArray JNICALL JNI_NAME(names)(JNIEnv *env, jobject instance, jlong directory) {
    (void)instance;
    if ((*env)->ExceptionCheck(env)) return NULL;
    if (directory <= 0) { fail(env, PWP_ARGUMENT); return NULL; }
    pwp_jni_names output = {env, NULL};
    pwp_result r = pwp_win_names((uint64_t)directory, receive_names, &output);
    fail(env, r);
    return r == PWP_OK && !(*env)->ExceptionCheck(env) ? output.result : NULL;
}
typedef struct { JNIEnv *env; jbyteArray result; size_t maximum; } pwp_jni_read;
static pwp_result receive_bytes(unsigned char *bytes, size_t count, void *opaque) {
    pwp_jni_read *output = opaque; JNIEnv *env = output->env;
    if ((!bytes && count) || count > output->maximum || count > PWP_RECORD_LIMIT) return PWP_LIMIT;
    jbyteArray result = (*env)->NewByteArray(env, (jsize)count);
    if (!result) return PWP_OS;
    if (!(*env)->ExceptionCheck(env) && count)
        (*env)->SetByteArrayRegion(env, result, 0, (jsize)count, (const jbyte *)bytes);
    if ((*env)->ExceptionCheck(env)) { (*env)->DeleteLocalRef(env, result); return PWP_OS; }
    output->result = result;
    return PWP_OK;
}
JNIEXPORT jbyteArray JNICALL JNI_NAME(read)(JNIEnv *env, jobject instance,
                                           jlong directory, jstring name, jint maximum) {
    (void)instance;
    if ((*env)->ExceptionCheck(env)) return NULL;
    if (directory <= 0 || maximum < 0 || maximum > (jint)PWP_RECORD_LIMIT) { fail(env, PWP_ARGUMENT); return NULL; }
    jsize length = 0; const jchar *chars = component(env, name, &length); if (!chars) return NULL;
    pwp_jni_read output = {env, NULL, (size_t)maximum};
    pwp_result r = pwp_win_read((uint64_t)directory, (const uint16_t *)chars, (size_t)length,
                                (size_t)maximum, receive_bytes, &output);
    (*env)->ReleaseStringChars(env, name, chars); fail(env, r);
    return r == PWP_OK && !(*env)->ExceptionCheck(env) ? output.result : NULL;
}
JNIEXPORT jlong JNICALL JNI_NAME(lockExisting)(JNIEnv *env, jobject instance, jlong directory, jstring name) {
    (void)instance;
    if ((*env)->ExceptionCheck(env)) return 0;
    if (directory <= 0) { fail(env, PWP_ARGUMENT); return 0; }
    jsize length = 0; const jchar *chars = component(env, name, &length); if (!chars) return 0;
    uint64_t handle = 0;
    pwp_result r = pwp_win_lock((uint64_t)directory, (const uint16_t *)chars, (size_t)length, &handle);
    (*env)->ReleaseStringChars(env, name, chars); fail(env, r); return r == PWP_OK ? (jlong)handle : 0;
}
JNIEXPORT jlong JNICALL JNI_NAME(createProfileLock)(JNIEnv *env, jobject instance, jlong root) {
    (void)instance;
    if ((*env)->ExceptionCheck(env)) return 0;
    if (root <= 0) { fail(env, PWP_ARGUMENT); return 0; }
    uint64_t handle = 0;
    pwp_result r = pwp_win_create_profile_lock((uint64_t)root, &handle);
    fail(env, r); return r == PWP_OK ? (jlong)handle : 0;
}
JNIEXPORT jlong JNICALL JNI_NAME(createVaultLock)(JNIEnv *env, jobject instance, jlong directory) {
    (void)instance;
    if ((*env)->ExceptionCheck(env)) return 0;
    if (directory <= 0) { fail(env, PWP_ARGUMENT); return 0; }
    uint64_t handle = 0;
    pwp_result r = pwp_win_create_vault_lock((uint64_t)directory, &handle);
    fail(env, r); return r == PWP_OK ? (jlong)handle : 0;
}
typedef struct { JNIEnv *env; jbyteArray ciphertext; size_t count; } pwp_jni_record;
static pwp_result copy_ciphertext(unsigned char *bytes, size_t count, void *opaque) {
    pwp_jni_record *input = opaque; JNIEnv *env = input->env;
    if (count != input->count || (!bytes && count) || count > PWP_RECORD_LIMIT) return PWP_ARGUMENT;
    if (count) (*env)->GetByteArrayRegion(env, input->ciphertext, 0, (jsize)count, (jbyte *)bytes);
    return (*env)->ExceptionCheck(env) ? PWP_OS : PWP_OK;
}
JNIEXPORT jlong JNICALL JNI_NAME(stageRecord)(JNIEnv *env, jobject instance,
                                               jlong directory, jstring name, jbyteArray ciphertext) {
    (void)instance;
    if ((*env)->ExceptionCheck(env)) return 0;
    if (directory <= 0 || !ciphertext) { fail(env, PWP_ARGUMENT); return 0; }
    jsize count = (*env)->GetArrayLength(env, ciphertext);
    if ((*env)->ExceptionCheck(env)) return 0;
    if (count < 0 || count > (jsize)PWP_RECORD_LIMIT) { fail(env, PWP_ARGUMENT); return 0; }
    jsize length = 0; const jchar *chars = component(env, name, &length); if (!chars) return 0;
    if (!pwp_stage_name((const uint16_t *)chars, (size_t)length)) {
        (*env)->ReleaseStringChars(env, name, chars); fail(env, PWP_ARGUMENT); return 0;
    }
    pwp_jni_record input = {env, ciphertext, (size_t)count}; uint64_t handle = 0;
    pwp_result r = pwp_win_stage((uint64_t)directory, (const uint16_t *)chars, (size_t)length,
                                 (size_t)count, copy_ciphertext, &input, &handle);
    (*env)->ReleaseStringChars(env, name, chars); fail(env, r);
    return r == PWP_OK && !(*env)->ExceptionCheck(env) ? (jlong)handle : 0;
}
JNIEXPORT jlong JNICALL JNI_NAME(prepareRecord)(JNIEnv *env, jobject instance,
                                                 jlong directory, jstring name, jbyteArray ciphertext) {
    (void)instance;
    if ((*env)->ExceptionCheck(env)) return 0;
    if (directory <= 0 || !ciphertext) { fail(env, PWP_ARGUMENT); return 0; }
    jsize count = (*env)->GetArrayLength(env, ciphertext);
    if ((*env)->ExceptionCheck(env)) return 0;
    if (count < 0 || count > (jsize)PWP_RECORD_LIMIT) { fail(env, PWP_ARGUMENT); return 0; }
    jsize length = 0; const jchar *chars = component(env, name, &length); if (!chars) return 0;
    if (!pwp_candidate_name((const uint16_t *)chars, (size_t)length)) {
        (*env)->ReleaseStringChars(env, name, chars); fail(env, PWP_ARGUMENT); return 0;
    }
    pwp_jni_record input = {env, ciphertext, (size_t)count}; uint64_t handle = 0;
    /* Persistent uncommitted owner, not a disposable stage or completed write. Copy/zero/free are native-owned. */
    pwp_result r = pwp_win_prepare_record((uint64_t)directory, (const uint16_t *)chars, (size_t)length,
                                          (size_t)count, copy_ciphertext, &input, &handle);
    (*env)->ReleaseStringChars(env, name, chars); fail(env, r);
    return r == PWP_OK && !(*env)->ExceptionCheck(env) ? (jlong)handle : 0;
}
JNIEXPORT void JNICALL JNI_NAME(renameCandidate)(JNIEnv *env, jobject instance, jlong candidate, jstring name) {
    (void)instance;
    if ((*env)->ExceptionCheck(env)) return;
    if (candidate <= 0) { fail(env, PWP_ARGUMENT); return; }
    jsize length = 0; const jchar *chars = component(env, name, &length); if (!chars) return;
    /* Syntax only: the original native owner/role ledger, never a JVM argument, establishes the actual scope. */
    if (!pwp_candidate_target((const uint16_t *)chars, (size_t)length, 0) &&
        !pwp_candidate_target((const uint16_t *)chars, (size_t)length, 1)) {
        (*env)->ReleaseStringChars(env, name, chars); fail(env, PWP_ARGUMENT); return;
    }
    pwp_result r = pwp_win_rename_candidate((uint64_t)candidate, (const uint16_t *)chars, (size_t)length);
    /* No commit receipt, automatic close, discard or retry; native uncertainty retains its original owner. */
    (*env)->ReleaseStringChars(env, name, chars); fail(env, r);
}
JNIEXPORT void JNICALL JNI_NAME(syncDirectory)(JNIEnv *env, jobject instance, jlong directory) {
    (void)instance;
    if ((*env)->ExceptionCheck(env)) return;
    if (directory <= 0) { fail(env, PWP_ARGUMENT); return; }
    /* No path reopen, allocation, commit promotion, retry or automatic retirement at this boundary. */
    fail(env, pwp_win_sync_directory((uint64_t)directory));
}
JNIEXPORT void JNICALL JNI_NAME(discardStage)(JNIEnv *env, jobject instance, jlong stage) {
    (void)instance;
    if ((*env)->ExceptionCheck(env)) return;
    if (stage <= 0) { fail(env, PWP_ARGUMENT); return; }
    fail(env, pwp_win_discard_stage((uint64_t)stage));
}
JNIEXPORT void JNICALL JNI_NAME(requestExpectedFileDeletion)(JNIEnv *env, jobject instance,
                                                               jlong directory, jstring name, jlongArray expected) {
    (void)instance;
    if ((*env)->ExceptionCheck(env)) return;
    if (directory <= 0 || !expected) { fail(env, PWP_ARGUMENT); return; }
    jsize count = (*env)->GetArrayLength(env, expected);
    if ((*env)->ExceptionCheck(env)) return;
    if (count != PWP_IDENTITY_WORDS) {
        fail(env, PWP_ARGUMENT); return;
    }
    jlong input[PWP_IDENTITY_WORDS] = {0}; uint64_t words[PWP_IDENTITY_WORDS] = {0};
    (*env)->GetLongArrayRegion(env, expected, 0, PWP_IDENTITY_WORDS, input);
    if ((*env)->ExceptionCheck(env)) { pwp_clear(input, sizeof(input)); return; }
    for (size_t i = 0; i < PWP_IDENTITY_WORDS; ++i) words[i] = (uint64_t)input[i];
    pwp_clear(input, sizeof(input));
    if (!pwp_expected_file(words, PWP_IDENTITY_WORDS, words[1])) {
        pwp_clear(words, sizeof(words)); fail(env, PWP_ARGUMENT); return;
    }
    jsize length = 0; const jchar *chars = component(env, name, &length);
    if (!chars) { pwp_clear(words, sizeof(words)); return; }
    pwp_result r = pwp_win_request_delete((uint64_t)directory, (const uint16_t *)chars,
                                          (size_t)length, words, PWP_IDENTITY_WORDS);
    (*env)->ReleaseStringChars(env, name, chars); pwp_clear(words, sizeof(words)); fail(env, r);
}
JNIEXPORT void JNICALL JNI_NAME(close)(JNIEnv *env, jobject instance, jlong handle) {
    (void)instance;
    if ((*env)->ExceptionCheck(env)) return;
    if (handle <= 0) { fail(env, PWP_ARGUMENT); return; }
    fail(env, pwp_win_close((uint64_t)handle));
}
