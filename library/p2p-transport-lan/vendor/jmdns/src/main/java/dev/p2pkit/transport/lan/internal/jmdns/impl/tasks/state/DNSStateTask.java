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
import java.util.ArrayList;
import java.util.List;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import dev.p2pkit.transport.lan.internal.jmdns.ServiceInfo;
import dev.p2pkit.transport.lan.internal.jmdns.impl.DNSOutgoing;
import dev.p2pkit.transport.lan.internal.jmdns.impl.DNSStatefulObject;
import dev.p2pkit.transport.lan.internal.jmdns.impl.JmDNSImpl;
import dev.p2pkit.transport.lan.internal.jmdns.impl.ServiceInfoImpl;
import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSConstants;
import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSState;
import dev.p2pkit.transport.lan.internal.jmdns.impl.tasks.DNSTask;

/**
 * This is the root class for all state tasks. These tasks work with objects that implements the
 * {@link dev.p2pkit.transport.lan.internal.jmdns.impl.DNSStatefulObject} interface and therefore participate in the state machine.
 *
 * @author Pierre Frisch
 */
public abstract class DNSStateTask extends DNSTask {
    private final Logger logger = LoggerFactory.getLogger(DNSStateTask.class);

    /**
     * By setting a 0 ttl we effectively expire the record.
     */
    private final int ttl;

    private static int defaultTTL = DNSConstants.DNS_TTL;

    /**
     * The state of the task.
     */
    private DNSState taskState = null;

    private DNSState initialAssociationState;

    public abstract String getTaskDescription();

    public static int defaultTTL() {
        return defaultTTL;
    }

    /**
     * For testing only do not use in production.
     *
     * @param value
     */
    public static void setDefaultTTL(int value) {
        defaultTTL = value;
    }

    /**
     * @param jmDNSImpl
     * @param ttl
     */
    DNSStateTask(JmDNSImpl jmDNSImpl, int ttl) {
        super(jmDNSImpl);
        this.ttl = ttl;
    }

    /**
     * @return the ttl
     */
    public int getTTL() {
        return ttl;
    }

    /**
     * Record the DNS host and service association to apply atomically with admitted scheduling.
     *
     * @param state target state
     */
    protected void associate(DNSState state) {
        this.initialAssociationState = state;
    }

    /**
     * Return the association requested by construction, without applying it before scheduling admission.
     *
     * @return initial association state
     */
    public final DNSState getInitialAssociationState() {
        return this.initialAssociationState;
    }

    /**
     * Remove the DNS host and service info association with this task.
     */
    protected void removeAssociation() {
        // Remove association from host to this
        synchronized (this.getDns()) {
            this.getDns().removeAssociationWithTask(this);
        }

        // Remove associations from services to this
        for (ServiceInfo serviceInfo : this.getDns().getServices().values()) {
            ((ServiceInfoImpl) serviceInfo).removeAssociationWithTask(this);
        }
    }

    @Override
    protected void runTask() {
        DNSOutgoing out = this.createOutgoing();
        try {
            if (!this.checkRunCondition()) {
                this.cancel();
                return;
            }
            List<DNSStatefulObject> stateObjects = new ArrayList<>();
            // send probes for JmDNS itself
            synchronized (this.getDns()) {
                if (this.getDns().isAssociatedWithTask(this, this.getTaskState())) {
                    logger.debug("{}.run() JmDNS {} {}", this.getName(), this.getTaskDescription(), this.getDns().getName());
                    stateObjects.add(this.getDns());
                    out = this.buildOutgoingForDNS(out);
                }
            }
            // send probes for services
            for (ServiceInfo serviceInfo : this.getDns().getServices().values()) {
                ServiceInfoImpl info = (ServiceInfoImpl) serviceInfo;

                synchronized (info) {
                    if (info.isAssociatedWithTask(this, this.getTaskState())) {
                        logger.debug("{}.run() JmDNS {} {}", this.getName(), this.getTaskDescription(), info.getQualifiedName());
                        stateObjects.add(info);
                        out = this.buildOutgoingForInfo(info, out);
                    }
                }
            }
            if (!out.isEmpty()) {
                logger.debug("{}.run() JmDNS {} #{}", this.getName(), this.getTaskDescription(), this.getTaskState());
                this.getDns().send(out);

                // Advance the state of objects.
                this.advanceObjectsState(stateObjects);
            } else {
                // Advance the state of objects.
                this.advanceObjectsState(stateObjects);

                // If we have nothing to send, another timer taskState ahead of us has done the job for us. We can cancel.
                cancel();
                return;
            }
        } catch (Throwable e) {
            logger.warn("{}.run() exception ", this.getName(), e);
            this.recoverTask(e);
        }

        this.advanceTask();
    }

    protected abstract boolean checkRunCondition();

    protected abstract DNSOutgoing buildOutgoingForDNS(DNSOutgoing out) throws IOException;

    protected abstract DNSOutgoing buildOutgoingForInfo(ServiceInfoImpl info, DNSOutgoing out) throws IOException;

    protected abstract DNSOutgoing createOutgoing();

    protected void advanceObjectsState(List<DNSStatefulObject> list) {
        if (list != null) {
            for (DNSStatefulObject object : list) {
                synchronized (object) {
                    object.advanceState(this);
                }
            }
        }
    }

    protected abstract void recoverTask(Throwable e);

    protected abstract void advanceTask();

    /**
     * @return the taskState
     */
    protected DNSState getTaskState() {
        return this.taskState;
    }

    /**
     * @param taskState the taskState to set
     */
    protected void setTaskState(DNSState taskState) {
        this.taskState = taskState;
    }

}
