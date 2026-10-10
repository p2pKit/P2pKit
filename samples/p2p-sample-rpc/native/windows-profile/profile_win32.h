#ifndef P2PKIT_WINDOWS_PROFILE_WIN32_H
#define P2PKIT_WINDOWS_PROFILE_WIN32_H
#include "profile_policy.h"
/* Custody implementation, NOT complete profile persistence: transaction capability remains absent. */
pwp_result pwp_win_open_root(uint64_t *root);
pwp_result pwp_win_child(uint64_t parent, const uint16_t *name, size_t length, uint64_t *child);
pwp_result pwp_win_identity(uint64_t handle, uint64_t words[PWP_IDENTITY_WORDS]);
pwp_result pwp_win_read(uint64_t directory, const uint16_t *name, size_t length,
                        unsigned char *output, size_t maximum, size_t *written);
pwp_result pwp_win_lock(uint64_t directory, const uint16_t *name, size_t length, uint64_t *lease);
pwp_result pwp_win_close(uint64_t handle);
#endif
