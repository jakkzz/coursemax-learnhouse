// Run with the pinned web dependencies in a bounded test container.
// Keep real controls and roster components; omit unrelated shell/calendar owners.
const web = process.env.LEARNHOUSE_WEB_SOURCE || '/source'
const dependencies = process.env.LEARNHOUSE_WEB_DEPS || '/app'
const output = process.env.LEARNHOUSE_UI_OUTPUT || '/out'
const result = await Bun.build({
  entrypoints: [web + '/extensions/route66/tests/fixtures/RosterRefresh.tsx'], outdir: output, target: 'browser',
  plugins: [{ name: 'roster-component-fixture', setup(build) {
    build.onResolve({ filter: /.*/ }, args => {
      const p = args.path
      if (['./TeacherTimetable', './calendar/CalendarLibrary', './calendar/ClassSchedule', '../calendar/ClassSchedule'].includes(p)) return { path: 'unrelated', namespace: 'fixture' }
      if (p === 'next/link') return { path: 'link', namespace: 'fixture' }
      if (p === '@/extensions/route66/adapters/ui') return { path: 'ui', namespace: 'fixture' }
      if (p.startsWith('@/')) return { path: Bun.resolveSync(web + '/' + p.slice(2), args.resolveDir) }
      if (p.startsWith('@components/')) return { path: Bun.resolveSync(web + '/components/' + p.slice(12), args.resolveDir) }
      if (!p.startsWith('.') && !p.startsWith('/')) try { return { path: Bun.resolveSync(p, dependencies) } } catch {}
    })
    build.onLoad({ filter: /.*/, namespace: 'fixture' }, args => ({ loader: 'tsx', contents:
      args.path === 'ui' ? `export {Button} from ${JSON.stringify(web + '/extensions/route66/components/interior/Button.tsx')};export {Input} from ${JSON.stringify(web + '/components/ui/input.tsx')};` :
      args.path === 'link' ? `import React from 'react';export default function Link({children,...props}){return <a {...props}>{children}</a>}` :
      'export default function Unrelated(){return null}',
    }))
  } }],
})
if (!result.success) { console.error(result.logs); process.exit(1) }
console.log('Real roster components compiled; unrelated shell/calendar owners substituted')
