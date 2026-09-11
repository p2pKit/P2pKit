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
package dev.p2pkit.transport.lan.internal.jmdns.impl;

import java.io.IOException;
import java.net.DatagramPacket;
import java.net.MulticastSocket;

import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSConstants;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Listen for multicast packets.
 */
class SocketListener extends Thread {
    final Logger logger = LoggerFactory.getLogger(SocketListener.class);

    private final JmDNSImpl _jmDNSImpl;
    private final MulticastSocket _socket;

    SocketListener(JmDNSImpl jmDNSImpl, MulticastSocket socket) {
        super("SocketListener(" + (jmDNSImpl != null ? jmDNSImpl.getName() : "") + ")");
        this.setDaemon(true);
        this._jmDNSImpl = jmDNSImpl;
        this._socket = socket;
    }

    private void sleepThread() {
        if (_jmDNSImpl._threadSleepDurationMs > 0) {
            try {
                // sleep a small amount of time in case the network is overloaded with mdns packets (some devices do this),
                // in order to allow other threads to get some cpu time
                Thread.sleep(_jmDNSImpl._threadSleepDurationMs);
            } catch (InterruptedException e) {
                logger.warn("{}.run() interrupted ", this.getName(), e);
                Thread.currentThread().interrupt();
            }
        }
    }

    @Override
    public void run() {
        _jmDNSImpl.enterListenerExecution();
        try {
            runListener();
        } finally {
            _jmDNSImpl.exitListenerExecution();
        }
    }

    private void runListener() {
        try {
            byte[] buf = new byte[DNSConstants.MAX_MSG_ABSOLUTE];
            DatagramPacket packet = new DatagramPacket(buf, buf.length);

            while (!this._jmDNSImpl.isTerminalRequested() && !this._jmDNSImpl.isCanceling() && !this._jmDNSImpl.isCanceled()) {
                sleepThread();
                packet.setLength(buf.length);
                _socket.receive(packet);
                if (this._jmDNSImpl.isTerminalRequested() || this._jmDNSImpl.isCanceling() || this._jmDNSImpl.isCanceled() || this._jmDNSImpl.isClosing() || this._jmDNSImpl.isClosed()) {
                    break;
                }
                try {
                    if (this._jmDNSImpl.getLocalHost().shouldIgnorePacket(packet)) {
                        continue;
                    }

                    DNSIncoming msg = new DNSIncoming(packet);
                    if (msg.isValidResponseCode()) {
                        if (logger.isTraceEnabled()) {
                            logger.trace("{}.run() JmDNS in:{}", this.getName(), msg.print(true));
                        }
                        if (msg.isQuery()) {
                            // When we have a QUERY, unique means that QU is true, and we should respond to the sender directly
                            if (msg.getQuestions().stream().anyMatch(DNSEntry::isUnique)) {
                                this._jmDNSImpl.handleQuery(msg, packet.getAddress(), packet.getPort());
                            } else {
                                this._jmDNSImpl.handleQuery(msg, this._jmDNSImpl.getGroup(), DNSConstants.MDNS_PORT);
                            }
                        } else {
                            this._jmDNSImpl.handleResponse(msg);
                        }
                    } else {
                        if (logger.isDebugEnabled()) {
                            logger.debug("{}.run() JmDNS in message with error code: {}", this.getName(), msg.print(true));
                        }
                    }
                } catch (IOException e) {
                    logger.warn("{}.run() exception ", this.getName(), e);
                }
            }
        } catch (IOException e) {
            if (!this._jmDNSImpl.isTerminalRequested() && !this._jmDNSImpl.isCanceling() && !this._jmDNSImpl.isCanceled() && !this._jmDNSImpl.isClosing() && !this._jmDNSImpl.isClosed()) {
                logger.warn("{}.run() exception ", this.getName(), e);
                this._jmDNSImpl.recover();
            }
        }
        logger.trace("{}.run() exiting.", this.getName());
    }

    public JmDNSImpl getDns() {
        return _jmDNSImpl;
    }

}
