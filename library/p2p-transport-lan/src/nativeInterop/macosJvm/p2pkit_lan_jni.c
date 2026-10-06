#include "p2pkit_lan_socket.h"
#include <errno.h>
#include <jni.h>
#include <string.h>
#ifndef P2P_LAN_BUILD_SOURCE
#error "The native library must be bound to a reviewed source commit"
#endif
#ifndef P2P_LAN_BUILD_TREE
#error "The native library must be bound to a reviewed source tree"
#endif
#define JNI(name) Java_dev_p2pkit_transport_lan_MacLanNative_##name
#define IGNORE_SELF (void)self

/* Volatile stores cannot be optimized away after the last JNI copy; no optional libc extension required. */
static void wipe(void *memory, size_t length) {
    volatile unsigned char *bytes = memory;
    while (length-- > 0) *bytes++ = 0;
}
static int valid_array(JNIEnv *env, jarray value, jsize expected) {
    return value != NULL && (*env)->GetArrayLength(env, value) == expected;
}
static int address(JNIEnv *env, jbyteArray bytes, uint8_t out[4]) {
    if (!valid_array(env, bytes, 4)) return 0;
    (*env)->GetByteArrayRegion(env, bytes, 0, 4, (jbyte *)out);
    return !(*env)->ExceptionCheck(env);
}
static int bounds(JNIEnv *env, jbyteArray bytes, jint offset, jint length) {
    return bytes != NULL && offset >= 0 && length > 0 && length <= (jint)P2P_LAN_SOCKET_MAX_BYTES &&
        offset <= (*env)->GetArrayLength(env, bytes) - length;
}
JNIEXPORT jint JNICALL JNI(abi)(JNIEnv *env, jobject self) {
    (void)env; IGNORE_SELF; return (jint)p2p_lan_socket_abi();
}
JNIEXPORT jstring JNICALL JNI(source)(JNIEnv *env, jobject self) {
    IGNORE_SELF; return (*env)->NewStringUTF(env, P2P_LAN_BUILD_SOURCE ":" P2P_LAN_BUILD_TREE);
}
JNIEXPORT jintArray JNICALL JNI(constants)(JNIEnv *env, jobject self) {
    IGNORE_SELF;
    const jint values[] = { EAGAIN, EWOULDBLOCK, EINTR, EINPROGRESS, EALREADY, ENOTCONN, EINVAL, EBADF };
    jintArray result = (*env)->NewIntArray(env, 8);
    if (result != NULL) (*env)->SetIntArrayRegion(env, result, 0, 8, values);
    return result;
}
JNIEXPORT jint JNICALL JNI(open)(JNIEnv *env, jobject self, jint index, jlongArray output) {
    IGNORE_SELF;
    if (!valid_array(env, output, 1)) return EINVAL;
    jlong cleared = 0; (*env)->SetLongArrayRegion(env, output, 0, 1, &cleared);
    if ((*env)->ExceptionCheck(env)) return EINVAL;
    uint64_t handle = 0;
    int32_t result = index > 0 ? p2p_lan_socket_open((uint32_t)index, &handle) : ENXIO;
    jlong owned = (jlong)handle;
    (*env)->SetLongArrayRegion(env, output, 0, 1, &owned);
    /* Ownership has a preallocated one-element output. No allocation follows native creation. */
    return result;
}
JNIEXPORT jint JNICALL JNI(bind)(JNIEnv *env, jobject self, jlong handle, jbyteArray bytes, jint port) {
    IGNORE_SELF; uint8_t ip[4];
    if (!address(env, bytes, ip) || port < 0 || port > 65535) return EINVAL;
    return p2p_lan_socket_bind((uint64_t)handle, ip, (uint16_t)port);
}
JNIEXPORT jint JNICALL JNI(listen)(JNIEnv *env, jobject self, jlong handle, jint backlog) {
    (void)env; IGNORE_SELF; return p2p_lan_socket_listen((uint64_t)handle, backlog);
}
JNIEXPORT jint JNICALL JNI(accept)(JNIEnv *env, jobject self, jlong handle, jlongArray output) {
    IGNORE_SELF;
    if (!valid_array(env, output, 1)) return EINVAL;
    jlong cleared = 0; (*env)->SetLongArrayRegion(env, output, 0, 1, &cleared);
    if ((*env)->ExceptionCheck(env)) return EINVAL;
    uint64_t child = 0;
    int32_t result = p2p_lan_socket_accept((uint64_t)handle, &child);
    jlong owned = (jlong)child;
    (*env)->SetLongArrayRegion(env, output, 0, 1, &owned);
    return result;
}
JNIEXPORT jint JNICALL JNI(connect)(JNIEnv *env, jobject self, jlong handle, jbyteArray bytes, jint port) {
    IGNORE_SELF; uint8_t ip[4];
    if (!address(env, bytes, ip) || port < 1 || port > 65535) return EINVAL;
    return p2p_lan_socket_connect((uint64_t)handle, ip, (uint16_t)port);
}
JNIEXPORT jint JNICALL JNI(connected)(JNIEnv *env, jobject self, jlong handle) {
    (void)env; IGNORE_SELF; return p2p_lan_socket_connected((uint64_t)handle);
}
JNIEXPORT jint JNICALL JNI(endpoint)(JNIEnv *env, jobject self, jlong handle, jint remote,
    jbyteArray bytes, jintArray port) {
    IGNORE_SELF;
    if (!valid_array(env, bytes, 4) || !valid_array(env, port, 1)) return EINVAL;
    uint8_t ip[4] = {0}; uint16_t actual = 0;
    int32_t result = p2p_lan_socket_endpoint((uint64_t)handle, remote, ip, &actual);
    jint actual_port = (jint)actual;
    (*env)->SetByteArrayRegion(env, bytes, 0, 4, (jbyte *)ip);
    if (!(*env)->ExceptionCheck(env)) (*env)->SetIntArrayRegion(env, port, 0, 1, &actual_port);
    return result;
}
JNIEXPORT jint JNICALL JNI(boundInterface)(JNIEnv *env, jobject self, jlong handle, jintArray output) {
    IGNORE_SELF;
    if (!valid_array(env, output, 1)) return EINVAL;
    uint32_t index = 0;
    int32_t result = p2p_lan_socket_bound_interface((uint64_t)handle, &index);
    jint actual = (jint)index;
    (*env)->SetIntArrayRegion(env, output, 0, 1, &actual);
    return result;
}
JNIEXPORT jint JNICALL JNI(option)(JNIEnv *env, jobject self, jlong handle, jint option, jint enabled) {
    (void)env; IGNORE_SELF; return p2p_lan_socket_option((uint64_t)handle, option, enabled);
}
JNIEXPORT jint JNICALL JNI(read)(JNIEnv *env, jobject self, jlong handle, jbyteArray bytes,
    jint offset, jint length) {
    IGNORE_SELF;
    if (!bounds(env, bytes, offset, length)) return -EINVAL;
    uint8_t buffer[P2P_LAN_SOCKET_MAX_BYTES]; uint32_t count = 0;
    int32_t result = p2p_lan_socket_read((uint64_t)handle, buffer, (uint32_t)length, &count);
    if (result == 0 && count != 0) (*env)->SetByteArrayRegion(env, bytes, offset, (jsize)count, (jbyte *)buffer);
    wipe(buffer, sizeof(buffer));
    return result == 0 ? (jint)count : -result;
}
JNIEXPORT jint JNICALL JNI(write)(JNIEnv *env, jobject self, jlong handle, jbyteArray bytes,
    jint offset, jint length) {
    IGNORE_SELF;
    if (!bounds(env, bytes, offset, length)) return -EINVAL;
    uint8_t buffer[P2P_LAN_SOCKET_MAX_BYTES]; uint32_t count = 0;
    (*env)->GetByteArrayRegion(env, bytes, offset, length, (jbyte *)buffer);
    int32_t result = (*env)->ExceptionCheck(env) ? EINVAL :
        p2p_lan_socket_write((uint64_t)handle, buffer, (uint32_t)length, &count);
    wipe(buffer, sizeof(buffer));
    return result == 0 ? (jint)count : -result;
}
JNIEXPORT jint JNICALL JNI(poll)(JNIEnv *env, jobject self, jlong handle, jint writable, jint timeout) {
    (void)env; IGNORE_SELF; int32_t ready = 0;
    int32_t result = p2p_lan_socket_poll((uint64_t)handle, writable, timeout, &ready);
    return result == 0 ? ready : -result;
}
JNIEXPORT jint JNICALL JNI(close)(JNIEnv *env, jobject self, jlong handle) {
    (void)env; IGNORE_SELF; return p2p_lan_socket_close((uint64_t)handle);
}
