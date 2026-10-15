#include "p2pkit_bonjour.h"
#include <errno.h>
#include <jni.h>
#include <string.h>
#define JNI(name) Java_dev_p2pkit_transport_lan_MacBonjourNative_##name

JNIEXPORT jint JNICALL JNI(abi)(JNIEnv *env, jobject self) {
    (void)env; (void)self; return (jint)p2p_bonjour_abi();
}
JNIEXPORT jint JNICALL JNI(open)(JNIEnv *env, jobject self, jint index, jint operation, jint profile,
    jbyteArray name, jint port, jbyteArray txt, jlongArray output) {
    (void)self;
    if (output == NULL || (*env)->GetArrayLength(env, output) != 1) return EINVAL;
    jlong zero = 0; (*env)->SetLongArrayRegion(env, output, 0, 1, &zero);
    if ((*env)->ExceptionCheck(env) || index <= 0 || name == NULL || txt == NULL ||
        port < 0 || port > 65535) return EINVAL;
    jsize namesize = (*env)->GetArrayLength(env, name), txtsize = (*env)->GetArrayLength(env, txt);
    if (namesize > (jsize)P2P_BONJOUR_NAME || txtsize > (jsize)P2P_BONJOUR_TXT) return EINVAL;
    char namebytes[P2P_BONJOUR_NAME + 1] = {0};
    uint8_t txtbytes[P2P_BONJOUR_TXT] = {0};
    (*env)->GetByteArrayRegion(env, name, 0, namesize, (jbyte *)namebytes);
    if ((*env)->ExceptionCheck(env)) return EINVAL;
    if (memchr(namebytes, 0, (size_t)namesize) != NULL) return EINVAL;
    (*env)->GetByteArrayRegion(env, txt, 0, txtsize, (jbyte *)txtbytes);
    if ((*env)->ExceptionCheck(env)) return EINVAL;
    uint64_t handle = 0;
    int32_t result = p2p_bonjour_open((uint32_t)index, operation, profile, namebytes,
        (uint16_t)port, txtbytes, (uint32_t)txtsize, &handle);
    jlong owned = (jlong)handle;
    (*env)->SetLongArrayRegion(env, output, 0, 1, &owned);
    return result;
}
JNIEXPORT jint JNICALL JNI(poll)(JNIEnv *env, jobject self, jlong handle, jint timeout, jbyteArray output) {
    (void)self;
    if (output == NULL || (*env)->GetArrayLength(env, output) != (jsize)P2P_BONJOUR_FRAME) return -EINVAL;
    uint8_t frame[P2P_BONJOUR_FRAME];
    int32_t result = p2p_bonjour_poll((uint64_t)handle, timeout, frame);
    (*env)->SetByteArrayRegion(env, output, 0, P2P_BONJOUR_FRAME, (jbyte *)frame);
    return result;
}
JNIEXPORT jint JNICALL JNI(close)(JNIEnv *env, jobject self, jlong handle) {
    (void)env; (void)self; return p2p_bonjour_close((uint64_t)handle);
}
