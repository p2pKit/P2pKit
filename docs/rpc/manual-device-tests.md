# Manual device tests

The Android, iPhone and Mac RPC samples have a separate **Device tests** screen.
Open it on each device, join the same approved private Wi-Fi, and run the tests
with the buttons. Network discovery supplies addresses; no IP entry is needed.
The exercises send generated test data over the real authenticated and encrypted
RPC connection.

1. Choose **Host here** on one device and **Client here** on another.
2. On the Client, select the nearby Host. Compare fingerprints and approve the
   first connection on the Host. The Host then lists the connected Client.
   The Mac may ask you to unlock its local application profile.
3. Choose a test button on the Client. To start it from the Host, select the
   connected Client and enable **Allow selected Host to start tests** on that
   Client while its Device tests screen is open.
4. Wait for the saved result before starting another test. **Cancel test** ends
   the current exercise; **Stop** closes the role and its owned resources.

Start with **Correctness**, **Large data**, **Cancellation / deadline**, then
**Disconnect / reconnect**. Run **Steady · 30 minutes** after the short tests
work. Report a failure immediately with the direction, phase and saved run ID;
there is no need to finish the other tests first. When finished, ask the agent
to collect and analyze the private archives.

For all application directions, exercise Android → Mac, iPhone → Mac,
Mac → Android, iPhone → Android, Mac → iPhone and Android → iPhone. The arrow
means Client sends requests to Host, even when the Host starts a test using
the Client's explicit permission. Choose one phase on one Client at a time.
Keep both phones connected as Clients while Mac is Host, and select each in
turn for Host-started tests.

| Button | Exercise |
| --- | --- |
| Large data | Check exact replies for 64 KiB, 256 KiB and 1 MiB encoded bodies |
| Correctness | Check echo replies, application data and the expected invalid-input error |
| Disconnect / reconnect | Disconnect five times and rediscover the saved Host identity before checking another reply |
| Steady · 30 minutes | Measure thirty minutes separately from initialization, targeting one call every 100 ms |
| Cancellation / deadline | Check a deadline, caller cancellation and a subsequent successful reply |

Keep the apps foreground and unlocked during a test. Rediscovery uses the
saved identity and a fresh endpoint, including after an address change. A Wi-Fi
outage that exceeds recovery bounds produces an interrupted or failed result;
it does not silently restart a workload or turn the result into a pass.
Rejoin the approved network and start a new test when the connection is Ready.

**Live test activity** shows requests observed on this device, the procedure,
generated body size when known, reply/error state, elapsed time and execution
evidence. It uses actual RPC observations. A Host handler returning or finalizing
a reply does not by itself prove the Client received it. Source-matched test
registration makes Client-started runs visible on the Host, sends bounded
progress messages about once per second, and delivers the final report.
These progress messages are additional control traffic and are counted
separately from workload responses. A missing final report stays unconfirmed;
it is not converted into a passed result on the Host.

Every completed or failed test is saved as a separate private archive record;
older records are not automatically deleted. The recent-results list keeps
100 runs in memory. Android and iPhone use application-private
`rpc-test-archive` directories; Mac keeps encrypted records and a paged index
inside its existing protected profile. Archive-write failure is displayed and
pending records are retained; a full pending queue refuses new tests instead
of discarding an old result. Stop and changing roles keep these archives.
Uninstalling an app or deleting its profile/data can still remove its files.

Reports include Client → Host platform direction, start time, which side
initiated the test, run ID, phase and source,
actual client count, initialization and measured durations, correct responses,
latency percentiles, missed schedules, deliberate disconnect/deadline outcomes
and available sampled resources. They retain bounded recent request observations;
the live panel can miss intermediate states and is not a complete packet trace.
Old reports without endpoint metadata keep **Unknown** instead of guessing a
direction or date. Missing measurements remain unavailable.
Serious or critical thermal observations interrupt the exercise. Charging
observations do not establish battery discharge.

These buttons exercise **one connected Client per run**. A Host can select each
connected phone in turn, allowing Mac Host with both phone Clients and reciprocal
Android/iPhone roles. These application exercises do not establish 128/256-client
capacity, simultaneous 255 Mac clients plus a phone, socket backpressure, fairness,
revocation coverage or battery-discharge qualification. Use the
[maintained physical campaign](mac-mobile-continuation.md) for that scope.
Both endpoints must use matching source; a mismatch produces a failed result.
Authentication, encryption and first-connection approval remain required.

If the Mac's existing profile passphrase is unavailable, run its prepared
`run-desktop.py --new-test-profile` launcher. This creates a separate private
test profile. Choose a new strong passphrase of 12–128 characters in the app;
the existing profile, identity and approvals remain intact. Each invocation
with this flag creates another profile. The normal launcher keeps its existing
default profile.

## Screenshots

The Mac image is an idle UI render fixture from the prepared source. The iPhone
image shows source `3231b843` installed on the physical iPhone, with its Device
tests entry and no active role.
Neither image is workload evidence. Android's protected screen refused automated
capture; its private UI observation verified the page and all five buttons.

![Mac Device tests page, idle UI fixture](images/manual-device-tests-mac.png)

![Installed iPhone Device tests entry](images/manual-device-tests-iphone.png)
