// Real custom components with synthetic HTTP; native auth shell only is substituted by the builder.
import React from 'react'
import { createRoot } from 'react-dom/client'
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from '../../../../locales/en.json'
import th from '../../../../locales/th.json'
import ClassesWorkspace from '../../components/Objects/Classes/ClassesWorkspace'
import SchoolIdentity from '../../components/Objects/Account/subpages/SchoolIdentity'
import LinkGooglePage from '../../app/auth/link/google/page'
import LinkLinePage from '../../app/auth/link/line/page'
import material from '../../components/interior/material.module.css'

const params = new URLSearchParams(location.search)
await i18n.use(initReactI18next).init({ lng: params.get('lang') || 'en', fallbackLng: 'en', resources: { en: { translation: en }, th: { translation: th } } })
const surface = params.get('surface')
createRoot(document.getElementById('root')!).render(<main className={material.scope} style={{maxWidth:1100,margin:'auto',padding:20}}>
 {surface === 'school' ? <SchoolIdentity /> : surface === 'google' ? <LinkGooglePage /> : surface === 'line' ? <LinkLinePage /> : <ClassesWorkspace />}
</main>)
