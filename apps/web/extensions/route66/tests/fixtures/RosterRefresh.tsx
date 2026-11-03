// Synthetic rendered contracts. No native login or real registrar traffic.
import React from 'react'
import { createRoot } from 'react-dom/client'
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import ClassesWorkspace from '../../components/Objects/Classes/ClassesWorkspace'
import OfficialRoster from '../../components/Objects/Classes/real-teaching/OfficialRoster'
import material from '../../components/interior/material.module.css'

const params = new URLSearchParams(location.search), th = params.get('lang') === 'th'
await i18n.use(initReactI18next).init({ lng: th ? 'th' : 'en', fallbackLng: 'en', resources: {} })
const context = { academic_year: 2569, semester: 1, fetched_at: '2026-11-03T10:00:00Z',
  classRow: { registry_course_id: '100', course_code: '990001', title: 'Synthetic roster class', section: 'P1', meetings: [] } }
createRoot(document.getElementById('root')!).render(<main className={material.scope} style={{ maxWidth: 1100, margin: 'auto', padding: 20 }}>
  {params.get('official') ? <OfficialRoster context={context} th={th} onOpenSaved={() => { document.getElementById('saved-handoff')!.textContent = 'opened' }} /> : <ClassesWorkspace />}
  <output id="saved-handoff" />
</main>)
