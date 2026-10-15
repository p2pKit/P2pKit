#include "profile_jni_registration.h"
#include <stdlib.h>

#ifdef _WIN32
#include <windows.h>
static volatile LONG registration_reserved;
static int reserve_registration(void) {
    return InterlockedCompareExchange(&registration_reserved, 1, 0) == 0;
}
#else
#include <stdatomic.h>
static atomic_flag registration_reserved = ATOMIC_FLAG_INIT;
static int reserve_registration(void) {
    return !atomic_flag_test_and_set_explicit(&registration_reserved, memory_order_acq_rel);
}
#endif

_Static_assert(sizeof(pwp_jni_registration_report) == 32, "Registration report is exactly 32 bytes");
_Static_assert(sizeof(uintptr_t) == 8, "Only 64-bit registration is supported");
#ifdef JNI_VERSION_21
_Static_assert(PWP_JNI_RUNTIME_VERSION == JNI_VERSION_21, "Exact JDK21 JNI version required");
#endif

/* Only the one reserved invocation writes these. The VM owns the reference handles; this component
 * intentionally owns their lifetime through process exit, even after failed/partial registration.
 * External loader ownership, not these references, must keep the native module/runtime loaded. */
static jclass retained_class;
static jthrowable retained_failure;
static jthrowable retained_cleanup_failure;

static void clear_pending(JNIEnv *env) {
    (*env)->ExceptionClear(env);
    if ((*env)->ExceptionCheck(env)) {
        (*env)->FatalError(env, "Windows JNI registration could not clear pending exception");
        abort(); /* A broken JNI vtable must not return an exception through FFM. */
    }
}

static void retain_pending(JNIEnv *env, pwp_jni_registration_report *report) {
    if (!(*env)->ExceptionCheck(env)) return;
    int first = !report->exception_observed;
    report->exception_observed = 1;
    jthrowable original = (*env)->ExceptionOccurred(env);
    clear_pending(env);
    jthrowable retained = original ? (jthrowable)(*env)->NewGlobalRef(env, original) : NULL;
    int secondary = (*env)->ExceptionCheck(env);
    if (secondary) clear_pending(env);
    if (original) (*env)->DeleteLocalRef(env, original);
    if (first) {
        retained_failure = retained;
        report->exception_retained = retained != NULL;
    } else {
        retained_cleanup_failure = retained;
    }
    if (!retained || secondary) {
        report->retention_uncertain = 1;
        report->result = PWP_JNI_REGISTER_RETENTION_UNKNOWN;
    }
}

int32_t pwp_jni_register_once(JavaVM *expected_vm, const uintptr_t *expected_entry_points,
                            uint32_t entry_count, pwp_jni_registration_report *report, uint32_t report_bytes) {
    if (!report || report_bytes != sizeof(*report)) return PWP_JNI_REGISTER_ARGUMENT;
    *report = (pwp_jni_registration_report){sizeof(*report), 1, 0, PWP_JNI_REGISTER_ARGUMENT, 0, 0, 0, 0};
    if (!expected_vm || !expected_entry_points || entry_count != PWP_JNI_METHOD_COUNT) return report->result;
    if (!reserve_registration()) {
        report->result = PWP_JNI_REGISTER_DUPLICATE;
        return report->result;
    }
    /* Read each expected slot once. Registration uses only our original compiled const table, not
     * these observations, including after class initialization/reentrant Java code has run. */
    for (uint32_t i = 0; i < PWP_JNI_METHOD_COUNT; ++i) {
        uintptr_t observed = expected_entry_points[i];
        if (!observed || observed != (uintptr_t)pwp_jni_methods[i].fnPtr) {
            report->result = PWP_JNI_REGISTER_ADDRESS;
            return report->result;
        }
    }
    JNIEnv *env = NULL;
    report->result = PWP_JNI_REGISTER_THREAD;
    if ((*expected_vm)->GetEnv(expected_vm, (void **)&env, PWP_JNI_RUNTIME_VERSION) != JNI_OK || !env)
        return report->result; /* No attach, detach, VM creation, path or symbol lookup. */
    int frame = 0, registered = 0;
    report->result = PWP_JNI_REGISTER_EXCEPTION;
    if ((*env)->ExceptionCheck(env)) goto finish;
    report->result = PWP_JNI_REGISTER_RUNTIME;
    if ((*env)->GetVersion(env) != PWP_JNI_RUNTIME_VERSION || (*env)->ExceptionCheck(env)) goto finish;
    JavaVM *actual_vm = NULL;
    if ((*env)->GetJavaVM(env, &actual_vm) != JNI_OK || actual_vm != expected_vm ||
        (*env)->ExceptionCheck(env)) goto finish;
    report->result = PWP_JNI_REGISTER_EXCEPTION;
    if ((*env)->PushLocalFrame(env, 16) != JNI_OK) goto finish;
    frame = 1;
    if ((*env)->ExceptionCheck(env)) goto finish;

    /* FindClass is restricted to bootstrap java.lang classes. The application class always comes
     * from the actual system loader, never the incidental FFM/native caller's FindClass context. */
    report->result = PWP_JNI_REGISTER_CLASS;
    jclass loader_type = (*env)->FindClass(env, "java/lang/ClassLoader");
    if (!loader_type || (*env)->ExceptionCheck(env)) goto finish;
    jmethodID system_method = (*env)->GetStaticMethodID(env, loader_type, "getSystemClassLoader",
                                                     "()Ljava/lang/ClassLoader;");
    if (!system_method || (*env)->ExceptionCheck(env)) goto finish;
    jobject loader = (*env)->CallStaticObjectMethodA(env, loader_type, system_method, NULL);
    if (!loader || (*env)->ExceptionCheck(env)) goto finish;
    jclass class_type = (*env)->FindClass(env, "java/lang/Class");
    if (!class_type || (*env)->ExceptionCheck(env)) goto finish;
    /* Class.forName enforces the requested binary name even with a custom system loader; calling
     * an overridable ClassLoader.loadClass directly would not establish that relationship. */
    jmethodID load_method = (*env)->GetStaticMethodID(env, class_type, "forName",
                                                   "(Ljava/lang/String;ZLjava/lang/ClassLoader;)Ljava/lang/Class;");
    if (!load_method || (*env)->ExceptionCheck(env)) goto finish;
    jstring name = (*env)->NewStringUTF(env, "dev.p2pkit.sample.rpc.profile.WindowsProfileCustodyJni");
    if (!name || (*env)->ExceptionCheck(env)) goto finish;
    jvalue arguments[3]; arguments[0].l = name; arguments[1].z = JNI_FALSE; arguments[2].l = loader;
    jclass target = (jclass)(*env)->CallStaticObjectMethodA(env, class_type, load_method, arguments);
    if (!target || (*env)->ExceptionCheck(env)) goto finish;
    jmethodID owner_method = (*env)->GetMethodID(env, class_type, "getClassLoader", "()Ljava/lang/ClassLoader;");
    if (!owner_method || (*env)->ExceptionCheck(env)) goto finish;
    jobject owner = (*env)->CallObjectMethodA(env, target, owner_method, NULL);
    if ((*env)->ExceptionCheck(env) || !(*env)->IsSameObject(env, loader, owner)) goto finish;
    report->result = PWP_JNI_REGISTER_METHOD;
    for (uint32_t i = 0; i < PWP_JNI_METHOD_COUNT; ++i) {
        if (!(*env)->GetMethodID(env, target, pwp_jni_methods[i].name, pwp_jni_methods[i].signature) ||
            (*env)->ExceptionCheck(env)) goto finish;
    }
    report->result = PWP_JNI_REGISTER_RETENTION_UNKNOWN;
    retained_class = (jclass)(*env)->NewGlobalRef(env, target);
    report->class_retained = retained_class != NULL;
    if (!retained_class || (*env)->ExceptionCheck(env)) {
        report->retention_uncertain = 1;
        goto finish;
    }
    /* RegisterNatives is not atomic. The retained class and external module owner MUST predate even
     * the first binding. Once here, failure means possible cached native addresses forever. */
    report->phase = 1;
    report->result = PWP_JNI_REGISTER_FAILED;
    registered = (*env)->RegisterNatives(env, target, pwp_jni_methods, PWP_JNI_METHOD_COUNT) == JNI_OK;
    if ((*env)->ExceptionCheck(env)) registered = 0;
finish:
    retain_pending(env, report);
    if (frame) {
        (*env)->PopLocalFrame(env, NULL);
        if ((*env)->ExceptionCheck(env)) {
            if (registered) report->result = PWP_JNI_REGISTER_EXCEPTION;
            registered = 0;
            retain_pending(env, report);
        }
    }
    if (registered && !report->exception_observed && !report->retention_uncertain) {
        report->phase = 2;
        report->result = PWP_JNI_REGISTER_OK;
    }
    return report->result;
}
