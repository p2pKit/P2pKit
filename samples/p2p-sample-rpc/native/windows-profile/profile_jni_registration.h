#ifndef PWP_JNI_REGISTRATION_H
#define PWP_JNI_REGISTRATION_H

#include <jni.h>
#include <stdint.h>

#define PWP_JNI_METHOD_COUNT 23u
#define PWP_JNI_RUNTIME_VERSION ((jint)0x00150000) /* JNI_VERSION_21, including JDK17-header builds. */
#ifdef _WIN32
#define PWP_JNI_REGISTRATION_EXPORT __declspec(dllexport)
#else
#define PWP_JNI_REGISTRATION_EXPORT
#endif

typedef enum {
    PWP_JNI_REGISTER_OK = 0,
    PWP_JNI_REGISTER_ARGUMENT = 1,
    PWP_JNI_REGISTER_DUPLICATE = 2,
    PWP_JNI_REGISTER_ADDRESS = 3,
    PWP_JNI_REGISTER_THREAD = 4,
    PWP_JNI_REGISTER_RUNTIME = 5,
    PWP_JNI_REGISTER_CLASS = 6,
    PWP_JNI_REGISTER_METHOD = 7,
    PWP_JNI_REGISTER_EXCEPTION = 8,
    PWP_JNI_REGISTER_FAILED = 9,
    PWP_JNI_REGISTER_RETENTION_UNKNOWN = 10
} pwp_jni_registration_result;

typedef struct {
    uint32_t size;
    uint32_t version;
    uint32_t phase; /* 0 not attempted; 1 attempted/uncertain; 2 complete and no pending exception. */
    int32_t result;
    uint32_t class_retained;
    uint32_t exception_observed;
    uint32_t exception_retained;
    uint32_t retention_uncertain;
} pwp_jni_registration_report;

/* Original compiled symbols, never a caller-supplied table. Not an exported DLL interface. */
extern const JNINativeMethod pwp_jni_methods[PWP_JNI_METHOD_COUNT];

/* Exported post-admission interface version 1; dormant with no production caller yet.
 * Before entry the loader must independently admit the installed runtime, exactly one VM, this
 * original module/mappings/imports and fixed compiled Java class, and permanently reserve their
 * owners. Arguments and output must be live, disjoint, bounded allocations on the platform thread.
 * These pointers are NOT authority. The function neither loads nor pins a native module.
 * A valid invocation consumes the single original-module attempt even if registration is not reached.
 * The external process owner must prohibit another copy/reload, not just calls into this mapping.
 * Native global references are deliberately retained until process exit; no reset/unregister/free
 * API exists. Profile Stop must not unload code. Once JNIEnv is acquired, no pending JNI exception
 * crosses the return. Earlier argument/duplicate refusals do not inspect or alter caller JNI state.
 */
PWP_JNI_REGISTRATION_EXPORT int32_t pwp_jni_register_once(JavaVM *expected_vm, const uintptr_t *expected_entry_points,
                            uint32_t entry_count, pwp_jni_registration_report *report, uint32_t report_bytes);

#endif
