/* Exercise the retained default entry point's pre-application refusal in this
 * process. Exit 125 remains an infrastructure failure to the outer executor;
 * this control returns zero only after observing that exact expected refusal.
 * No Terminal invocation, subprocess, ownership claim or permission change. */
#ifdef P2PKIT_APPLE_CI_CANDIDATE
#error This refusal control must compile the default controller, not its candidate
#endif
#define main retained_default_terminal_main
#include "../../diagnostics/apple-terminal-context.m"
#undef main
#include <stdio.h>

int main(int argc, const char **argv) {
    (void)argv;
    if (argc != 1 || getuid() == 0 || getuid() != geteuid() || getgid() != getegid()) return 1;
    const char *arguments[] = {"default-terminal-control", "/unused-ci-refusal-control", "ci"};
    int code = retained_default_terminal_main(3, arguments);
    if (code != 125) return 1;
    puts("PASS: default Terminal ci refusal exit=125; NO_APPLICATION_EXECUTION");
    return 0;
}
