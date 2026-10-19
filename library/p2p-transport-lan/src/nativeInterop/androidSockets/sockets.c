#include <errno.h>
#include <fcntl.h>
#include <jni.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

/* No blocking calls, retry loops, Java fields, process routing, or retained native pointers. */
JNIEXPORT jint JNICALL Java_dev_p2pkit_transport_lan_AndroidNativeSockets_open(
    JNIEnv *env, jobject self, jboolean ipv6) {
    (void)env;
    (void)self;
    int fd = socket(ipv6 ? AF_INET6 : AF_INET,
        SOCK_STREAM | SOCK_NONBLOCK | SOCK_CLOEXEC, IPPROTO_TCP);
    return fd < 0 ? -errno : fd;
}

JNIEXPORT jint JNICALL Java_dev_p2pkit_transport_lan_AndroidNativeSockets_accept(
    JNIEnv *env, jobject self, jint listener) {
    (void)env;
    (void)self;
    int fd = accept4(listener, NULL, NULL, SOCK_NONBLOCK | SOCK_CLOEXEC);
    return fd < 0 ? -errno : fd;
}

JNIEXPORT jint JNICALL Java_dev_p2pkit_transport_lan_AndroidNativeSockets_verifyFlags(
    JNIEnv *env, jobject self, jint fd) {
    (void)env;
    (void)self;
    int status = fcntl(fd, F_GETFL);
    if (status < 0) return -errno;
    int descriptor = fcntl(fd, F_GETFD);
    if (descriptor < 0) return -errno;
    return (status & O_NONBLOCK) && (descriptor & FD_CLOEXEC) ? 0 : -EINVAL;
}

/* Only the unpublished integer, if ParcelFileDescriptor.adoptFd fails. Never retry close on Linux. */
JNIEXPORT jint JNICALL Java_dev_p2pkit_transport_lan_AndroidNativeSockets_closeUnowned(
    JNIEnv *env, jobject self, jint fd) {
    (void)env;
    (void)self;
    return close(fd) == 0 ? 0 : -errno;
}
