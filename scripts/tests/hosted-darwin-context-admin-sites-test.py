#!/usr/bin/env python3
"""Five offline administrative-refusal controls, not native qualification.

All OS returns below are synthetic. No subprocess, socket, native library,
privileged operation, key use, evidence export or workflow execution is allowed.
"""
import ast
import contextlib
import copy
import ctypes  # Import before forbidding native-library acquisition.
import hashlib
import importlib.util
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, call, patch

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/run-hosted-darwin-context-experiment.py"
BASE_AST_SHA256 = "6d1539c3daef94454d6ba1c02a8f231a2ae6c8dd539ce3aeb13be7cfeb3226e4"
CANARY = "SYNTHETIC_PRIVATE_CANARY"
FAILURE = "P2PKIT_CONTEXT_FAILURE|ADMIN_CREATE|IDENTITY_CHANGED|NONE"
PREFIX = "P2PKIT_CONTEXT_ADMIN_SITE|"
# Exact additions independently inspected against35968f11; these pins validate
# what is removed before the complete original-runtime AST comparison.
REVIEWED_ADDITION_AST_SHA256 = {
    "ADMIN_SITES": "762f5ca3cceae523bd3e1e261faa0741eb8b98a6bbe962deaa27846f485083aa",
    "ADMIN_ITEMS": "cd26fbdd342c5dda7c08006a28f2faf73c6f4e14a97352e776f4494a524bbdb3",
    "admin_object_item": "b366c957e825328b464544e5051ba5e29a7fdbf4492b4315f2188b888aa34150",
    "public_admin_site": "ca48644e27b36ffaa0af7326a97dc0c845d42e2a450728565fb5b37e79df8b1d",
}


def offline(event, _args):
    if event.startswith(("socket.", "subprocess.")) or event in {
        "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty",
        "os.kill", "os.killpg", "ctypes.dlopen", "ctypes.dlsym", "os.putenv", "os.unsetenv",
        "os.setuid", "os.seteuid", "os.setgid", "os.setegid", "os.setgroups", "os.chown",
        "os.setreuid", "os.setregid", "os.setresuid", "os.setresgid",
    }:
        raise AssertionError("OFFLINE_ADMIN_SITE_FORBIDDEN_OPERATION")


if len(sys.argv) != 1 or not sys.flags.isolated or not sys.flags.no_site or not sys.dont_write_bytecode:
    raise SystemExit("FIXED_OFFLINE_ADMIN_SITE_INVOCATION_REQUIRED")
sys.addaudithook(offline)
spec = importlib.util.spec_from_file_location("darwin_context_admin_site_controls", SOURCE)
M = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = M
spec.loader.exec_module(M)

# Independently transcribed from the eight original35968f11 guard groups.
CONDITIONS = {
    "META_KIND": 'kind in ("directory", "file")',
    "META_TYPE": "is_type",
    "META_OWNER": 'value["uid"] == 0',
    "META_GROUP": '0 <= value["gid"] < 2 ** 32',
    "META_INODE": 'value["ino"] > 0',
    "META_WRITE_MODE": 'not value["mode"] & 0o022',
    "META_LINKS": '(kind == "directory" and expected_os_links is None) or (kind == "file" and ((expected_os_links is None and value["nlink"] == 1) or (path in OS_TOOLS and type(expected_os_links) is int and expected_os_links > 0 and value["nlink"] == expected_os_links)))',
    "META_EXACT_MODE": 'mode is None or stat.S_IMODE(value["mode"]) == mode',
    "META_LIST_TYPE": '(line[0][0] == "d") == (kind == "directory")',
    "META_SIZE": 'size is None or value["size"] == size',
    "META_PREVIOUS": 'all(value[key] == previous[key] for key in ("dev", "ino", "mode", "uid", "gid", "nlink"))',
    "META_STABLE": "first == second",
    "PLIST_TEE": 'returned["stdout"] == self.plist',
    "PLIST_CAT": 'self._run(["/bin/cat", self.path], "ADMIN_CREATE")["stdout"] == self.plist',
}
OS_ITEMS = {
    "/": "ROOT", "/private": "PRIVATE", "/private/var": "PRIVATE_VAR", "/private/var/db": "PRIVATE_VAR_DB",
    "/usr": "USR", "/usr/bin": "USR_BIN", "/bin": "BIN",
    "/usr/bin/sudo": "SUDO", "/usr/bin/mktemp": "MKTEMP", "/usr/bin/stat": "STAT", "/usr/bin/tee": "TEE",
    "/bin/cat": "CAT", "/bin/ls": "LS", "/bin/rm": "RM", "/bin/rmdir": "RMDIR",
    "/bin/launchctl": "LAUNCHCTL", "/usr/bin/git": "GIT", "/usr/bin/sw_vers": "SW_VERS",
}


def form(value):
    """Python3.9-compatible AST identity; newer empty type_params adds no syntax."""
    if isinstance(value, ast.AST):
        pairs = []
        for key, item in ast.iter_fields(value):
            if key == "type_params":
                if item != []:
                    raise AssertionError("NO_ADDED_TYPE_PARAMETER_SYNTAX")
                continue
            pairs.append((key, form(item)))
        return type(value).__name__, pairs
    if isinstance(value, list):
        return [form(item) for item in value]
    return value


def ast_hash(value):
    return hashlib.sha256(repr(form(value)).encode("utf-8")).hexdigest()


def expression(value):
    return form(ast.parse(value, mode="eval").body)


class AdminSites(unittest.TestCase):
    def _site(self, error, site, item):
        self.assertIsInstance(error, M.ExperimentError)
        self.assertEqual(M.public_error(error), FAILURE)
        self.assertIsNone(M.public_source_site(error))
        self.assertEqual(M.public_admin_site(error), PREFIX + site + "|" + item)
        self.assertEqual(str(error), "ADMIN_CREATE/IDENTITY_CHANGED/NONE")

    def _refusal(self, callback, site, item):
        with self.assertRaises(M.ExperimentError) as raised:
            callback()
        self._site(raised.exception, site, item)

    def _original_ast(self, source):
        tree = ast.parse(source, feature_version=(3, 9))
        # Exact added definitions are pinned only after their independent source
        # inspection; no arbitrary function or annotation can be stripped here.
        additions = {}
        for node in tree.body:
            name = node.name if isinstance(node, ast.FunctionDef) else (
                node.targets[0].id if isinstance(node, ast.Assign) and len(node.targets) == 1 and
                isinstance(node.targets[0], ast.Name) else None)
            if name in REVIEWED_ADDITION_AST_SHA256:
                self.assertNotIn(name, additions)
                self.assertEqual(ast_hash(node), REVIEWED_ADDITION_AST_SHA256[name])
                additions[name] = node
        self.assertEqual(set(additions), {"ADMIN_SITES", "ADMIN_ITEMS", "admin_object_item", "public_admin_site"})
        os_roster = next(node for node in tree.body if isinstance(node, ast.Assign) and
                         isinstance(node.targets[0], ast.Name) and node.targets[0].id == "SOURCE_OS_ITEMS")
        self.assertEqual(tree.body.index(additions["ADMIN_SITES"]), tree.body.index(os_roster) + 1)
        self.assertEqual(tree.body.index(additions["ADMIN_ITEMS"]), tree.body.index(os_roster) + 2)
        original_formatter = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "public_source_site")
        stage_wrapper = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "at_stage")
        self.assertEqual([tree.body.index(additions[name]) for name in ("admin_object_item", "public_admin_site")],
                         [tree.body.index(original_formatter) + 1, tree.body.index(original_formatter) + 2])
        self.assertEqual(tree.body.index(stage_wrapper), tree.body.index(original_formatter) + 3)
        tree.body = [node for node in tree.body if node not in additions.values()]
        functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
        init = next(node for node in classes["ExperimentError"].body if isinstance(node, ast.FunctionDef) and node.name == "__init__")
        require = functions["require"]
        exact_arguments = ast.parse("def annotated(*, source_site=None, source_item=None, admin_site=None, admin_item=None): pass").body[0].args.kwonlyargs
        for function in (init, require):
            self.assertEqual(form(function.args.kwonlyargs), form(exact_arguments))
            self.assertEqual([form(node) for node in function.args.kw_defaults],
                             [expression("None")] * 4)
            function.args.kwonlyargs = function.args.kwonlyargs[:2]
            function.args.kw_defaults = function.args.kw_defaults[:2]
        added_assignment = ast.parse("self.admin_site, self.admin_item = admin_site, admin_item").body[0]
        matches = [node for node in init.body if form(node) == form(added_assignment)]
        self.assertEqual(len(matches), 1)
        self.assertEqual(init.body.index(matches[0]), 4)
        init.body.remove(matches[0])

        methods = {node.name: node for node in classes["Admin"].body if isinstance(node, ast.FunctionDef)}
        seen = []
        for name, function in (("parse_admin_metadata", functions["parse_admin_metadata"]),
                               ("metadata", methods["metadata"]), ("create", methods["create"])):
            for node in ast.walk(function):
                if not isinstance(node, ast.Call):
                    continue
                annotations = {kw.arg: kw.value for kw in node.keywords if kw.arg in ("admin_site", "admin_item")}
                if not annotations:
                    continue
                self.assertEqual(set(annotations), {"admin_site", "admin_item"})
                self.assertEqual(len(node.keywords), 2)
                self.assertIsInstance(node.func, ast.Name)
                self.assertEqual(node.func.id, "require")
                self.assertEqual(len(node.args), 3)
                self.assertEqual([form(value) for value in node.args[1:]],
                                 [expression('"ADMIN_CREATE"'), expression('"IDENTITY_CHANGED"')])
                self.assertIsInstance(annotations["admin_site"], ast.Constant)
                site = annotations["admin_site"].value
                self.assertIn(site, CONDITIONS)
                self.assertNotIn(site, seen)
                self.assertEqual(form(node.args[0]), expression(CONDITIONS[site]))
                self.assertEqual(name, "metadata" if site == "META_STABLE" else
                                 "create" if site.startswith("PLIST_") else "parse_admin_metadata")
                expected_item = '"PRIVATE_FILE"' if name == "create" else "admin_object_item(path, kind)"
                self.assertEqual(form(annotations["admin_item"]), expression(expected_item))
                seen.append(site)
        self.assertEqual(set(seen), set(CONDITIONS))

        parser = functions["parse_admin_metadata"]
        initial_sites = list(CONDITIONS)[:7]
        split = []
        for index, statement in enumerate(parser.body):
            if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
                continue
            site = next((kw.value.value for kw in statement.value.keywords
                         if kw.arg == "admin_site" and isinstance(kw.value, ast.Constant)), None)
            if site in initial_sites:
                split.append((index, site, statement))
        self.assertEqual([site for _index, site, _node in split], initial_sites)
        self.assertEqual([index for index, _site, _node in split], list(range(split[0][0], split[0][0] + 7)))
        first = copy.deepcopy(split[0][2])
        first.value.args[0] = ast.BoolOp(op=ast.And(), values=[node.value.args[0] for _index, _site, node in split])
        parser.body[split[0][0]:split[0][0] + 7] = [first]
        # The sole forwarding call is checked separately, not erased generically.
        forwarded = [node for node in ast.walk(require) if isinstance(node, ast.Call) and
                     isinstance(node.func, ast.Name) and node.func.id == "ExperimentError"]
        self.assertEqual(len(forwarded), 1)
        self.assertEqual({kw.arg: form(kw.value) for kw in forwarded[0].keywords if kw.arg.startswith("admin_")},
                         {"admin_site": expression("admin_site"), "admin_item": expression("admin_item")})
        for function in (parser, methods["metadata"], methods["create"], require):
            for node in ast.walk(function):
                if isinstance(node, ast.Call):
                    node.keywords = [kw for kw in node.keywords if kw.arg not in ("admin_site", "admin_item")]
        handler = functions["main"].body[-1].handlers[0]
        extra = ast.parse("admin_diagnostic = public_admin_site(error)\nif admin_diagnostic is not None:\n    print(admin_diagnostic)\n").body
        matching = [index for index in range(len(handler.body) - 1)
                    if form(handler.body[index:index + 2]) == form(extra)]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0], len(handler.body) - 3)
        del handler.body[matching[0]:matching[0] + 2]
        self.assertEqual(ast_hash(tree), BASE_AST_SHA256)
        return tree

    def test_01_annotations_preserve_complete_runtime_ast(self):
        source = SOURCE.read_text(encoding="utf-8")
        self._original_ast(source)
        for old, new in (
            ('value["uid"] == 0', 'value["uid"] in (0, 501)'),
            ('not value["mode"] & 0o022', 'not value["mode"] & 0o002'),
            ('value["nlink"] == 1', 'value["nlink"] >= 1'),
            ("first == second", "True"),
            ('require(error.errno == errno.ENOENT, "RETIRE"', 'require(True, "RETIRE"'),
            ("CASE_SECONDS = 120, 180, 40", "CASE_SECONDS = 120, 180, 41"),
            ('admin_site="META_OWNER"', 'admin_site="META_TYPE"'),
            ('admin_site=None, admin_item=None', 'admin_site: object=None, admin_item=None'),
            ('env.get("GITHUB_SHA") == env.get("GITHUB_WORKFLOW_SHA") == request["source_sha"]',
             'env.get("GITHUB_SHA") == env.get("GITHUB_WORKFLOW_SHA")'),
            ('context.recipient_original', 'context.changed_recipient_original'),
        ):
            changed = source.replace(old, new, 1)
            self.assertNotEqual(changed, source)
            with self.assertRaises(AssertionError):
                self._original_ast(changed)

    def test_02_parser_failure_sites_and_preserved_short_circuit_order(self):
        path = "/usr/bin/stat"
        raw = b"1:2:100600:0:0:1:0:170:170\n"
        acl = ("-rw------- 1 root wheel 0 Sep 29 00:00 " + path + "\n").encode("ascii")
        original = M.parse_admin_metadata(raw, acl, path, "file", mode=0o600, size=0)
        self.assertEqual(original, dict(dev=1, ino=2, mode=0o100600, uid=0, gid=0, nlink=1, size=0, mtime=170, ctime=170))
        cases = (
            ("META_KIND", {}, {"kind": "socket"}, None, "NONE"),
            ("META_TYPE", {2: "40700", 3: "501"}, {}, None, "STAT"),
            ("META_OWNER", {3: "501", 2: "100622"}, {}, None, "STAT"),
            ("META_GROUP", {4: str(2 ** 32), 1: "0"}, {}, None, "STAT"),
            ("META_INODE", {1: "0", 2: "100622"}, {}, None, "STAT"),
            ("META_WRITE_MODE", {2: "100622", 5: "2"}, {}, None, "STAT"),
            ("META_LINKS", {5: "2"}, {}, None, "STAT"),
            ("META_EXACT_MODE", {}, {"mode": 0o700}, None, "STAT"),
            ("META_LIST_TYPE", {}, {}, acl.replace(b"-rw-------", b"drw-------"), "STAT"),
            ("META_SIZE", {}, {"size": 1}, None, "STAT"),
            ("META_PREVIOUS", {}, {"previous": {**original, "dev": 2}}, None, "STAT"),
        )
        for site, fields, options, listing, item in cases:
            changed = raw.decode("ascii").strip().split(":")
            for index, value in fields.items():
                changed[index] = value
            arguments = {"kind": "file", "mode": 0o600, "size": 0, **options}
            self._refusal(lambda: M.parse_admin_metadata(":".join(changed).encode("ascii"),
                          acl if listing is None else listing, path, **arguments), site, item)
        for listing in (acl.replace(b"-rw-------", b"-rw-------+"), acl + b" 0: user:synthetic allow read\n"):
            with self.assertRaises(M.ExperimentError) as raised:
                M.parse_admin_metadata(raw, listing, path, "file")
            self.assertEqual(raised.exception.reason, "UNSUPPORTED")
            self.assertIsNone(M.public_admin_site(raised.exception))

    def test_03_three_return_stability_and_private_plist_readbacks(self):
        admin = M.Admin.__new__(M.Admin)
        admin._run = Mock(side_effect=[{"stdout": b"FIRST"}, {"stdout": b"LISTING"}, {"stdout": b"SECOND"}])
        with patch.object(M, "parse_admin_metadata") as parser:
            self._refusal(lambda: admin.metadata("/private/var/db", "directory"), "META_STABLE", "PRIVATE_VAR_DB")
            parser.assert_not_called()
        self.assertEqual(admin._run.call_args_list, [
            call(["/usr/bin/stat", "-f", M.STAT_FORMAT, "/private/var/db"], "ADMIN_CREATE"),
            call(["/bin/ls", "-lde", "/private/var/db"], "ADMIN_CREATE"),
            call(["/usr/bin/stat", "-f", M.STAT_FORMAT, "/private/var/db"], "ADMIN_CREATE"),
        ])
        root = "/private/var/db/p2pkit-context.ABCDEFGHIJ"
        path = root + "/job.KLMNOPQRST"
        for site, count in (("PLIST_TEE", 3), ("PLIST_CAT", 4)):
            admin = M.Admin.__new__(M.Admin)
            admin.root, admin.path, admin.plist = None, None, b"SYNTHETIC_PLIST_NOT_INSTALLED"
            admin.metadata = Mock(return_value={"synthetic": True})
            returns = [{"stdout": (root + "\n").encode()}, {"stdout": (path + "\n").encode()},
                       {"stdout": b"WRONG" if site == "PLIST_TEE" else admin.plist}, {"stdout": b"WRONG"}]
            admin._run = Mock(side_effect=returns)
            with patch.object(M, "write_new") as write:
                self._refusal(admin.create, site, "PRIVATE_FILE")
                write.assert_not_called()
            self.assertEqual(admin._run.call_count, count)
            self.assertEqual(admin.metadata.call_count, count)
            self.assertEqual(admin._run.call_args_list[2], call(["/usr/bin/tee", path], "ADMIN_CREATE", input_raw=admin.plist))
            if site == "PLIST_CAT":
                self.assertEqual(admin._run.call_args_list[3], call(["/bin/cat", path], "ADMIN_CREATE"))

    def test_04_fixed_public_containment(self):
        class Hostile:
            def __str__(self):
                raise AssertionError("DO_NOT_STRINGIFY_UNTRUSTED_DIAGNOSTIC")

            __repr__ = __str__

            def __hash__(self):
                raise AssertionError("DO_NOT_HASH_UNTRUSTED_DIAGNOSTIC")

            def __eq__(self, _other):
                raise AssertionError("DO_NOT_COMPARE_UNTRUSTED_DIAGNOSTIC")

        class StringSubclass(str):
            pass

        items = {*OS_ITEMS.values(), "PRIVATE_DIRECTORY", "PRIVATE_FILE"}
        self.assertEqual(M.ADMIN_SITES, frozenset(CONDITIONS))
        self.assertEqual(M.ADMIN_ITEMS, frozenset(items))
        for site in CONDITIONS:
            for item in items:
                self._site(M.ExperimentError("ADMIN_CREATE", "IDENTITY_CHANGED", admin_site=site, admin_item=item), site, item)
        bad = (None, True, 123, [], {}, b"META_OWNER", CANARY, "/private/" + CANARY,
               "META_OWNER\n" + CANARY, Hostile(), StringSubclass("META_OWNER"))
        for value in bad:
            error = M.ExperimentError("ADMIN_CREATE", "IDENTITY_CHANGED", admin_site=value, admin_item=value)
            self._site(error, "UNKNOWN", "NONE")
            error.admin_site = "META_OWNER"
            self._site(error, "META_OWNER", "NONE")
            self.assertEqual(M.admin_object_item(value, "file"), "PRIVATE_FILE" if type(value) is str else "NONE")
            self.assertEqual(M.admin_object_item("/usr/bin/stat", value), "NONE")
        for attribute in ("stage", "reason"):
            for value in bad:
                error = M.ExperimentError("ADMIN_CREATE", "IDENTITY_CHANGED", admin_site="META_OWNER", admin_item="ROOT")
                setattr(error, attribute, value)
                self.assertIsNone(M.public_admin_site(error))
        error = M.ExperimentError("ADMIN_CREATE", "IDENTITY_CHANGED")
        del error.admin_site
        del error.admin_item
        self._site(error, "UNKNOWN", "NONE")
        for path, item in OS_ITEMS.items():
            self.assertEqual(M.admin_object_item(path, "directory" if path in ("/", "/private", "/private/var", "/private/var/db", "/usr", "/usr/bin", "/bin") else "file"), item)
        self.assertEqual(M.admin_object_item("/private/" + CANARY, "directory"), "PRIVATE_DIRECTORY")
        self.assertEqual(M.admin_object_item("/private/" + CANARY, "file"), "PRIVATE_FILE")
        for stage in M.STAGES:
            for reason in M.REASONS:
                if (stage, reason) != ("ADMIN_CREATE", "IDENTITY_CHANGED"):
                    self.assertIsNone(M.public_admin_site(M.ExperimentError(stage, reason, admin_site="META_OWNER", admin_item="ROOT")))
        for error in (RuntimeError(CANARY), OSError(CANARY), SystemExit(CANARY)):
            self.assertIsNone(M.public_admin_site(error))
        with patch.object(M, "ExperimentError", side_effect=AssertionError("SUCCESS_HAS_NO_DIAGNOSTIC_ERROR")) as constructor:
            self.assertIsNone(M.require(True, "ADMIN_CREATE", "IDENTITY_CHANGED", admin_site=Hostile(), admin_item=Hostile()))
            constructor.assert_not_called()

    def test_05_main_refusal_cannot_seal_or_upload(self):
        error = M.ExperimentError("ADMIN_CREATE", "IDENTITY_CHANGED", admin_site="META_OWNER", admin_item="ROOT")
        expected = FAILURE + "\nP2PKIT_CONTEXT_ADMIN_SITE|META_OWNER|ROOT\n"
        for returned, failure, output in ((0, None, ""), (1, None, ""), (None, error, expected),
                                          (None, RuntimeError(CANARY), "P2PKIT_CONTEXT_FAILURE|PREPARE|REFUSED|UNKNOWN\n")):
            text = io.StringIO()
            with patch.object(M.sys, "argv", ["SYNTHETIC_ENTRY", "experiment"]), patch.object(M.os, "umask") as umask, \
                    patch.object(M, "experiment", return_value=returned, side_effect=failure) as experiment, \
                    patch.object(M, "finish_export") as export, patch.object(M, "upload_guard") as upload, \
                    patch.object(M, "write_new") as write, patch.object(M, "Darwin") as native, \
                    patch.object(M, "capture_fixed") as capture, contextlib.redirect_stdout(text):
                self.assertEqual(M.main(), returned if failure is None else 2)
                experiment.assert_called_once_with()
                umask.assert_called_once_with(0o077)
                for endpoint in (export, upload, write, native, capture):
                    endpoint.assert_not_called()
            self.assertEqual(text.getvalue(), output)
            self.assertNotIn(CANARY, text.getvalue())


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(AdminSites)
    if suite.countTestCases() != 5:
        raise SystemExit("FIXED_FIVE_ADMIN_SITE_METHODS_REQUIRED")
    result = unittest.TextTestRunner(verbosity=2, failfast=True).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
