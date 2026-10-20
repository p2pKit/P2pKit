#!/usr/bin/env python3
"""Fail closed on stale limits citations/values; this is not a Kotlin compiler or semantic review."""
import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = Path('docs/reference/limits.md')
EXCERPTS = Path('scripts/tests/operational-limits-source-excerpts.json')
LINK = re.compile(r'\[([^]]+)\]\(([^)]+)\)')


def require(value, message):
    if not value:
        raise ValueError(message)


def check(root=ROOT, document=None, reader=None):
    read = reader or (lambda path: (root / path).read_text())
    text = read(DOC) if document is None else document
    cache = {}

    def source(path):
        path = Path(path)
        if path not in cache:
            cache[path] = read(path).splitlines()
        return cache[path]

    def citation(href):
        match = re.fullmatch(r'(../../library/[^#]+)#L([1-9][0-9]*)(?:-L([1-9][0-9]*))?', href)
        require(match, 'source citation requires exact line/range: ' + href)
        path = (root / DOC.parent / match[1]).resolve().relative_to(root.resolve())
        start, end = int(match[2]), int(match[3] or match[2])
        lines = source(path)
        require(1 <= start <= end <= len(lines), 'source citation out of bounds: ' + href)
        return path, start, end, '\n'.join(lines[start - 1:end])

    def declaration(path, name):
        pattern = re.compile(r'\bval\s+' + re.escape(name) + r'(?:\s*:\s*(?:Int|Long))?\s*=\s*(.*)')
        matches = [(i, pattern.search(line)) for i, line in enumerate(source(path)) if pattern.search(line)]
        require(len(matches) == 1, 'missing/ambiguous numeric declaration: ' + str(path) + ':' + name)
        start, match = matches[0]
        end, expression = start, match[1]
        while not expression.strip() or expression.rstrip().endswith(('+', '*')):
            end += 1
            require(end < len(source(path)), 'unterminated numeric declaration')
            expression += ' ' + source(path)[end].strip()
        return start + 1, end + 1, expression.strip().rstrip(',')

    def resolve(path, name, stack):
        owner, _, symbol = name.rpartition('.')
        symbol = symbol or name
        # Constants here are file-local, top-level siblings or named sibling containers.
        candidates = [path] + sorted(p.relative_to(root) for p in (root / path).parent.glob('*.kt') if p != root / path)
        if owner:
            candidates = [p for p in candidates if re.search(r'\b(?:class|object)\s+' + re.escape(owner) + r'\b', '\n'.join(source(p)))]
        else:
            local = [p for p in candidates[:1] if re.search(r'\bval\s+' + re.escape(symbol) + r'\b', '\n'.join(source(p)))]
            if local:
                candidates = local
        candidates = [p for p in candidates if re.search(r'\bval\s+' + re.escape(symbol) + r'\b', '\n'.join(source(p)))]
        require(len(candidates) == 1, 'missing/ambiguous constant reference: ' + name)
        target = candidates[0]
        key = (target, symbol)
        require(key not in stack, 'cyclic constant reference')
        expression = declaration(target, symbol)[2]
        expression = re.sub(r'(?<=\d)L\b', '', expression).replace('.toInt()', '')
        tree = ast.parse(expression, mode='eval')

        def evaluate(node):
            if isinstance(node, ast.Constant) and type(node.value) is int:
                return node.value
            if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mult)):
                left, right = evaluate(node.left), evaluate(node.right)
                return left + right if isinstance(node.op, ast.Add) else left * right
            if isinstance(node, ast.Name):
                return resolve(target, node.id, (*stack, key))
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                return resolve(target, node.value.id + '.' + node.attr, (*stack, key))
            raise ValueError('unsupported numeric expression; review explicitly: ' + expression)

        return evaluate(tree.body)

    rows = 0
    seen = set()
    supplemental = {}
    for line in text.splitlines():
        links = [(label, href) for label, href in LINK.findall(line) if '../../library/' in href]
        if line.startswith('| `'):
            columns = line.split('|')
            name = re.fullmatch(r'\s*`([^`]+)`\s*', columns[1])[1].split('.')[-1]
            number = re.match(r'\s*`([0-9,]+)`', columns[2])
            require(number and links, 'numeric row requires value and source: ' + name)
            path, start, end, _ = citation(links[0][1])
            require((path, name) not in seen, 'duplicate operational setting: ' + name)
            seen.add((path, name))
            actual_start, actual_end, _ = declaration(path, name)
            require((start, end) == (actual_start, actual_end), 'stale declaration citation: ' + name)
            expected_label = path.name + ':' + str(start) + ('–' + str(end) if end != start else '')
            require(links[0][0] == expected_label, 'displayed citation differs from fragment: ' + name)
            require(resolve(path, name, ()) == int(number[1].replace(',', '')), 'numeric value differs from source: ' + name)
            require(columns[3].strip(), 'missing scope/consequence: ' + name)
            for _, href in links[1:]:
                citation(href)
            rows += 1
        else:
            for _, href in links:
                supplemental[href] = citation(href)[3]
    expected = json.loads(read(EXCERPTS))
    require(supplemental == expected, 'supporting source excerpt changed; review citation and semantics')
    require(rows == 74, 'operational-limits inventory changed; review the documented set')
    return rows, len(supplemental)


if __name__ == '__main__':
    rows, excerpts = check()
    print(f'PASS: {rows} operational values/declaration ranges and {excerpts} supporting source excerpts')
