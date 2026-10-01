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

// GitBook features that docusaurus-plugin-gitbook does not cover, so the
// preview renders content/ the way mariadb.com/docs does:
//
//  1. `{% content-ref url="…" %}` blocks. The plugin has no transformer for
//     them and silently drops unknown blocks inside other blocks. We register
//     one with the plugin's own registry, then render it as a link card whose
//     label is the target page's title, as GitBook does.
//  2. The frontmatter `description`, shown by GitBook as a lead paragraph
//     under the page title.
//  3. Directory links (`[x](some-dir/)`), which GitBook resolves to the
//     directory's README.md and Docusaurus does not.
//
// The plugin's tokenizer only accepts `\w+` tag names, so `content-ref` is
// never recognized as a block. `remarkGitBookPrepare` renames it to
// `contentref` before remarkGitBook runs; `remarkGitBookExtras` must run after
// it and before Docusaurus resolves `.md` links:
//
//   beforeDefaultRemarkPlugins: [remarkGitBookPrepare, remarkGitBook, remarkGitBookExtras]

import fs from 'node:fs';
import path from 'node:path';
import { visit } from 'unist-util-visit';
import {
  registerTransformer,
  getTransformer,
  getRegisteredBlocks,
  createMdxJsxElement,
} from 'docusaurus-plugin-gitbook/lib/remark/index.js';

const CONTENT_REF_CLASS = 'gb-content-ref';

registerTransformer('contentref', (block, transformContent) => {
  const url = block.attributes.url || block.attributes._positional || '';
  return [
    createMdxJsxElement('div', { className: CONTENT_REF_CLASS, 'data-url': url }, transformContent(block.content)),
  ];
});

// The plugin's parser gives a block that contains other blocks only the text
// *between* them as `content`, and transformers such as `columns` read nothing
// else, so `{% column %}{% content-ref %}…{% endcolumn %}` renders empty. Hand
// every such block its full inner source instead; transformContent parses the
// nested blocks itself.
function innerSource(block) {
  const open = block.raw.indexOf('%}');
  const close = block.raw.lastIndexOf('{%');
  return open === -1 || close <= open ? block.content : block.raw.slice(open + 2, close).replace(/^\r?\n|\r?\n$/g, '');
}

function withNestedContent(block) {
  if (!block.children?.length) return block;
  return { ...block, content: innerSource(block), children: block.children.map(withNestedContent) };
}

for (const name of getRegisteredBlocks()) {
  const transformer = getTransformer(name);
  registerTransformer(name, (block, transformContent) => transformer(withNestedContent(block), transformContent));
}

const CONTENT_REF_TAG =/\{%(\s*)(end)?content-ref\b/g;

export function remarkGitBookPrepare() {
  return (tree) => {
    visit(tree, 'text', (node) => {
      if (node.value.includes('content-ref')) node.value = node.value.replace(CONTENT_REF_TAG, '{%$1$2contentref');
    });
  };
}

function isRelative(url) {
  return url && !/^([a-z][a-z0-9+.-]*:|\/|#)/i.test(url);
}

// Resolve a GitBook link target to a file on disk, or null.
function resolveTarget(fromFile, url) {
  const [pathPart] = url.split('#');
  let target = path.resolve(path.dirname(fromFile), decodeURI(pathPart));
  if (pathPart.endsWith('/') || (fs.existsSync(target) && fs.statSync(target).isDirectory())) {
    target = path.join(target, 'README.md');
  }
  return fs.existsSync(target) ? target : null;
}

function readPageMeta(file) {
  const text = fs.readFileSync(file, 'utf8');
  const fm = text.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  const body = fm ? text.slice(fm[0].length) : text;
  const h1 = body.match(/^#\s+(.+?)\s*#*\s*$/m);
  const icon = fm && fm[1].match(/^icon:\s*(\S+)\s*$/m);
  return {
    title: h1 ? h1[1].replace(/\\(.)/g, '$1') : path.basename(file, '.md'),
    icon: icon ? icon[1] : null,
  };
}

function textNode(value) {
  return { type: 'text', value };
}

function inlineElement(name, attributes, children = []) {
  return {
    type: 'mdxJsxTextElement',
    name,
    attributes: Object.entries(attributes).map(([key, value]) => ({ type: 'mdxJsxAttribute', name: key, value })),
    children,
  };
}

function findLink(node) {
  let found = null;
  visit(node, 'link', (link) => {
    found ??= link;
  });
  return found;
}

function hasClass(node, className) {
  return node.attributes?.some((a) => a.name === 'className' && String(a.value).split(/\s+/).includes(className));
}

export default function remarkGitBookExtras() {
  return (tree, vfile) => {
    const file = vfile.path;

    // 3. Directory links → README.md, so Docusaurus can resolve them.
    visit(tree, 'link', (link) => {
      if (!isRelative(link.url)) return;
      const [pathPart, hash] = link.url.split('#');
      if (!pathPart.endsWith('/')) return;
      const target = resolveTarget(file, pathPart);
      if (target) link.url = `${pathPart}README.md${hash ? `#${hash}` : ''}`;
    });

    // 1. content-ref cards.
    visit(tree, 'mdxJsxFlowElement', (node) => {
      if (!hasClass(node, CONTENT_REF_CLASS)) return;
      const urlAttr = node.attributes.find((a) => a.name === 'data-url');
      const link = findLink(node);
      const url = link?.url || urlAttr?.value;
      if (!url) return;

      let title = link ? link.children.map((c) => c.value ?? '').join('') : url;
      let icon = null;
      if (isRelative(url)) {
        const target = resolveTarget(file, url);
        if (target) ({ title, icon } = readPageMeta(target));
        else vfile.message(`content-ref target not found: ${url}`);
      }

      const label = [];
      if (icon) label.push(inlineElement('i', { className: `gb-content-ref__icon fa-solid fa-${icon}`, 'aria-hidden': 'true' }));
      label.push(inlineElement('span', { className: 'gb-content-ref__title' }, [textNode(title)]));
      node.children = [
        {
          type: 'paragraph',
          children: [{ type: 'link', url, title: null, children: label }],
        },
      ];
    });

    // 2. Frontmatter description as the lead paragraph under the H1.
    const description = vfile.data?.frontMatter?.description;
    if (typeof description === 'string' && description.trim()) {
      const h1 = tree.children.findIndex((n) => n.type === 'heading' && n.depth === 1);
      if (h1 !== -1) {
        tree.children.splice(
          h1 + 1,
          0,
          createMdxJsxElement('p', { className: 'gb-page-description' }, [textNode(description.trim())]),
        );
      }
    }
  };
}
