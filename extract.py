#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import email
import logging
import pathlib
import quopri
import sys
import time
import urllib.parse

import bs4

logging.basicConfig(
    level=logging.DEBUG,
    format="%(pathname)s:%(lineno)d - %(asctime)s - %(levelname)s - %(message)s",
)


def log(msg):
    logging.info(msg)


MAGIC_EXT = "mhtml.blink"
DEFAULT_DECODE = "latin1"


def unquote(quoted):
    decoded = quopri.decodestring(quoted)
    content = decoded.decode(DEFAULT_DECODE)
    return content


def extract_file_ext(file_name):
    return pathlib.Path(file_name).suffix.replace(".", "")


def extract_filename(file_path, ctype):
    file_name = file_path.name  # myfile.png
    ext = extract_file_ext(file_name)
    if ctype[-1] == "svg+xml":
        ctype.append("svg")

    if ext in ctype:
        return file_name

    split = file_name.split("@")
    if split[-1] == MAGIC_EXT:
        return f"{split[-0]}.css"

    return f"{file_name}.{ctype[-1]}"


class Extract:
    def __init__(self, source_file):
        with open(source_file, "r") as f:
            self.msg = email.message_from_file(f)

        self.html = None
        self.attrs = {}
        self.payloads = {}
        for part in self.msg.walk():
            if not part.is_multipart():
                self.parse_part(part)

    def files(self):
        return list(self.attrs.keys())

    def replace_filename(self, uri, file_name):
        local_file = f"./{file_name}"
        link = self.get(href=uri)
        if link:
            link["href"] = local_file
            return local_file
        logging.warning(f"replace_filename.not-found.href={uri}")

    def add_file(self, uri, ctype):
        sections = urllib.parse.urlparse(uri)
        file_path = pathlib.Path(sections.path)
        file_name = extract_filename(file_path, ctype)
        file_ext = extract_file_ext(file_name)

        attrs = {
            "uri": uri,
            "uri.sections": sections,
            "path": file_path,
            "name": file_name,
            "ext": file_ext,
        }
        self.attrs[file_name] = attrs
        self.replace_filename(uri, file_name)
        return attrs

    def save(self, dest="."):
        root = pathlib.Path(dest) / self.folder
        root.mkdir(exist_ok=True)

        def write(f, s):
            (root / f).write_text(s)

        write("index.html", str(self))
        for file, data in self.payloads.items():
            write(file, data)

        return root

    def get(self, name=None, attrs={}, **kwargs):
        return self.soup.find(name, attrs={}, **kwargs) if self.soup else None

    def get_all(self, name=None, attrs={}, **kwargs):
        return self.soup.find_all(name, attrs={}, **kwargs) if self.soup else None

    def update_link(self, uri, file_name):
        pass

    def parse_part(self, part):
        ctype = part.get("Content-Type").split("/")
        quoted = part.get("Content-Transfer-Encoding") == "quoted-printable"
        uri = part.get("Content-Location")
        raw_payload = part.get_payload()
        payload = unquote(raw_payload) if quoted else raw_payload

        data_dir = pathlib.Path("data")
        data_dir.mkdir(exist_ok=True, parents=True)

        if "html" in ctype:
            # assert not self.html
            self.folder = pathlib.Path(uri or data_dir).name
            self.raw_html = raw_payload
            self.html = payload
            self.soup = bs4.BeautifulSoup(payload, features="html.parser")
            timestamp = int(time.time() * 1_000_000)
            file_path = pathlib.Path(f"out-{ctype[0]}-{ctype[1]}-{timestamp}.html")
            pathlib.Path(file_path).write_text(str(self.soup))
        else:
            attrs = self.add_file(uri, ctype)
            self.payloads[attrs["name"]] = payload
            logging.debug(f'file_name {attrs["name"]}')

    def __str__(self):
        return str(self.soup) if self.soup else "Extract<None>"  # .prettify()

    def print_text(self):
        print(self.msg.preamble)
        print(self)
        print(self.msg.epilogue)


def main():
    args = sys.argv
    if len(args) != 2:
        print("Usage: ./extract.py <mht file>")
        return
    mht = sys.argv[1]
    log('Extract multi-part of "%s" ...' % mht)
    parsed = Extract(mht)
    folder = parsed.save()
    log(folder)


if __name__ == "__main__":
    main()
