// Copyright (c) 2026, MariaDB plc.
//
// This program is free software; you can redistribute it and/or modify
// it under the terms of the GNU General Public License, version 2.0,
// as published by the Free Software Foundation.
//
// This program is distributed in the hope that it will be useful, but
// WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See
// the GNU General Public License, version 2.0, for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program; if not, write to the Free Software Foundation, Inc.,
// 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA

// Builds the Docusaurus sidebar from content/SUMMARY.md, so that GitBook's own
// navigation file stays the single source of truth for the page tree.
//
// SUMMARY.md format (GitBook): `* [Title](path/to/page.md)`, two spaces of
// indent per level. Headings (`## Part`) start a new group. An entry with
// children becomes a category whose own page is the entry's target.

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const summaryPath = path.join(here, 'content', 'SUMMARY.md');

const ENTRY = /^(\s*)[*-] \[(.+?)\]\((.+?)\)\s*$/;
const PART = /^##\s+(.+?)\s*$/;

// A GitBook path to the Docusaurus doc id: drop `.md`, keep `README`.
function docId(target) {
  let p = decodeURI(target).replace(/^\.\//, '');
  if (p.endsWith('/')) p += 'README.md';
  return p.replace(/\.md$/, '');
}

// GitBook escapes Markdown characters in titles (`mariadb\_rpl\_init()`).
function unescape(title) {
  return title.replace(/\\([\\`*_{}[\]()#+\-.!])/g, '$1');
}

function parseSummary(text) {
  const root = [];
  const stack = [{ depth: -1, items: root }];

  for (const line of text.split(/\r?\n/)) {
    const part = line.match(PART);
    if (part) {
      root.push({ type: 'html', value: unescape(part[1]), className: 'sidebar-part' });
      stack.length = 1;
      continue;
    }
    const m = line.match(ENTRY);
    if (!m) continue;
    const depth = Math.floor(m[1].replace(/\t/g, '  ').length / 2);
    const node = { label: unescape(m[2]), id: docId(m[3]), items: [] };
    while (stack.at(-1).depth >= depth) stack.pop();
    stack.at(-1).items.push(node);
    stack.push({ depth, items: node.items });
  }
  return root;
}

function toSidebarItem(node) {
  if (node.type === 'html') return { ...node, defaultStyle: true };
  if (node.items.length === 0) {
    return { type: 'doc', id: node.id, label: node.label };
  }
  return {
    type: 'category',
    label: node.label,
    link: { type: 'doc', id: node.id },
    collapsible: true,
    collapsed: true,
    items: node.items.map(toSidebarItem),
  };
}

const tree = parseSummary(fs.readFileSync(summaryPath, 'utf8'));

export default {
  reference: tree.map(toSidebarItem),
};
