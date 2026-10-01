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

// Wraps the classic navbar with the second header row of mariadb.com/docs:
// the space tabs (Home, Server, …, Enterprise Tools, …). The tab list comes
// from `customFields.spaceTabs` in docusaurus.config.js.

import React from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import OriginalNavbar from '@theme-original/Navbar';

function SpaceTabs({ tabs }) {
  return (
    <nav className="space-tabs" aria-label="Documentation spaces">
      <ul className="space-tabs__list">
        {tabs.map((tab) => (
          <li key={tab.label}>
            <Link
              className={clsx('space-tabs__tab', tab.active && 'space-tabs__tab--active')}
              aria-current={tab.active ? 'page' : undefined}
              {...(tab.to ? { to: tab.to } : { href: tab.href, target: '_self', rel: undefined })}
            >
              {tab.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

export default function Navbar(props) {
  const { siteConfig } = useDocusaurusContext();
  const tabs = siteConfig.customFields?.spaceTabs ?? [];
  return (
    <div className="site-header">
      <OriginalNavbar {...props} />
      {tabs.length > 0 && <SpaceTabs tabs={tabs} />}
    </div>
  );
}
