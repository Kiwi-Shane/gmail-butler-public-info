"""Check public site structure and local links without network access."""

import argparse
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


_REQUIRED_STRUCTURE_TAGS = frozenset({"html", "head", "title", "body", "main", "h1"})


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.tags = set()
        self.closed = set()
        self.required_tag_stack = []
        self.nesting_errors = []
        self.ids = set()
        self.links = []
        self.language = False
        self.doctype = False
        self.feed(text)
        self.close()
        self.nesting_errors.extend(
            f"unclosed required tag <{tag}>" for tag in reversed(self.required_tag_stack)
        )

    def handle_decl(self, decl):
        self.doctype |= decl.lower() == "doctype html"

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag)
        if tag in _REQUIRED_STRUCTURE_TAGS:
            self.required_tag_stack.append(tag)
        attrs = dict(attrs)
        if tag == "html":
            self.language = bool(attrs.get("lang"))
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        for key in ("href", "src"):
            if attrs.get(key):
                self.links.append(attrs[key])

    def handle_endtag(self, tag):
        self.closed.add(tag)
        if tag not in _REQUIRED_STRUCTURE_TAGS:
            return
        if tag not in self.required_tag_stack:
            self.nesting_errors.append(f"unexpected closing required tag </{tag}>")
            return
        if self.required_tag_stack[-1] != tag:
            self.nesting_errors.append(
                f"mismatched closing required tag </{tag}> while "
                f"<{self.required_tag_stack[-1]}> is open"
            )
            while self.required_tag_stack and self.required_tag_stack[-1] != tag:
                self.required_tag_stack.pop()
        self.required_tag_stack.pop()


def _case_mismatch(root, source_path, requested_path):
    requested = Path(requested_path)
    if requested.is_absolute():
        return None
    current = source_path.parent
    for component in requested.parts:
        if component in ("", "."):
            continue
        current = current.resolve()
        if not current.is_relative_to(root):
            return None
        if component == "..":
            current = current.parent
            continue
        if not current.is_dir():
            current = current / component
            continue
        try:
            entries = list(current.iterdir())
        except OSError:
            return (component, None)
        exact = next((entry for entry in entries if entry.name == component), None)
        if exact is not None:
            current = exact
            continue
        equivalents = [entry for entry in entries if entry.name.casefold() == component.casefold()]
        if len(equivalents) == 1:
            return (component, equivalents[0].name)
        candidate = current / component
        for entry in entries:
            try:
                if candidate.samefile(entry):
                    return (component, entry.name)
            except OSError:
                continue
        current = candidate
    return None


def check(root, pages):
    root = root.resolve()
    errors = []
    parsed = {}
    required = _REQUIRED_STRUCTURE_TAGS

    def read(path):
        if path not in parsed:
            parsed[path] = Page(path.read_text(encoding="utf-8"))
        return parsed[path]

    for name in pages:
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            errors.append(f"{name}: missing required page")
            continue
        page = read(path)
        errors.extend(f"{name}: required tag nesting: {issue}" for issue in page.nesting_errors)
        if not (required <= page.tags and required <= page.closed and page.language and page.doctype):
            errors.append(f"{name}: required structure, language or doctype missing")
        for link in page.links:
            parts = urlsplit(link)
            if parts.scheme or parts.netloc:
                continue
            requested_path = unquote(parts.path)
            target = (path.parent / requested_path).resolve() if requested_path else path
            if not target.is_relative_to(root):
                errors.append(f"{name}: target outside site: {link}")
            elif mismatch := _case_mismatch(root, path, requested_path):
                requested, actual = mismatch
                if actual is None:
                    errors.append(f"{name}: cannot verify target case: {link}")
                else:
                    errors.append(
                        f"{name}: local target case mismatch: {link} "
                        f"(requested {requested!r}, actual {actual!r})"
                    )
            elif not target.is_file():
                errors.append(f"{name}: missing target: {link}")
            elif parts.fragment and (target.suffix.lower() != ".html" or unquote(parts.fragment) not in read(target).ids):
                errors.append(f"{name}: missing fragment: {link}")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    errors = check(args.root, ["index.html", "privacy.html", "terms.html"])
    for error in errors:
        print(error)
    if not errors:
        print("PASS: public page structure and local links")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
