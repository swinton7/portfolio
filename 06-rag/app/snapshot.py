"""Refresh data/conditions.jsonl from the latest MedlinePlus health topic XML (public domain).

Keeps English topics that describe a condition, as plain text. Run it by hand:
    docker compose run --rm ingest python snapshot.py
"""
import io
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from html.parser import HTMLParser

import yaml

cfg = yaml.safe_load(open("/config.yaml"))["snapshot"]


class TextOnly(HTMLParser):
    """Turn the summary's HTML into plain paragraphs and list lines."""

    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("p", "ul", "ol"):
            self.parts.append("\n\n")
        elif tag == "li":
            self.parts.append("\n- ")

    def handle_data(self, data):
        self.parts.append(data)

    def text(self):
        lines = (re.sub(r"[ \t]+", " ", line).strip() for line in "".join(self.parts).splitlines())
        return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def to_text(html):
    parser = TextOnly()
    parser.feed(html)
    return parser.text()


def is_condition(groups):
    if any(g in cfg["drop_if_any_group"] for g in groups):
        return False
    return any(g not in cfg["non_condition_groups"] for g in groups)


index = urllib.request.urlopen(cfg["index_url"]).read().decode()
zip_url = re.search(r'href="(https://medlineplus\.gov/xml/mplus_topics_compressed_[\d-]+\.zip)"', index).group(1)
archive = zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(zip_url).read()))
root = ET.fromstring(archive.read(archive.namelist()[0]))

kept = 0
with open(cfg["path"], "w") as out:
    for topic in root.findall("health-topic"):
        groups = [g.text for g in topic.findall("group")]
        if topic.get("language") != "English" or not is_condition(groups):
            continue
        out.write(json.dumps({
            "id": topic.get("id"),
            "title": topic.get("title"),
            "url": topic.get("url"),
            "also_called": [a.text for a in topic.findall("also-called")],
            "groups": groups,
            "summary": to_text(topic.findtext("full-summary") or ""),
        }) + "\n")
        kept += 1

print(f"{zip_url} (generated {root.get('date-generated')}): kept {kept} condition topics -> {cfg['path']}")
