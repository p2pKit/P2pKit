#!/usr/bin/env python3
"""Offline actual curl deadline controls; no Central requests or signing.

Only the URL is redirected by the fixture boundary. Real curl must enforce
connect/transfer deadlines against local stalled TLS and HTTP peers.
"""
import http.server
import json
import os
from pathlib import Path
import shutil
import socketserver
import subprocess
import tempfile
import threading
import time
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    block_on_close = False


class Peer(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_POST(self):
        self.respond()

    def do_GET(self):
        self.respond()

    def respond(self):
        self.server.paths.append(self.path)
        upload = '/upload?' in self.path
        if self.server.mode == 'status' and upload:
            body = b'12345678-1234-1234-1234-123456789abc'
            self.send_response(201)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.server.mode == 'bytes' and len(self.server.paths) == 1:
            body = b'fixture\n'
            self.send_response(200)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            # A partial body that never completes tests total-time (not merely
            # first-byte or connection) enforcement. Delay mode sends no header.
            if self.server.mode == 'stream':
                self.send_response(200)
                self.send_header('Content-Length', '99999999')
                self.end_headers()
                self.wfile.write(b'partial')
                self.wfile.flush()
            self.server.stop.wait(5)


class CentralHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'scripts').mkdir()
        for name in ('central-http.sh', 'publish-central-portal-bundle.sh', 'check-maven-central-version.sh'):
            shutil.copyfile(ROOT / 'scripts' / name, self.root / 'scripts' / name)
        (self.root / 'gradle.properties').write_text(
            'GROUP=fixture.group\nVERSION_NAME=9.8.7-rc6\nLATEST_PUBLISHED_VERSION=9.8.7-rc5\n')
        self.bundle = self.root / 'bundle.zip'
        with zipfile.ZipFile(self.bundle, 'w') as archive:
            archive.writestr('fixture/group/p2p-core/9.8.7-rc6/p2p-core-9.8.7-rc6.pom', b'fixture\n')
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        # No shell parsing of URLs/credentials, no network other than loopback.
        real_curl = shutil.which('curl')
        self.assertIsNotNone(real_curl)
        (self.bin / 'curl').write_text('#!/usr/bin/env python3\n'
            'import json,os,sys,urllib.parse\n'
            'args=sys.argv[1:]\n'
            'with open(os.environ["CURL_CALLS"],"a") as f: f.write(json.dumps(args)+"\\n")\n'
            'u=urllib.parse.urlsplit(args[-1])\n'
            'args[-1]=os.environ["LOCAL_URL"]+u.path+("?"+u.query if u.query else "")\n'
            f'os.execv({real_curl!r}, [{real_curl!r}, *args])\n')
        (self.bin / 'curl').chmod(0o755)
        self.env = dict(os.environ, PATH=f'{self.bin}:{os.environ["PATH"]}',
            CURL_CALLS=str(self.root / 'calls.jsonl'), P2PKIT_CENTRAL_TEST_MODE='1',
            P2PKIT_CENTRAL_PHASE_SECONDS='0.9', P2PKIT_CENTRAL_REQUEST_SECONDS='0.3',
            P2PKIT_CENTRAL_POLL_SECONDS='0', P2PKIT_CENTRAL_MAX_POLLS='100',
            MAVEN_CENTRAL_USERNAME='disposable-user', MAVEN_CENTRAL_PASSWORD='disposable-password',
            GITHUB_ACTIONS='false', GITHUB_SHA='1' * 40)
        # Avoid ambient proxies/configuration contacting anything outside this fixture.
        self.env.update(NO_PROXY='*', no_proxy='*')

    def peer(self, mode):
        server = Server(('127.0.0.1', 0), Peer)
        server.mode, server.paths, server.stop = mode, [], threading.Event()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def close():
            server.stop.set()
            server.shutdown()
            server.server_close()
            thread.join()
        self.addCleanup(close)
        self.env['LOCAL_URL'] = f'http://127.0.0.1:{server.server_port}'
        return server

    def run_script(self, name, *args):
        start = time.monotonic()
        result = subprocess.run(['bash', str(self.root / 'scripts' / name), *map(str, args)],
            env=self.env, text=True, capture_output=True, timeout=5)
        self.assertLess(time.monotonic() - start, 3, result.stderr)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertNotIn('RESULT: PASS', result.stdout)
        return result

    def events(self):
        return [json.loads(line) for line in (self.root / 'evidence/portal-events.jsonl').read_text().splitlines()]

    def test_stalled_upload_is_ambiguous_and_never_retried(self):
        server = self.peer('delay')
        result = self.run_script('publish-central-portal-bundle.sh', self.bundle, self.root / 'evidence')
        self.assertIn('outcome is ambiguous', result.stderr)
        self.assertEqual(len(server.paths), 1)
        self.assertEqual([e['event'] for e in self.events()], ['upload_started', 'upload_ambiguous'])
        self.assertEqual(self.events()[-1]['detail'], 'curl_exit_28')
        args = json.loads((self.root / 'calls.jsonl').read_text())
        self.assertEqual(args[0], '--disable')
        self.assertNotIn('--retry', args)

    def test_stalled_status_stops_at_phase_deadline_and_retains_deployment(self):
        server = self.peer('status')
        result = self.run_script('publish-central-portal-bundle.sh', self.bundle, self.root / 'evidence')
        self.assertIn('bounded polling window', result.stderr)
        self.assertEqual(sum('/upload?' in p for p in server.paths), 1)
        self.assertGreaterEqual(sum('/status?' in p for p in server.paths), 2)
        self.assertLess(len(server.paths), 10)
        self.assertEqual(self.events()[-1]['event'], 'publication_timeout')
        self.assertTrue((self.root / 'evidence/deployment-id.txt').is_file())
        calls = [json.loads(line) for line in (self.root / 'calls.jsonl').read_text().splitlines()]
        # The last poll is clipped to remaining phase time, not a fresh budget.
        self.assertLess(float(calls[-1][calls[-1].index('--max-time') + 1]), 0.3)

    def test_absence_never_ending_body_is_not_absence(self):
        self.peer('stream')
        result = self.run_script('check-maven-central-version.sh', 'absent')
        self.assertIn('could not check Maven Central', result.stderr)

    def test_propagation_stall_is_bounded(self):
        server = self.peer('delay')
        result = self.run_script('check-maven-central-version.sh', 'published', self.bundle)
        self.assertIn('did not propagate within the bounded window', result.stderr)
        self.assertLess(len(server.paths), 10)

    def test_published_bytes_stall_is_not_a_match(self):
        self.peer('bytes')
        result = self.run_script('check-maven-central-version.sh', 'published', self.bundle)
        self.assertIn('published files failed verification', result.stderr)

    def test_stalled_tls_handshake_has_connection_deadline(self):
        # Accept TCP, never answer TLS. A real external delayed SYN is deliberately
        # not needed; curl's connect timer also bounds TLS establishment.
        class Blackhole(socketserver.BaseRequestHandler):
            def handle(inner):
                inner.server.stop.wait(5)
        class TCP(socketserver.ThreadingMixIn, socketserver.TCPServer):
            daemon_threads = True
            block_on_close = False
        server = TCP(('127.0.0.1', 0), Blackhole)
        server.stop = threading.Event()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (server.stop.set(), server.shutdown(), server.server_close(), thread.join()))
        self.env['LOCAL_URL'] = f'https://127.0.0.1:{server.server_address[1]}'
        result = self.run_script('check-maven-central-version.sh', 'absent')
        self.assertIn('could not check Maven Central', result.stderr)
        self.assertIn('28', result.stderr)

    def test_original_job_deadline_clips_stalled_request_not_a_new_phase_window(self):
        server = self.peer('status')
        self.env['P2PKIT_CENTRAL_PHASE_SECONDS'] = '2'
        self.env['P2PKIT_CENTRAL_REQUEST_SECONDS'] = '1'
        self.env['P2PKIT_CENTRAL_JOB_DEADLINE'] = str(time.monotonic() + 0.8)
        result = self.run_script('publish-central-portal-bundle.sh', self.bundle, self.root / 'evidence')
        self.assertIn('bounded polling window', result.stderr)
        self.assertEqual(sum('/upload?' in p for p in server.paths), 1)
        self.assertEqual(sum('/status?' in p for p in server.paths), 1)
        calls = [json.loads(line) for line in (self.root / 'calls.jsonl').read_text().splitlines()]
        self.assertLess(float(calls[-1][calls[-1].index('--max-time') + 1]), 0.8)
        self.assertEqual(self.events()[-1]['event'], 'publication_timeout')

    def test_expired_original_job_never_starts_upload(self):
        self.peer('delay')
        self.env['P2PKIT_CENTRAL_JOB_DEADLINE'] = str(time.monotonic() - 1)
        result = self.run_script('publish-central-portal-bundle.sh', self.bundle, self.root / 'evidence')
        self.assertIn('no upload attempted', result.stderr)
        self.assertEqual(self.events(), [])
        self.assertFalse((self.root / 'calls.jsonl').exists())

    def test_hosted_publisher_cannot_omit_original_job_clock(self):
        self.peer('delay')
        self.env.update(GITHUB_ACTIONS='true', GITHUB_JOB='publish-release')
        self.env.pop('P2PKIT_CENTRAL_JOB_DEADLINE', None)
        result = self.run_script('publish-central-portal-bundle.sh', self.bundle, self.root / 'evidence')
        self.assertIn('requires original-job HTTP deadline', result.stderr)
        self.assertFalse((self.root / 'calls.jsonl').exists())

    def test_expired_phase_does_not_start_curl_and_zero_override_is_rejected(self):
        self.env['P2PKIT_CENTRAL_PHASE_SECONDS'] = '0'
        self.peer('delay')
        result = self.run_script('check-maven-central-version.sh', 'absent')
        self.assertIn('invalid Central phase budget', result.stderr)
        self.assertFalse((self.root / 'calls.jsonl').exists())
        result = subprocess.run(['bash', '-c',
            'source "$1"; CENTRAL_HTTP_DEADLINE=0; central_http 120 https://example.invalid',
            'fixture', str(self.root / 'scripts/central-http.sh')], env=self.env, capture_output=True, timeout=3)
        self.assertEqual(result.returncode, 28)
        self.assertFalse((self.root / 'calls.jsonl').exists())


if __name__ == '__main__':
    unittest.main()
