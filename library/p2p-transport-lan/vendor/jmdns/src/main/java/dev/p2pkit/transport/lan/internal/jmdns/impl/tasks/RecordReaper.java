/*
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
/*
 * P2pKit modification: privately relocated from javax.jmdns to
 * dev.p2pkit.transport.lan.internal.jmdns. See the accompanying
 * PROVENANCE.json and MODIFICATIONS.txt for origin and change details.
 */
package dev.p2pkit.transport.lan.internal.jmdns.impl.tasks;

import java.util.Timer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import dev.p2pkit.transport.lan.internal.jmdns.impl.JmDNSImpl;
import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSConstants;

/**
 * Periodically removes expired entries from the cache.
 */
public class RecordReaper extends DNSTask {
    private final Logger logger = LoggerFactory.getLogger(RecordReaper.class);

    public RecordReaper(JmDNSImpl jmDNSImpl) {
        super(jmDNSImpl);
    }

    /*
     * (non-Javadoc)
     * @see dev.p2pkit.transport.lan.internal.jmdns.impl.tasks.DNSTask#getName()
     */
    @Override
    public String getName() {
        return "RecordReaper(" + (this.getDns() != null ? this.getDns().getName() : "") + ")";
    }

    /*
     * (non-Javadoc)
     * @see dev.p2pkit.transport.lan.internal.jmdns.impl.tasks.DNSTask#start(java.util.Timer)
     */
    @Override
    public void start(Timer timer) {
        if (!this.getDns().isCanceling() && !this.getDns().isCanceled()) {
            this.getDns().scheduleTask(this, timer,
                    DNSConstants.RECORD_REAPER_INTERVAL, DNSConstants.RECORD_REAPER_INTERVAL, false);
        }
    }

    @Override
    protected void runTask() {
        if (this.getDns().isCanceling() || this.getDns().isCanceled()) {
            return;
        }
        logger.trace("{}.run() JmDNS reaping cache", this.getName());

        // Remove expired answers from the cache
        // -------------------------------------
        this.getDns().cleanCache();
    }

}
