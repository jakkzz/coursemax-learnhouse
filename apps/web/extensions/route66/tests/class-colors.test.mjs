import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const dir = new URL('../components/Objects/Classes/', import.meta.url)
const css = fs.readFileSync(new URL('class-colors.module.css', dir), 'utf8')
const linear = hex => hex.match(/[a-f\d]{2}/gi).map(x => {
  const n = parseInt(x, 16) / 255
  return n <= .04045 ? n / 12.92 : ((n + .055) / 1.055) ** 2.4
})
const vision = {
  ordinary: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
  protanopia: [[.152286, 1.052583, -.204868], [.114503, .786281, .099216], [-.003882, -.048116, 1.051998]],
  deuteranopia: [[.367322, .860646, -.227968], [.280085, .672501, .047413], [-.01182, .04294, .968881]],
  tritanopia: [[1.255528, -.076749, -.178779], [-.078411, .930809, .147602], [.004733, .691367, .3039]],
}
const luminance = (hex, matrix) => {
  const rgb = linear(hex)
  const transformed = matrix.map(row => Math.max(0, Math.min(1, row.reduce((sum, v, i) => sum + v * rgb[i], 0))))
  return transformed.reduce((sum, n, i) => sum + n * [.2126, .7152, .0722][i], 0)
}

test('class colors reuse scoped native control roles, not global theme changes', () => {
  assert.match(css, /\.workspace\s*\{[^}]*--color-primary: #1d4ed8;/)
  assert.doesNotMatch(css, /:root|!important|linear-gradient|border-(left|right)/)
  for (const name of ['ClassConnections.tsx', 'ClassesWorkspace.tsx', 'real-teaching/RealTeachingWorkspace.tsx']) {
    assert.match(fs.readFileSync(new URL(name, dir), 'utf8'), /class-colors\.module\.css/)
  }
  assert.match(css, /prefers-reduced-motion/)
  assert.match(css, /forced-colors/)
})

test('action and semantic text retain AA contrast, including simulated color-vision deficiencies', () => {
  const pairs = [['#ffffff', '#1d4ed8'], ['#1e40af', '#eff6ff'], ['#166534', '#f0fdf4'], ['#92400e', '#fffbeb'], ['#991b1b', '#fef2f2'], ['#525252', '#f5f5f5']]
  for (const [foreground, background] of pairs) {
    assert(css.includes(foreground) && css.includes(background))
    for (const [name, matrix] of Object.entries(vision)) {
      const a = luminance(foreground, matrix), b = luminance(background, matrix)
      assert((Math.max(a, b) + .05) / (Math.min(a, b) + .05) >= 4.5, `${name}: ${foreground}/${background}`)
    }
  }
})

test('roster colors distinguish membership, account matching and the selected member', () => {
  const source = fs.readFileSync(new URL('ClassesWorkspace.tsx', dir), 'utf8')
  assert.match(css, /\.rosterRow:nth-of-type\(even\)/)
  assert.match(css, /\.rosterRow\[data-selected='true'\][^{]*\{[^}]*border-color: #1d4ed8/)
  assert.match(css, /@container \(min-width: 700px\)/)
  assert.match(source, /data-state=\{p\.status\}/)
  assert.match(source, /data-state=\{p\.account_status\}/)
  assert.match(source, /data-selected=\{person\?\.id===p\.id\}/)
  assert.match(source, /aria-expanded=\{person\?\.id===p\.id\}/)
  assert.match(source, /id="roster-member-editor"/)
  assert.match(source, /<UserMinus/)
})

test('status color is accompanied by existing labels, icons and a non-color selection cue', () => {
  const connections = fs.readFileSync(new URL('ClassConnections.tsx', dir), 'utf8')
  assert.match(connections, /data-state=\{data\?\.status/)
  assert.match(connections, /<StatusIcon[^>]*aria-hidden="true"[^>]*\/>{heading}/)
  const tabs = fs.readFileSync(new URL('../../interior/material.module.css', dir), 'utf8')
  assert.match(tabs, /\[aria-checked=true\][^}]*font-weight: 600; box-shadow:/)
  assert.match(tabs, /\[aria-checked=true\][^}]*outline: 2px solid Highlight/)
})
