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
    (void)env; (void)instance; return PWP_CUSTODY_ABI;
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
JNIEXPORT jlongArray JNICALL JNI_NAME(fileIdentity)(JNIEnv *env, jobject instance,
                                                    jlong directory, jstring name) {
    (void)instance;
    if (directory <= 0) { fail(env, PWP_ARGUMENT); return NULL; }
    jsize length = 0; const jchar *chars = component(env, name, &length); if (!chars) return NULL;
    uint64_t identity[6];
    pwp_result r = pwp_win_file_identity((uint64_t)directory, (const uint16_t *)chars, (size_t)length, identity);
    (*env)->ReleaseStringChars(env, name, chars); fail(env, r); if (r != PWP_OK) return NULL;
    jlongArray result = (*env)->NewLongArray(env, 6);
    if (result) {
        jlong words[6]; for (size_t i = 0; i < 6; ++i) words[i] = (jlong)identity[i];
        (*env)->SetLongArrayRegion(env, result, 0, 6, words);
    }
    return result;
}
JNIEXPORT jboolean JNICALL JNI_NAME(exists)(JNIEnv *env, jobject instance, jlong directory, jstring name) {
    (void)instance;
    if (directory <= 0) { fail(env, PWP_ARGUMENT); return JNI_FALSE; }
    jsize length = 0; const jchar *chars = component(env, name, &length); if (!chars) return JNI_FALSE;
    int exists = 0;
    pwp_result r = pwp_win_exists((uint64_t)directory, (const uint16_t *)chars, (size_t)length, &exists);
    (*env)->ReleaseStringChars(env, name, chars); fail(env, r);
    return r == PWP_OK && exists == 1 ? JNI_TRUE : JNI_FALSE;
}
JNIEXPORT jobjectArray JNICALL JNI_NAME(names)(JNIEnv *env, jobject instance, jlong directory) {
    (void)instance;
    if (directory <= 0) { fail(env, PWP_ARGUMENT); return NULL; }
    pwp_directory_names *names = calloc(1, sizeof(*names));
    if (!names) { fail(env, PWP_LIMIT); return NULL; }
    pwp_result r = pwp_win_names((uint64_t)directory, names);
    if (r == PWP_OK && names->count > PWP_DIRECTORY_LIMIT) r = PWP_LIMIT;
    jobjectArray result = NULL;
    if (r == PWP_OK) {
        jclass string = (*env)->FindClass(env, "java/lang/String");
        if (string) {
            result = (*env)->NewObjectArray(env, (jsize)names->count, string, NULL);
            (*env)->DeleteLocalRef(env, string);
        }
        for (size_t i = 0; result && i < names->count && !(*env)->ExceptionCheck(env); ++i) {
            if (names->lengths[i] > PWP_COMPONENT_LIMIT ||
                !pwp_component(names->names[i], names->lengths[i])) { r = PWP_POLICY; break; }
            jstring value = (*env)->NewString(env, (const jchar *)names->names[i], names->lengths[i]);
            if (!value) break;
            (*env)->SetObjectArrayElement(env, result, (jsize)i, value);
            (*env)->DeleteLocalRef(env, value);
        }
    }
    pwp_clear(names, sizeof(*names)); free(names); fail(env, r);
    return r == PWP_OK && !(*env)->ExceptionCheck(env) ? result : NULL;
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
JNIEXPORT jlong JNICALL JNI_NAME(stageRecord)(JNIEnv *env, jobject instance,
                                               jlong directory, jstring name, jbyteArray ciphertext) {
    (void)instance;
    if (directory <= 0 || !ciphertext) { fail(env, PWP_ARGUMENT); return 0; }
    jsize count = (*env)->GetArrayLength(env, ciphertext);
    if (count < 0 || count > (jsize)PWP_RECORD_LIMIT) { fail(env, PWP_ARGUMENT); return 0; }
    jsize length = 0; const jchar *chars = component(env, name, &length); if (!chars) return 0;
    if (!pwp_stage_name((const uint16_t *)chars, (size_t)length)) {
        (*env)->ReleaseStringChars(env, name, chars); fail(env, PWP_ARGUMENT); return 0;
    }
    unsigned char *buffer = count ? malloc((size_t)count) : NULL;
    if (count && !buffer) {
        (*env)->ReleaseStringChars(env, name, chars); fail(env, PWP_LIMIT); return 0;
    }
    if (count) (*env)->GetByteArrayRegion(env, ciphertext, 0, count, (jbyte *)buffer);
    uint64_t handle = 0; pwp_result r = PWP_OS;
    if (!(*env)->ExceptionCheck(env))
        r = pwp_win_stage((uint64_t)directory, (const uint16_t *)chars, (size_t)length,
                           buffer, (size_t)count, &handle);
    pwp_clear(buffer, (size_t)count); free(buffer);
    (*env)->ReleaseStringChars(env, name, chars); fail(env, r); return r == PWP_OK ? (jlong)handle : 0;
}
JNIEXPORT void JNICALL JNI_NAME(discardStage)(JNIEnv *env, jobject instance, jlong stage) {
    (void)instance;
    if (stage <= 0) { fail(env, PWP_ARGUMENT); return; }
    fail(env, pwp_win_discard_stage((uint64_t)stage));
}
JNIEXPORT void JNICALL JNI_NAME(close)(JNIEnv *env, jobject instance, jlong handle) {
    (void)instance;
    if (handle <= 0) { fail(env, PWP_ARGUMENT); return; }
    fail(env, pwp_win_close((uint64_t)handle));
}
