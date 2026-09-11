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
package dev.p2pkit.transport.lan.internal.jmdns.impl.tasks.resolver;

import java.io.IOException;

import dev.p2pkit.transport.lan.internal.jmdns.ServiceInfo;
import dev.p2pkit.transport.lan.internal.jmdns.impl.DNSOutgoing;
import dev.p2pkit.transport.lan.internal.jmdns.impl.DNSQuestion;
import dev.p2pkit.transport.lan.internal.jmdns.impl.DNSRecord;
import dev.p2pkit.transport.lan.internal.jmdns.impl.JmDNSImpl;
import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSConstants;
import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSRecordClass;
import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSRecordType;

/**
 * The ServiceResolver queries three times consecutively for services of a given type, and then removes itself from the timer.
 * <p>
 * The ServiceResolver will run only if JmDNS is in state ANNOUNCED. REMIND: Prevent having multiple service resolvers for the same type in the timer queue.
 * </p>
 */
public class ServiceResolver extends DNSResolverTask {

    private final String type;

    public ServiceResolver(JmDNSImpl jmDNSImpl, String type) {
        super(jmDNSImpl);
        this.type = type;
    }

    /*
     * (non-Javadoc)
     * @see dev.p2pkit.transport.lan.internal.jmdns.impl.tasks.DNSTask#getName()
     */
    @Override
    public String getName() {
        return "ServiceResolver(" + (this.getDns() != null ? this.getDns().getName() : "") + ")";
    }

    /*
     * (non-Javadoc)
     * @see dev.p2pkit.transport.lan.internal.jmdns.impl.tasks.Resolver#addAnswers(dev.p2pkit.transport.lan.internal.jmdns.impl.DNSOutgoing)
     */
    @Override
    protected DNSOutgoing addAnswers(DNSOutgoing out) throws IOException {
        DNSOutgoing newOut = out;
        long now = System.currentTimeMillis();
        for (ServiceInfo info : this.getDns().getServices().values()) {
            newOut = this.addAnswer(newOut, new DNSRecord.Pointer(info.getType(), DNSRecordClass.CLASS_IN, DNSRecordClass.NOT_UNIQUE, DNSConstants.DNS_TTL, info.getQualifiedName()), now);
        }
        return newOut;
    }

    /*
     * (non-Javadoc)
     * @see dev.p2pkit.transport.lan.internal.jmdns.impl.tasks.Resolver#addQuestions(dev.p2pkit.transport.lan.internal.jmdns.impl.DNSOutgoing)
     */
    @Override
    protected DNSOutgoing addQuestions(DNSOutgoing out) throws IOException {
        DNSOutgoing newOut = out;
        newOut = this.addQuestion(newOut, DNSQuestion.newQuestion(type, DNSRecordType.TYPE_PTR, DNSRecordClass.CLASS_IN, DNSRecordClass.NOT_UNIQUE));
        return newOut;
    }

    /*
     * (non-Javadoc)
     * @see dev.p2pkit.transport.lan.internal.jmdns.impl.tasks.Resolver#description()
     */
    @Override
    protected String description() {
        return "querying service";
    }
}
