// Synthetic component contracts; no native login or live school traffic.
import React from 'react'
import { createRoot } from 'react-dom/client'
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import ClassesWorkspace from '../../components/Objects/Classes/ClassesWorkspace'
import SchoolIdentity from '../../components/Objects/Account/subpages/SchoolIdentity'
import material from '../../components/interior/material.module.css'

const params = new URLSearchParams(location.search)
const language = params.get('lang') || localStorage.getItem('fixture-language') || 'en'
localStorage.setItem('fixture-language', language)
await i18n.use(initReactI18next).init({ lng: language, fallbackLng: 'en', resources: {} })
createRoot(document.getElementById('root')!).render(<main className={material.scope} style={{maxWidth:1100,margin:'auto',padding:20}}>
 {params.get('role') === 'student' ? <SchoolIdentity /> : <ClassesWorkspace />}
</main>)
