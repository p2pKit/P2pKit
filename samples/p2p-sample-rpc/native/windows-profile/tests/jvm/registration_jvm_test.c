/* Component test only: actual development JDK21 JNI with a statically linked registrar/bridge.
 * No Windows DLL, FFM, OS storage, installed runtime or productive loader is exercised.
 * The driver creates the VM; the unmodified registrar must never create or attach one.
 */
#include "../../profile_jni_registration.h"
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define REQUIRE(condition) do { \
    if (!(condition)) { \
        fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #condition); \
        exit(1); \
    } \
} while (0)

static const char target_name[] = "dev/p2pkit/sample/rpc/profile/WindowsProfileCustodyJni";

static void no_exception(JNIEnv *env) {
    if ((*env)->ExceptionCheck(env)) {
        (*env)->ExceptionDescribe(env);
        exit(1);
    }
}

static jobject instance(JNIEnv *env, jclass type) {
    jfieldID field = (*env)->GetStaticFieldID(env, type, "INSTANCE",
        "Ldev/p2pkit/sample/rpc/profile/WindowsProfileCustodyJni;");
    no_exception(env);
    REQUIRE(field);
    jobject value = (*env)->GetStaticObjectField(env, type, field);
    no_exception(env);
    REQUIRE(value);
    return value;
}

static void unbound(JNIEnv *env) {
    jclass type = (*env)->FindClass(env, target_name);
    no_exception(env);
    REQUIRE(type);
    jobject value = instance(env, type);
    jmethodID abi = (*env)->GetMethodID(env, type, "abi", "()I");
    no_exception(env);
    REQUIRE(abi);
    (void)(*env)->CallIntMethodA(env, value, abi, NULL);
    REQUIRE((*env)->ExceptionCheck(env));
    jthrowable error = (*env)->ExceptionOccurred(env);
    (*env)->ExceptionClear(env);
    jclass expected = (*env)->FindClass(env, "java/lang/UnsatisfiedLinkError");
    no_exception(env);
    REQUIRE(expected && (*env)->IsInstanceOf(env, error, expected));
    (*env)->DeleteLocalRef(env, expected);
    (*env)->DeleteLocalRef(env, error);
    (*env)->DeleteLocalRef(env, value);
    (*env)->DeleteLocalRef(env, type);
    no_exception(env);
}

static void constants(JNIEnv *env) {
    jclass type = (*env)->FindClass(env, target_name);
    no_exception(env);
    REQUIRE(type);
    jobject value = instance(env, type);
    jmethodID abi = (*env)->GetMethodID(env, type, "abi", "()I");
    no_exception(env);
    jmethodID capabilities = (*env)->GetMethodID(env, type, "capabilities", "()J");
    no_exception(env);
    REQUIRE(abi && capabilities);
    jint actual_abi = (*env)->CallIntMethodA(env, value, abi, NULL);
    no_exception(env);
    jlong actual_capabilities = (*env)->CallLongMethodA(env, value, capabilities, NULL);
    no_exception(env);
    REQUIRE(actual_abi == 13 && actual_capabilities == 0x43);
    (*env)->DeleteLocalRef(env, value);
    (*env)->DeleteLocalRef(env, type);
    no_exception(env);
}

static void collect(JNIEnv *env) {
    jclass system = (*env)->FindClass(env, "java/lang/System");
    no_exception(env);
    REQUIRE(system);
    jmethodID gc = (*env)->GetStaticMethodID(env, system, "gc", "()V");
    no_exception(env);
    REQUIRE(gc);
    (*env)->CallStaticVoidMethodA(env, system, gc, NULL);
    no_exception(env);
    (*env)->DeleteLocalRef(env, system);
}

int main(int argc, char **argv) {
    REQUIRE(argc == 4 && argv[1][0] == '/' && argv[2][0] == '/');
    const int success = strcmp(argv[3], "success") == 0;
    const int pending = strcmp(argv[3], "pending") == 0;
    const int address = strcmp(argv[3], "address") == 0;
    const int missing = strcmp(argv[3], "missing-class") == 0;
    REQUIRE(success || pending || address || missing);
    /* Explicit existing trusted development JDK, NOT a candidate helper or production bootstrap.
     * Keep the loaded development runtime alive through process exit; never dlclose it. */
    void *runtime = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!runtime) fprintf(stderr, "development JDK load failed: %s\n", dlerror());
    REQUIRE(runtime);
    void *symbol = dlsym(runtime, "JNI_CreateJavaVM");
    REQUIRE(symbol);
    jint (JNICALL *create_vm)(JavaVM **, void **, void *);
    _Static_assert(sizeof(create_vm) == sizeof(symbol), "Function pointer size");
    memcpy(&create_vm, &symbol, sizeof(create_vm));
    char classpath[8192];
    int length = snprintf(classpath, sizeof(classpath), "-Djava.class.path=%s", argv[2]);
    REQUIRE(length > 0 && (size_t)length < sizeof(classpath));
    JavaVMOption options[] = {
        {classpath, NULL}, {"-Xcheck:jni", NULL}, {"-Xms16m", NULL}, {"-Xmx64m", NULL},
        {"-XX:+UseSerialGC", NULL}, {"-XX:-CreateCoredumpOnCrash", NULL},
    };
    JavaVMInitArgs arguments = {PWP_JNI_RUNTIME_VERSION, 6, options, JNI_FALSE};
    JavaVM *vm = NULL;
    JNIEnv *env = NULL;
    REQUIRE(create_vm(&vm, (void **)&env, &arguments) == JNI_OK && vm && env);
    REQUIRE((*env)->GetVersion(env) == PWP_JNI_RUNTIME_VERSION);
    if (!missing) unbound(env); /* Reject accidental automatic symbol resolution before registration. */
    uintptr_t entries[PWP_JNI_METHOD_COUNT];
    for (uint32_t i = 0; i < PWP_JNI_METHOD_COUNT; ++i)
        entries[i] = (uintptr_t)pwp_jni_methods[i].fnPtr;
    if (address) entries[0] = entries[1];
    if (pending) {
        jclass error = (*env)->FindClass(env, "java/lang/IllegalStateException");
        no_exception(env);
        REQUIRE(error && (*env)->ThrowNew(env, error, "synthetic registrar control") == JNI_OK);
        (*env)->DeleteLocalRef(env, error);
        REQUIRE((*env)->ExceptionCheck(env));
    }
    pwp_jni_registration_report report;
    int32_t result = pwp_jni_register_once(vm, entries, PWP_JNI_METHOD_COUNT, &report, sizeof(report));
    no_exception(env);
    REQUIRE(report.size == sizeof(report) && report.version == 1 && report.result == result);
    REQUIRE(!report.retention_uncertain);
    if (success) {
        REQUIRE(result == PWP_JNI_REGISTER_OK && report.phase == 2 && report.class_retained == 1);
        REQUIRE(!report.exception_observed && !report.exception_retained);
        constants(env);
        collect(env); /* A completed real GC request, not a promise of class unloading. */
        constants(env);
    } else {
        REQUIRE(report.phase == 0 && !report.class_retained);
        REQUIRE(result == (pending ? PWP_JNI_REGISTER_EXCEPTION :
            (address ? PWP_JNI_REGISTER_ADDRESS : PWP_JNI_REGISTER_CLASS)));
        REQUIRE(report.exception_observed == (uint32_t)!address);
        REQUIRE(report.exception_retained == (uint32_t)!address);
        if (!missing) unbound(env);
    }
    for (uint32_t i = 0; i < PWP_JNI_METHOD_COUNT; ++i)
        entries[i] = (uintptr_t)pwp_jni_methods[i].fnPtr;
    REQUIRE(pwp_jni_register_once(vm, entries, PWP_JNI_METHOD_COUNT, &report, sizeof(report)) ==
        PWP_JNI_REGISTER_DUPLICATE);
    no_exception(env);
    REQUIRE(report.phase == 0 && !report.class_retained && !report.exception_observed &&
        !report.exception_retained && !report.retention_uncertain);
    if (success) constants(env);
    /* This test owns its VM. No unregister/global-reference release or module unload is attempted. */
    REQUIRE((*vm)->DestroyJavaVM(vm) == JNI_OK);
    printf("PASS real-development-JDK21-registration %s; no Windows storage or loader\n", argv[3]);
    return 0;
}
