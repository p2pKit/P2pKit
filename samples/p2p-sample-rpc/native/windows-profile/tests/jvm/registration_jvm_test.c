/* Component test only: actual development JDK21 JNI with a statically linked registrar/bridge.
 * Opt-in FFM controls use the actual dormant named-module invocation, never the profile DLL,
 * OS storage, installed runtime or productive loader.
 * The driver creates the VM; the unmodified registrar must never create or attach one.
 */
#include "../../profile_jni_registration.h"
#ifdef _WIN32
#include <windows.h>
#else
#include <dlfcn.h>
#endif
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define REQUIRE(condition) do { \
    if (!(condition)) { \
        fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #condition); \
        exit(1); \
    } \
} while (0)

static int absolute_path(const char *path) {
#ifdef _WIN32
    return strlen(path) > 3 && ((path[0] >= 'A' && path[0] <= 'Z') ||
        (path[0] >= 'a' && path[0] <= 'z')) && path[1] == ':' && path[2] == '\\';
#else
    return path[0] == '/';
#endif
}

typedef jint (JNICALL *create_vm_entry)(JavaVM **, void **, void *);

#ifdef _WIN32
/* Test-process roots only. Never FreeLibrary/RemoveDllDirectory before VM/process exit. */
static HMODULE development_runtime;
static DLL_DIRECTORY_COOKIE development_bin;
#endif

static create_vm_entry development_vm_entry(const char *path) {
#ifdef _WIN32
    /* No ordinary jvm.lib import: that would resolve jvm.dll before this closed search policy.
     * The hosted controller supplies only the selected existing development JDK's canonical path. */
    wchar_t original[8192], bin[8192], observed[8192];
    const char suffix[] = "\\bin\\server\\jvm.dll";
    size_t length = strlen(path), suffix_length = sizeof(suffix) - 1;
    REQUIRE(absolute_path(path) && length < 8192 && length > suffix_length);
    REQUIRE(strcmp(path + length - suffix_length, suffix) == 0);
    for (size_t i = 0; i <= length; ++i) {
        REQUIRE((unsigned char)path[i] < 128);
        original[i] = (wchar_t)(unsigned char)path[i];
        bin[i] = original[i];
    }
    bin[length - suffix_length + 4] = L'\0'; /* Preserve only the exact selected JDK\bin. */
    SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX);
    REQUIRE(GetModuleHandleW(L"jvm.dll") == NULL);
    REQUIRE(SetDllDirectoryW(L""));
    REQUIRE(SetDefaultDllDirectories(LOAD_LIBRARY_SEARCH_SYSTEM32 | LOAD_LIBRARY_SEARCH_USER_DIRS));
    development_bin = AddDllDirectory(bin);
    REQUIRE(development_bin);
    development_runtime = LoadLibraryExW(original, NULL,
        LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_SYSTEM32 | LOAD_LIBRARY_SEARCH_USER_DIRS);
    REQUIRE(development_runtime);
    DWORD observed_length = GetModuleFileNameW(development_runtime, observed, 8192);
    REQUIRE(observed_length > 0 && observed_length < 8192);
    REQUIRE(CompareStringOrdinal(original, -1, observed, -1, TRUE) == CSTR_EQUAL);
    FARPROC symbol = GetProcAddress(development_runtime, "JNI_CreateJavaVM");
#else
    /* Explicit existing development JDK, NOT a candidate helper or productive bootstrap. */
    void *runtime = dlopen(path, RTLD_NOW | RTLD_LOCAL);
    if (!runtime) fprintf(stderr, "development JDK load failed: %s\n", dlerror());
    REQUIRE(runtime);
    void *symbol = dlsym(runtime, "JNI_CreateJavaVM");
#endif
    REQUIRE(symbol);
    create_vm_entry create_vm;
    _Static_assert(sizeof(create_vm) == sizeof(symbol), "Function pointer size");
    memcpy(&create_vm, &symbol, sizeof(create_vm));
    return create_vm;
}

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

static void ffm_registration(JNIEnv *env, JavaVM *vm, const uintptr_t *entries, const char *mode) {
    jclass adapter = (*env)->FindClass(env, "dev/p2pkit/rpc/windows/loader/RealRegistrationInvocationTest");
    no_exception(env);
    REQUIRE(adapter);
    jmethodID run = (*env)->GetStaticMethodID(env, adapter, "run", "(JJ[JLjava/lang/String;)V");
    no_exception(env);
    REQUIRE(run);
    jlongArray addresses = (*env)->NewLongArray(env, PWP_JNI_METHOD_COUNT);
    no_exception(env);
    REQUIRE(addresses);
    jlong values[PWP_JNI_METHOD_COUNT];
    for (uint32_t i = 0; i < PWP_JNI_METHOD_COUNT; ++i) values[i] = (jlong)entries[i];
    (*env)->SetLongArrayRegion(env, addresses, 0, PWP_JNI_METHOD_COUNT, values);
    no_exception(env);
    jstring name = (*env)->NewStringUTF(env, mode);
    no_exception(env);
    REQUIRE(name);
    /* Only the test-created VM and statically linked original symbols cross this test-only adapter. */
    jvalue arguments[4];
    arguments[0].j = (jlong)(uintptr_t)pwp_jni_register_once;
    arguments[1].j = (jlong)(uintptr_t)vm;
    arguments[2].l = addresses;
    arguments[3].l = name;
    (*env)->CallStaticVoidMethodA(env, adapter, run, arguments);
    no_exception(env);
    (*env)->DeleteLocalRef(env, name);
    (*env)->DeleteLocalRef(env, addresses);
    (*env)->DeleteLocalRef(env, adapter);
}

int main(int argc, char **argv) {
    REQUIRE((argc == 4 || argc == 5) && absolute_path(argv[1]) && absolute_path(argv[2]));
    const int ffm = strncmp(argv[3], "ffm-", 4) == 0;
    REQUIRE((ffm && argc == 5 && absolute_path(argv[4])) || (!ffm && argc == 4));
    const int success = strcmp(argv[3], "success") == 0 || strcmp(argv[3], "ffm-success") == 0;
    const int pending = strcmp(argv[3], "pending") == 0;
    const int address = strcmp(argv[3], "address") == 0 || strcmp(argv[3], "ffm-address") == 0;
    const int missing = strcmp(argv[3], "missing-class") == 0 || strcmp(argv[3], "ffm-missing-class") == 0;
    REQUIRE(success || pending || address || missing);
    create_vm_entry create_vm = development_vm_entry(argv[1]);
    char classpath[8192];
    int length = snprintf(classpath, sizeof(classpath), "-Djava.class.path=%s", argv[2]);
    REQUIRE(length > 0 && (size_t)length < sizeof(classpath));
    char modulepath[8192] = {0};
    if (ffm) {
        length = snprintf(modulepath, sizeof(modulepath), "--module-path=%s", argv[4]);
        REQUIRE(length > 0 && (size_t)length < sizeof(modulepath));
    }
    JavaVMOption options[] = {
        {classpath, NULL}, {"-Xcheck:jni", NULL}, {"-Xms16m", NULL}, {"-Xmx64m", NULL},
        {"-XX:+UseSerialGC", NULL}, {"-XX:-CreateCoredumpOnCrash", NULL},
        {"--enable-preview", NULL}, {modulepath, NULL},
        {"--add-modules=dev.p2pkit.rpc.windows.loader", NULL},
        {"--enable-native-access=dev.p2pkit.rpc.windows.loader", NULL},
    };
    JavaVMInitArgs arguments = {PWP_JNI_RUNTIME_VERSION, ffm ? 10 : 6, options, JNI_FALSE};
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
    if (ffm) {
        ffm_registration(env, vm, entries, argv[3]);
        if (success) {
            constants(env);
            collect(env);
            constants(env);
        } else if (!missing) {
            unbound(env);
        }
    } else {
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
