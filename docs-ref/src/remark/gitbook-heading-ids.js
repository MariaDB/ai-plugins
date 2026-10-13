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

// Two GitBook rules the preview has to follow, or its build passes pages
// that are broken on mariadb.com/docs:
//
//  1. Heading ids. GitBook slugs headings differently from Docusaurus: it
//     keeps dots and underscores (`### View.find` → `#view.find`, where
//     Docusaurus makes `#viewfind`), numbers duplicates -1, -2 in one
//     namespace with `{% tab %}` titles, and gives h5 and h6 no id at all.
//     Each h2–h4 gets GitBook's id here, so links are checked against the
//     anchors GitBook publishes (`onBrokenAnchors: 'throw'`). Each h5 and h6
//     gets an id no link can match, so a link to one fails here as it fails
//     on GitBook. h1 is the page title, which GitBook doesn't anchor either;
//     it is left alone.
//  2. Descriptions. GitBook cuts the frontmatter `description` at 200
//     characters, mid-word and with no ellipsis, so a longer one fails the
//     build.
//
// The slug rules are a port of `gitbook_slug()` in the mariadb-docs fragment
// checker (`.claude/hooks/fragcheck.py`), which was validated against the ids
// on the published pages. They work on the Markdown source rather than the
// syntax tree, as that checker does, so both compute the same ids.
//
// Docusaurus slugifies an id that a plugin sets in `hProperties`, which would
// drop the dots again, but takes an explicit `{#id}` heading id verbatim. So
// the id is appended as `{#id}` in the syntax tree (never in the source),
// before Docusaurus's own heading plugin runs.
//
// It runs before remarkGitBook, which re-parses the body of every GitBook
// block (`{% hint %}`, `{% tabs %}`, `{% stepper %}`, ...) from a string, so
// a heading inside a block would otherwise carry the line number within the
// block, not within the file. The appended `{#id}` text survives that
// round trip, since the heading is serialised with its children:
//
//   beforeDefaultRemarkPlugins: [remarkGitBookPrepare, remarkGitBookHeadingIds, remarkGitBook, ...]

import { visit } from 'unist-util-visit';

const MAX_DESCRIPTION = 200;
const MAX_SLUG = 100;
const ANCHORED = new Set([2, 3, 4]);

const FENCE = /^\s*(```|~~~)/;
const HEADING = /^(#{1,6})\s+(.*?)\s*$/;
const TAB_TITLE = /\{%\s*tab\s+title="([^"]*)"\s*%\}/g;
const KRAMDOWN_ID = /\s*\{#[A-Za-z0-9._:-]+\}\s*$/;
const FOOTNOTE_REF = /\[\^[^\]]+\]/g;
const CODESPAN = /`+([^`]*)`+/g;

// Characters GitBook spells out. Only the ones confirmed on a rendered page.
const CHARMAP = [
  ['&', ' and '], ['|', ' or '], ['>', ' greater than '],
  ['<', ' less than '], ['$', 'usd'], ['®', '(r)'],
];

function decodeEntities(text) {
  return text
    .replace(/&#x([0-9a-f]+);/gi, (_, hex) => String.fromCodePoint(parseInt(hex, 16)))
    .replace(/&#(\d+);/g, (_, dec) => String.fromCodePoint(Number(dec)))
    .replace(/&(amp|lt|gt|quot|apos|nbsp);/g, (_, name) =>
      ({ amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ' })[name]);
}

// Heading markup reduced to the words GitBook renders.
function stripInline(heading) {
  let text = decodeEntities(heading);
  text = text.replace(KRAMDOWN_ID, '');
  text = text.replace(FOOTNOTE_REF, '');
  text = text.replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1');
  text = text.replace(/\[([^\]]*)\]\([^)]*\)/g, '$1');
  text = text.replace(/<[^>]+>/g, '');
  // Park code spans, so emphasis sees a non-alphanumeric neighbour.
  const parked = [];
  text = text.replace(CODESPAN, (_, code) => `\0${parked.push(code) - 1}\0`);
  text = text.replace(/\*\*([^*]+)\*\*/g, '$1');
  text = text.replace(/\*([^*]+)\*/g, '$1');
  // An underscore closes emphasis only when nothing alphanumeric follows it.
  text = text.replace(/(?<![A-Za-z0-9\\])_([^\\]*?[^_\\])_(?![A-Za-z0-9])/g, '$1');
  text = text.replace(/\\(.)/g, '$1');
  return text.replace(/\0(\d+)\0/g, (_, i) => parked[Number(i)]);
}

export function gitbookSlug(heading) {
  let s = stripInline(heading).toLowerCase();
  for (const [char, spelled] of CHARMAP) s = s.split(char).join(spelled);
  s = s.replace(/['‘’]/g, '');
  s = s.replace(/[^a-z0-9._+]+/g, '-');
  s = s.replace(/\+/g, '');
  s = s.replace(/^-+|-+$/g, '');
  s = s.replace(/^_+/, '').replace(/[._]+$/, '').replace(/^-+|-+$/g, '');
  if (/^[0-9]/.test(s)) s = `id-${s}`;
  return s.slice(0, MAX_SLUG);
}

// Blank out HTML comments, which GitBook doesn't publish.
function uncomment(line, state) {
  let out = '';
  let rest = line;
  while (rest) {
    if (state.inComment) {
      const close = rest.indexOf('-->');
      if (close < 0) return out;
      rest = rest.slice(close + 3);
      state.inComment = false;
    } else {
      const open = rest.indexOf('<!--');
      if (open < 0) return out + rest;
      out += rest.slice(0, open);
      rest = rest.slice(open + 4);
      state.inComment = true;
    }
  }
  return out;
}

// GitBook's id for each heading, keyed by its line number.
function headingIds(source) {
  const ids = new Map();
  const used = new Map();
  const unique = (slug) => {
    const n = used.get(slug) ?? 0;
    used.set(slug, n + 1);
    return n ? `${slug}-${n}` : slug;
  };
  const state = { inComment: false };
  let inFence = false;
  let unanchored = 0;
  source.split(/\r?\n/).forEach((raw, index) => {
    if (FENCE.test(raw)) {
      inFence = !inFence;
      return;
    }
    if (inFence) return;
    const line = uncomment(raw, state);
    const heading = HEADING.exec(line);
    if (heading) {
      const level = heading[1].length;
      if (ANCHORED.has(level)) ids.set(index + 1, unique(gitbookSlug(heading[2])));
      else if (level > 4) ids.set(index + 1, `gitbook-no-anchor-h${level}-${++unanchored}`);
    }
    // A tab title takes an id from the same namespace, in document order.
    for (const tab of line.matchAll(TAB_TITLE)) {
      if (tab[1]) unique(gitbookSlug(tab[1]));
    }
  });
  return ids;
}

export default function remarkGitBookHeadingIds() {
  return (tree, vfile) => {
    const description = vfile.data?.frontMatter?.description;
    if (typeof description === 'string' && description.trim().length > MAX_DESCRIPTION) {
      vfile.fail(
        `description is ${description.trim().length} characters; ` +
          `GitBook cuts it at ${MAX_DESCRIPTION}, mid-word and with no ellipsis`,
      );
    }

    const ids = headingIds(String(vfile.value));
    visit(tree, 'heading', (node) => {
      const id = node.position && ids.get(node.position.start.line);
      if (!id) return;
      node.children.push({ type: 'text', value: ` {#${id}}` });
    });
  };
}
