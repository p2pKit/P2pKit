#include "profile_win32.h"
#include <jni.h>
#include <stdlib.h>
#include <stdio.h>

#define JNI_NAME(name) Java_dev_p2pkit_sample_rpc_profile_WindowsProfileCustodyJni_##name
static void fail(JNIEnv *env, pwp_result result) {
    if (result == PWP_OK || (*env)->ExceptionCheck(env)) return;
    jclass error = (*env)->FindClass(env, "java/io/IOException");
    if (!error) return;
    char message[80];
    (void)snprintf(message, sizeof(message), "Windows profile custody rejected (code %d)", (int)result);
    (*env)->ThrowNew(env, error, message);
    (*env)->DeleteLocalRef(env, error);
}
static const jchar *component(JNIEnv *env, jstring name, jsize *length) {
    if (!name) { fail(env, PWP_ARGUMENT); return NULL; }
    *length = (*env)->GetStringLength(env, name);
    if (*length < 1 || *length > (jsize)PWP_COMPONENT_LIMIT) { fail(env, PWP_ARGUMENT); return NULL; }
    const jchar *chars = (*env)->GetStringChars(env, name, NULL);
    if (!chars) return NULL;
    if (!pwp_component((const uint16_t *)chars, (size_t)*length)) {
        (*env)->ReleaseStringChars(env, name, chars); fail(env, PWP_ARGUMENT); return NULL;
    }
    return chars;
}
JNIEXPORT jint JNICALL JNI_NAME(abi)(JNIEnv *env, jobject instance) {
    (void)env; (void)instance; return 1;
}
JNIEXPORT jlong JNICALL JNI_NAME(capabilities)(JNIEnv *env, jobject instance) {
    /* Root custody, handle readback, cleanup only. No full lock/mutation/durability claims. */
    (void)env; (void)instance; return 0x43;
}
JNIEXPORT jlong JNICALL JNI_NAME(openRoot)(JNIEnv *env, jobject instance) {
    (void)instance; uint64_t handle = 0;
    pwp_result r = pwp_win_open_root(&handle); fail(env, r); return r == PWP_OK ? (jlong)handle : 0;
}
JNIEXPORT jlong JNICALL JNI_NAME(child)(JNIEnv *env, jobject instance, jlong parent, jstring name) {
    (void)instance;
    if (parent <= 0) { fail(env, PWP_ARGUMENT); return 0; }
    jsize length = 0; const jchar *chars = component(env, name, &length); if (!chars) return 0;
    uint64_t handle = 0;
    pwp_result r = pwp_win_child((uint64_t)parent, (const uint16_t *)chars, (size_t)length, &handle);
    (*env)->ReleaseStringChars(env, name, chars); fail(env, r); return r == PWP_OK ? (jlong)handle : 0;
}
JNIEXPORT jlongArray JNICALL JNI_NAME(identity)(JNIEnv *env, jobject instance, jlong handle) {
    (void)instance;
    if (handle <= 0) { fail(env, PWP_ARGUMENT); return NULL; }
    uint64_t identity[6];
    pwp_result r = pwp_win_identity((uint64_t)handle, identity); fail(env, r); if (r != PWP_OK) return NULL;
    jlongArray result = (*env)->NewLongArray(env, 6);
    if (result) {
        jlong words[6]; for (size_t i = 0; i < 6; ++i) words[i] = (jlong)identity[i];
        (*env)->SetLongArrayRegion(env, result, 0, 6, words);
    }
    return result;
}
JNIEXPORT jbyteArray JNICALL JNI_NAME(read)(JNIEnv *env, jobject instance,
                                           jlong directory, jstring name, jint maximum) {
    (void)instance;
    if (directory <= 0 || maximum < 0 || maximum > (jint)PWP_RECORD_LIMIT) { fail(env, PWP_ARGUMENT); return NULL; }
    jsize length = 0; const jchar *chars = component(env, name, &length); if (!chars) return NULL;
    unsigned char *buffer = maximum ? malloc((size_t)maximum) : NULL;
    if (maximum && !buffer) {
        (*env)->ReleaseStringChars(env, name, chars); fail(env, PWP_LIMIT); return NULL;
    }
    size_t count = 0;
    pwp_result r = pwp_win_read((uint64_t)directory, (const uint16_t *)chars, (size_t)length,
                                buffer, (size_t)maximum, &count);
    (*env)->ReleaseStringChars(env, name, chars);
    jbyteArray result = NULL;
    if (r == PWP_OK && count <= (size_t)maximum) {
        result = (*env)->NewByteArray(env, (jsize)count);
        if (result && count) (*env)->SetByteArrayRegion(env, result, 0, (jsize)count, (const jbyte *)buffer);
    } else fail(env, r == PWP_OK ? PWP_LIMIT : r);
    pwp_clear(buffer, (size_t)maximum); free(buffer); return result;
}
JNIEXPORT jlong JNICALL JNI_NAME(lockExisting)(JNIEnv *env, jobject instance, jlong directory, jstring name) {
    (void)instance;
    if (directory <= 0) { fail(env, PWP_ARGUMENT); return 0; }
    jsize length = 0; const jchar *chars = component(env, name, &length); if (!chars) return 0;
    uint64_t handle = 0;
    pwp_result r = pwp_win_lock((uint64_t)directory, (const uint16_t *)chars, (size_t)length, &handle);
    (*env)->ReleaseStringChars(env, name, chars); fail(env, r); return r == PWP_OK ? (jlong)handle : 0;
}
JNIEXPORT void JNICALL JNI_NAME(close)(JNIEnv *env, jobject instance, jlong handle) {
    (void)instance;
    if (handle <= 0) { fail(env, PWP_ARGUMENT); return; }
    fail(env, pwp_win_close((uint64_t)handle));
}
