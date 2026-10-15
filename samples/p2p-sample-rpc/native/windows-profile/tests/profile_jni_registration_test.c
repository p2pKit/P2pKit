/* Actual registrar with a mocked VM/vtable and inert table. No JVM, DLL, NTFS or native method executes.
 * Every invocation is a fresh process: no test-only reset exists in the real one-shot registrar. */
#include "../profile_jni_registration.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define REF(n) ((jobject)(uintptr_t)(n))
#define METHOD(n) ((jmethodID)(uintptr_t)(n))
/* Deliberately independent metadata oracle; these fnPtr values are data, never called. */
#define ENTRY(i, name, descriptor) {name, descriptor, (void *)(uintptr_t)(0x1000 + (i) * 16)}
const JNINativeMethod pwp_jni_methods[PWP_JNI_METHOD_COUNT] = {
    ENTRY(0, "abi", "()I"), ENTRY(1, "capabilities", "()J"), ENTRY(2, "openRoot", "()J"),
    ENTRY(3, "child", "(JLjava/lang/String;)J"), ENTRY(4, "createChildDirectory", "(JLjava/lang/String;)J"),
    ENTRY(5, "identity", "(J)[J"), ENTRY(6, "fileIdentity", "(JLjava/lang/String;)[J"),
    ENTRY(7, "exists", "(JLjava/lang/String;)Z"), ENTRY(8, "names", "(J)[Ljava/lang/String;"),
    ENTRY(9, "read", "(JLjava/lang/String;I)[B"), ENTRY(10, "lockExisting", "(JLjava/lang/String;)J"),
    ENTRY(11, "createProfileLock", "(J)J"), ENTRY(12, "createVaultLock", "(J)J"),
    ENTRY(13, "stageRecord", "(JLjava/lang/String;[B)J"), ENTRY(14, "prepareRecord", "(JLjava/lang/String;[B)J"),
    ENTRY(15, "writeRecord", "(JLjava/lang/String;Ljava/lang/String;[BZ)V"),
    ENTRY(16, "renameCandidate", "(JLjava/lang/String;)V"), ENTRY(17, "replaceCandidate", "(JLjava/lang/String;)V"),
    ENTRY(18, "syncDirectory", "(J)V"), ENTRY(19, "discardStage", "(J)V"),
    ENTRY(20, "requestExpectedFileDeletion", "(JLjava/lang/String;[J)V"),
    ENTRY(21, "deleteRecord", "(JLjava/lang/String;[J)V"), ENTRY(22, "close", "(J)V")
};

static const struct JNINativeInterface_ jni;
static const struct JNIInvokeInterface_ invocation;
static JNIEnv environment = &jni;
static JavaVM vm = &invocation;
static const char *mode;
static int fault_step = -1, step, pending, frame, locals, global_class, global_primary, global_secondary;
static int vm_calls, registers, method_count, popped, duplicate_checked;
static uintptr_t addresses[PWP_JNI_METHOD_COUNT];
static pwp_jni_registration_report report;
static int is(const char *name) { return strcmp(mode, name) == 0; }
static void healthy(JNIEnv *env) { assert(env == &environment && !pending); }
static int fault(JNIEnv *env) {
    healthy(env);
    if (step++ != fault_step) return 0;
    pending = is("fault") ? 100 : 0;
    return 1;
}
static jint JNICALL get_env(JavaVM *actual, void **out, jint version) {
    assert(actual == &vm && version == PWP_JNI_RUNTIME_VERSION); ++vm_calls;
    if (is("detached")) { *out = NULL; return JNI_EDETACHED; }
    if (is("nullenv")) { *out = NULL; return JNI_OK; }
    *out = &environment;
    if (is("pending")) pending = 100;
    return JNI_OK;
}
static jboolean JNICALL exception_check(JNIEnv *env) { assert(env == &environment); return pending != 0; }
static jthrowable JNICALL exception_occurred(JNIEnv *env) {
    assert(env == &environment && pending);
    if (is("lost-exception")) return NULL;
    ++locals; return (jthrowable)REF(pending);
}
static void JNICALL exception_clear(JNIEnv *env) { assert(env == &environment); pending = 0; }
static void JNICALL delete_local(JNIEnv *env, jobject ref) {
    healthy(env); assert(ref == REF(100) || ref == REF(101)); assert(locals == 1); --locals;
}
static jint JNICALL version(JNIEnv *env) { healthy(env); return is("version") ? JNI_VERSION_1_8 : PWP_JNI_RUNTIME_VERSION; }
static jint JNICALL get_vm(JNIEnv *env, JavaVM **out) {
    healthy(env); *out = is("vm") ? NULL : &vm; return is("vmerror") ? JNI_ERR : JNI_OK;
}
static jint JNICALL push(JNIEnv *env, jint capacity) {
    healthy(env); assert(capacity == 16 && !frame);
    if (is("push") || is("push-null")) { pending = is("push") ? 100 : 0; return JNI_ERR; }
    frame = 1;
    if (is("push-pending")) pending = 100;
    return JNI_OK;
}
static jobject JNICALL pop(JNIEnv *env, jobject result) {
    healthy(env); assert(!locals && frame && !result); frame = 0; ++popped;
    if (is("pop-error") || is("double-error") || is("lost-primary")) pending = 101;
    return NULL;
}
static jclass JNICALL find(JNIEnv *env, const char *name) {
    if (fault(env)) return NULL;
    assert(!strcmp(name, "java/lang/ClassLoader") || !strcmp(name, "java/lang/Class"));
    return (jclass)REF(!strcmp(name, "java/lang/ClassLoader") ? 1 : 2);
}
static jmethodID JNICALL static_method(JNIEnv *env, jclass type, const char *name, const char *sig) {
    if (fault(env)) return NULL;
    if (type == (jclass)REF(2)) {
        assert(!strcmp(name, "forName") && !strcmp(sig, "(Ljava/lang/String;ZLjava/lang/ClassLoader;)Ljava/lang/Class;"));
        return METHOD(2);
    }
    assert(type == (jclass)REF(1) && !strcmp(name, "getSystemClassLoader") && !strcmp(sig, "()Ljava/lang/ClassLoader;"));
    return METHOD(1);
}
static jobject JNICALL call_static(JNIEnv *env, jclass type, jmethodID method, const jvalue *args) {
    if (fault(env)) return NULL;
    if (method == METHOD(2)) {
        assert(type == (jclass)REF(2) && args && args[0].l == REF(5) && args[1].z == JNI_FALSE && args[2].l == REF(3));
        if (is("reenter")) {
            pwp_jni_registration_report nested;
            assert(pwp_jni_register_once(&vm, addresses, PWP_JNI_METHOD_COUNT, &nested, sizeof(nested)) ==
                   PWP_JNI_REGISTER_DUPLICATE);
            assert(!nested.phase && !nested.class_retained && vm_calls == 1); ++duplicate_checked;
        }
        if (is("mutate")) for (unsigned i = 0; i < PWP_JNI_METHOD_COUNT; ++i) addresses[i] = 0;
        return REF(4);
    }
    assert(type == (jclass)REF(1) && method == METHOD(1) && !args); return REF(3);
}
static jmethodID JNICALL method(JNIEnv *env, jclass type, const char *name, const char *sig) {
    if (fault(env)) return NULL;
    if (type == (jclass)REF(2)) {
        assert(!strcmp(name, "getClassLoader") && !strcmp(sig, "()Ljava/lang/ClassLoader;")); return METHOD(3);
    }
    assert(type == (jclass)REF(4) && method_count < (int)PWP_JNI_METHOD_COUNT);
    assert(!strcmp(name, pwp_jni_methods[method_count].name) && !strcmp(sig, pwp_jni_methods[method_count].signature));
    ++method_count; return METHOD(20 + method_count);
}
static jstring JNICALL string(JNIEnv *env, const char *name) {
    if (fault(env)) return NULL;
    assert(!strcmp(name, "dev.p2pkit.sample.rpc.profile.WindowsProfileCustodyJni")); return (jstring)REF(5);
}
static jobject JNICALL call(JNIEnv *env, jobject target, jmethodID method_id, const jvalue *args) {
    if (fault(env)) return NULL;
    assert(method_id == METHOD(3) && target == REF(4) && !args);
    return is("owner") ? REF(6) : (is("owner-null") ? NULL : REF(3));
}
static jboolean JNICALL same(JNIEnv *env, jobject left, jobject right) { healthy(env); return left == right; }
static jobject JNICALL global(JNIEnv *env, jobject ref) {
    healthy(env);
    if (ref == REF(4)) {
        assert(!registers && !global_class);
        if (is("class-global") || is("class-global-null")) {
            if (is("class-global")) pending = 100;
            return NULL;
        }
        ++global_class;
        if (is("class-global-pending")) pending = 100;
        return REF(44);
    }
    assert(ref == REF(100) || ref == REF(101));
    if (is("retain-error") || (is("lost-primary") && ref == REF(100))) { pending = 101; return NULL; }
    if (ref == REF(100)) { assert(!global_primary); ++global_primary; }
    else { assert(!global_secondary); ++global_secondary; }
    if (is("retain-pending")) pending = 101;
    return REF((uintptr_t)ref + 1000);
}
static jint JNICALL register_methods(JNIEnv *env, jclass type, const JNINativeMethod *methods, jint count) {
    healthy(env); assert(type == (jclass)REF(4) && methods == pwp_jni_methods && count == (jint)PWP_JNI_METHOD_COUNT);
    assert(method_count == count && global_class == 1 && report.class_retained == 1 && report.phase == 1);
    assert(!registers++);
    for (int i = 0; i < count; ++i) assert(methods[i].fnPtr == (void *)(uintptr_t)(0x1000 + i * 16));
    if (is("register-error") || is("register-pending") || is("retain-error") || is("double-error") ||
        is("lost-primary") || is("retain-pending") || is("lost-exception"))
        pending = 100;
    return is("register-noerror") || is("register-error") || is("retain-error") || is("double-error") ||
           is("lost-primary") || is("retain-pending") || is("lost-exception") ? JNI_ERR : JNI_OK;
}
static const struct JNINativeInterface_ jni = {
    .GetVersion = version, .GetJavaVM = get_vm, .ExceptionCheck = exception_check,
    .ExceptionOccurred = exception_occurred, .ExceptionClear = exception_clear, .DeleteLocalRef = delete_local,
    .PushLocalFrame = push, .PopLocalFrame = pop, .FindClass = find, .GetStaticMethodID = static_method,
    .CallStaticObjectMethodA = call_static, .GetMethodID = method, .NewStringUTF = string,
    .CallObjectMethodA = call, .IsSameObject = same, .NewGlobalRef = global, .RegisterNatives = register_methods
    /* Attach/detach/unregister/global deletion/native calls deliberately absent: any such call fails. */
};
static const struct JNIInvokeInterface_ invocation = {.GetEnv = get_env};

int main(int argc, char **argv) {
    assert(argc == 2 || argc == 3); mode = argv[1];
    for (unsigned i = 0; i < PWP_JNI_METHOD_COUNT; ++i) addresses[i] = (uintptr_t)pwp_jni_methods[i].fnPtr;
    if (is("fault") || is("null")) { assert(argc == 3); fault_step = atoi(argv[2]); assert(fault_step >= 0 && fault_step < 32); }
    if (is("address")) { assert(argc == 3); int index = atoi(argv[2]); assert(index >= 0 && index < 23); addresses[index] ^= 8; }
    if (is("arguments")) {
        memset(&report, 0xaa, sizeof(report)); pwp_jni_registration_report original = report;
        assert(pwp_jni_register_once(&vm, addresses, 23, &report, 31) == PWP_JNI_REGISTER_ARGUMENT);
        assert(!memcmp(&report, &original, sizeof(report)));
        assert(pwp_jni_register_once(&vm, addresses, 23, NULL, 32) == PWP_JNI_REGISTER_ARGUMENT);
        assert(pwp_jni_register_once(NULL, addresses, 23, &report, 32) == PWP_JNI_REGISTER_ARGUMENT);
        assert(pwp_jni_register_once(&vm, NULL, 23, &report, 32) == PWP_JNI_REGISTER_ARGUMENT);
        const uint32_t counts[] = {0, 22, 24, UINT32_MAX};
        for (unsigned i = 0; i < 4; ++i)
            assert(pwp_jni_register_once(&vm, addresses, counts[i], &report, 32) == PWP_JNI_REGISTER_ARGUMENT);
        assert(!vm_calls && !registers); /* Invalid arguments have not consumed a valid attempt. */
    }
    int result = pwp_jni_register_once(&vm, addresses, PWP_JNI_METHOD_COUNT, &report, sizeof(report));
    assert(report.size == 32 && report.version == 1 && result == report.result);
    assert(!pending && !locals && !frame); /* No live local reference or pending exception escapes. */
    if (is("ok") || is("arguments") || is("mutate") || is("reenter")) {
        assert(result == PWP_JNI_REGISTER_OK && report.phase == 2 && registers == 1 && popped == 1);
        assert(report.class_retained && !report.exception_observed && !report.retention_uncertain);
    } else {
        assert(result != PWP_JNI_REGISTER_OK && report.phase != 2);
        if (is("address")) assert(result == PWP_JNI_REGISTER_ADDRESS && !vm_calls);
        if (is("detached") || is("nullenv")) assert(result == PWP_JNI_REGISTER_THREAD);
        if (is("version") || is("vm") || is("vmerror")) assert(result == PWP_JNI_REGISTER_RUNTIME);
        if (is("register-error") || is("register-noerror") || is("register-pending") || is("double-error"))
            assert(result == PWP_JNI_REGISTER_FAILED);
        if (is("class-global") || is("class-global-null") || is("class-global-pending") || is("retain-error") ||
            is("lost-primary") || is("retain-pending") || is("lost-exception"))
            assert(result == PWP_JNI_REGISTER_RETENTION_UNKNOWN && report.retention_uncertain);
        assert(report.phase == (uint32_t)(registers == 1));
        assert(report.class_retained == (uint32_t)global_class);
        int late = is("register-error") || is("register-noerror") || is("register-pending") ||
                   is("double-error") || is("retain-error") || is("lost-primary") || is("pop-error") ||
                   is("retain-pending") || is("lost-exception");
        assert(registers == late && global_class == (late || is("class-global-pending")));
        if (is("fault") || is("null")) assert(step == fault_step + 1);
    }
    assert(report.exception_retained == (uint32_t)(global_primary || (is("pop-error") && global_secondary)));
    if (is("double-error")) assert(global_primary && global_secondary && !report.retention_uncertain);
    if (is("lost-primary")) assert(!global_primary && global_secondary && !report.exception_retained && report.retention_uncertain);
    if (is("reenter")) assert(duplicate_checked == 1);
    int prior_vm_calls = vm_calls, prior_registers = registers;
    pwp_jni_registration_report duplicate;
    assert(pwp_jni_register_once(&vm, addresses, 23, &duplicate, sizeof(duplicate)) == PWP_JNI_REGISTER_DUPLICATE);
    assert(!duplicate.phase && !duplicate.class_retained && prior_vm_calls == vm_calls && prior_registers == registers);
    printf("registration control %s %d PASS; scope=JNI_VTABLE_MODEL_NOT_VM_OR_WINDOWS\n", mode, fault_step);
    return 0;
}
