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
package dev.p2pkit.transport.lan.internal.jmdns.impl.tasks.state;

import java.io.IOException;
import java.util.Timer;

import dev.p2pkit.transport.lan.internal.jmdns.impl.DNSOutgoing;
import dev.p2pkit.transport.lan.internal.jmdns.impl.DNSRecord;
import dev.p2pkit.transport.lan.internal.jmdns.impl.JmDNSImpl;
import dev.p2pkit.transport.lan.internal.jmdns.impl.ServiceInfoImpl;
import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSConstants;
import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSRecordClass;
import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSState;

/**
 * The Canceler sends two announces with TTL=0 for the specified services.
 */
public class Canceler extends DNSStateTask {

    public Canceler(JmDNSImpl jmDNSImpl) {
        super(jmDNSImpl, 0);

        this.setTaskState(DNSState.CANCELING_1);
        this.associate(DNSState.CANCELING_1);
    }

    @Override
    protected boolean isCancellationTask() {
        return true;
    }

    /*
     * (non-Javadoc)
     * @see dev.p2pkit.transport.lan.internal.jmdns.impl.tasks.DNSTask#getName()
     */
    @Override
    public String getName() {
        return "Canceler(" + (this.getDns() != null ? this.getDns().getName() : "") + ")";
    }

    /*
     * (non-Javadoc)
     * @see java.lang.Object#toString()
     */
    @Override
    public String toString() {
        return super.toString() + " state: " + this.getTaskState();
    }

    /*
     * (non-Javadoc)
     * @see dev.p2pkit.transport.lan.internal.jmdns.impl.tasks.DNSTask#start(java.util.Timer)
     */
    @Override
    public void start(Timer timer) {
        this.getDns().scheduleTask(this, timer, 0, DNSConstants.ANNOUNCE_WAIT_INTERVAL, true);
    }

    /*
     * (non-Javadoc)
     * @see java.util.TimerTask#cancel()
     */
    @Override
    public boolean cancel() {
        this.removeAssociation();

        return super.cancel();
    }

    /*
     * (non-Javadoc)
     * @see dev.p2pkit.transport.lan.internal.jmdns.impl.tasks.state.DNSStateTask#getTaskDescription()
     */
    @Override
    public String getTaskDescription() {
        return "canceling";
    }

    /*
     * (non-Javadoc)
     * @see dev.p2pkit.transport.lan.internal.jmdns.impl.tasks.state.DNSStateTask#checkRunCondition()
     */
    @Override
    protected boolean checkRunCondition() {
        return true;
    }

    /*
     * (non-Javadoc)
     * @see dev.p2pkit.transport.lan.internal.jmdns.impl.tasks.state.DNSStateTask#createOutgoing()
     */
    @Override
    protected DNSOutgoing createOutgoing() {
        return new DNSOutgoing(DNSConstants.FLAGS_QR_RESPONSE | DNSConstants.FLAGS_AA);
    }

    /*
     * (non-Javadoc)
     * @see dev.p2pkit.transport.lan.internal.jmdns.impl.tasks.state.DNSStateTask#buildOutgoingForDNS(dev.p2pkit.transport.lan.internal.jmdns.impl.DNSOutgoing)
     */
    @Override
    protected DNSOutgoing buildOutgoingForDNS(DNSOutgoing out) throws IOException {
        DNSOutgoing newOut = out;
        for (DNSRecord answer : this.getDns().getLocalHost().answers(DNSRecordClass.CLASS_ANY, DNSRecordClass.UNIQUE, this.getTTL())) {
            newOut = this.addAnswer(newOut, null, answer);
        }
        return newOut;
    }

    /*
     * (non-Javadoc)
     * @see dev.p2pkit.transport.lan.internal.jmdns.impl.tasks.state.DNSStateTask#buildOutgoingForInfo(dev.p2pkit.transport.lan.internal.jmdns.impl.ServiceInfoImpl, dev.p2pkit.transport.lan.internal.jmdns.impl.DNSOutgoing)
     */
    @Override
    protected DNSOutgoing buildOutgoingForInfo(ServiceInfoImpl info, DNSOutgoing out) throws IOException {
        DNSOutgoing newOut = out;
        for (DNSRecord answer : info.answers(DNSRecordClass.CLASS_ANY, DNSRecordClass.UNIQUE, this.getTTL(), this.getDns().getLocalHost())) {
            newOut = this.addAnswer(newOut, null, answer);
        }
        return newOut;
    }

    /*
     * (non-Javadoc)
     * @see dev.p2pkit.transport.lan.internal.jmdns.impl.tasks.state.DNSStateTask#recoverTask(java.lang.Throwable)
     */
    @Override
    protected void recoverTask(Throwable e) {
        this.getDns().recover();
    }

    /*
     * (non-Javadoc)
     * @see dev.p2pkit.transport.lan.internal.jmdns.impl.tasks.state.DNSStateTask#advanceTask()
     */
    @Override
    protected void advanceTask() {
        this.setTaskState(this.getTaskState().advance());
        if (!this.getTaskState().isCanceling()) {
            cancel();
        }
    }
}
