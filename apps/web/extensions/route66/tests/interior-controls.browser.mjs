// Run with NODE_PATH=<web deps>, PLAYWRIGHT_MODULE_PATH=<playwright>, LEARNHOUSE_NATIVE_WEB=<built web>.
// No live accounts, provider traffic, academic writes or OS clipboard access.
import assert from 'node:assert/strict'
import fs from 'node:fs'
import http from 'node:http'
import os from 'node:os'
import path from 'node:path'
import { createRequire } from 'node:module'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
const here=path.dirname(fileURLToPath(import.meta.url)),web=path.resolve(here,'../../..'),deps=process.env.NODE_PATH,native=process.env.LEARNHOUSE_NATIVE_WEB
assert(deps&&native,'Provide reviewed dependencies and a compiled native web directory')
const evidence=process.env.LEARNHOUSE_UI_EVIDENCE||fs.mkdtempSync(path.join(os.tmpdir(),'lh-interior-'));fs.mkdirSync(evidence,{recursive:true,mode:0o700})
const require=createRequire(import.meta.url),{chromium}=require(process.env.PLAYWRIGHT_MODULE_PATH||'playwright')
const build=`const web=${JSON.stringify(web)},deps=${JSON.stringify(deps)};const result=await Bun.build({entrypoints:[${JSON.stringify(here+'/fixtures/InteriorControls.tsx')}],outdir:${JSON.stringify(evidence+'/public')},target:'browser',plugins:[{name:'reviewed-local-deps',setup(b){b.onResolve({filter:/.*/},a=>{const p=a.path;if(p.startsWith('@/'))return {path:Bun.resolveSync(web+'/'+p.slice(2),a.resolveDir)};if(p.startsWith('@components/'))return {path:Bun.resolveSync(web+'/components/'+p.slice(12),a.resolveDir)};if(!p.startsWith('.')&&!p.startsWith('/'))try{return {path:Bun.resolveSync(p,deps+'/../')}}catch{}})}}]});if(!result.success){console.error(result.logs);process.exit(1)}`
fs.writeFileSync(evidence+'/build.ts',build,{mode:0o600});execFileSync(process.env.BUN_BIN||'bun',[evidence+'/build.ts'],{stdio:'inherit'})
const chunks=path.join(native,'.next/static/chunks'),css=fs.readdirSync(chunks).filter(n=>n.endsWith('.css')).map(n=>fs.readFileSync(path.join(chunks,n))).join('\n')
const server=http.createServer((req,res)=>{
 const p=new URL(req.url,'http://fixture').pathname
 if(p==='/native.css'){res.setHeader('Content-Type','text/css');return res.end(css)}
 if(p==='/fixture.js'||p==='/fixture.css'){res.setHeader('Content-Type',p.endsWith('.css')?'text/css':'text/javascript');return res.end(fs.readFileSync(evidence+'/public/InteriorControls'+(p.endsWith('.css')?'.css':'.js')))}
 if(p.startsWith('/_next/static/')){const f=path.resolve(native,'.next/static',p.slice('/_next/static/'.length));if(f.startsWith(path.resolve(native,'.next/static')+'/')&&fs.existsSync(f))return res.end(fs.readFileSync(f));res.statusCode=404;return res.end()}
 res.setHeader('Content-Type','text/html');res.end('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/native.css"><link rel="stylesheet" href="/fixture.css"></head><body style="margin:0;background:#fafafa;font-family:system-ui"><div id="root"></div><script type="module" src="/fixture.js"></script></body></html>')
})
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']}),results=[]
try{
 for(const [lang,width] of [['en',1440],['th',390]]){
  const context=await browser.newContext({viewport:{width,height:950}}),page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message))
  await page.addInitScript(()=>{window.copyWrites=[];Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async text=>{window.copyWrites.push(text)}}})})
  await page.goto('http://127.0.0.1:'+server.address().port+'/?lang='+lang)
  const radios=page.getByRole('radiogroup',{name:'Fixture views'}),details=radios.getByRole('radio').first(),roster=radios.getByRole('radio').last()
  await details.focus();await page.keyboard.press('ArrowRight');assert.equal(await roster.getAttribute('aria-checked'),'true');assert.equal(await page.getByTestId('view').innerText(),'roster')
  await page.keyboard.press('ArrowRight');assert.equal(await details.getAttribute('aria-checked'),'true');await page.keyboard.press('End');assert.equal(await roster.getAttribute('aria-checked'),'true');await page.keyboard.press('Home');assert.equal(await details.getAttribute('aria-checked'),'true')
  assert.equal(await page.getByTestId('inherited-disabled').isDisabled(),true);assert.equal(await page.getByRole('radiogroup',{name:'Disabled choices'}).getByRole('radio').first().isDisabled(),true)
  await page.getByLabel('Draft name').fill('Unsaved local draft');const save=page.getByTestId('save'),before=await save.boundingBox();await save.click();assert.equal(await save.isDisabled(),true);assert.equal(await save.getAttribute('aria-busy'),'true');assert.equal(await page.getByTestId('saved').innerText(),'0');assert.deepEqual(await save.boundingBox(),before)
  await page.waitForFunction(()=>document.querySelector('[data-testid=saved]').textContent==='1');assert.deepEqual(await save.boundingBox(),before);assert.equal(await page.getByLabel('Draft name').inputValue(),'Unsaved local draft')
  await page.getByRole('button',{name:'Focus save',exact:true}).click();assert.equal(await save.evaluate(el=>el===document.activeElement),true)
  const box=await save.boundingBox();await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();await page.mouse.move(1,1);await page.mouse.up();assert.equal(await page.getByTestId('saved').innerText(),'1','Pointer cancellation must not submit')
  await page.getByRole('link',{name:'Link action'}).click();assert(page.url().endsWith('#destination'))
  const copy=page.getByTestId('copy'),copyBefore=await copy.boundingBox();await copy.click();await page.waitForFunction(()=>document.querySelector('[data-testid=copies]').textContent==='1');assert.deepEqual(await copy.boundingBox(),copyBefore);assert.equal(await page.evaluate(()=>window.copyWrites.length),1)
  await page.evaluate(()=>{Object.defineProperty(navigator,'clipboard',{configurable:true,value:undefined});document.execCommand=()=>{window.fallbackValue=document.querySelector('textarea').value;return true}})
  await copy.focus();await page.keyboard.press('Enter');await page.waitForFunction(()=>document.querySelector('[data-testid=copies]').textContent==='2');assert.equal(await copy.evaluate(el=>el===document.activeElement),true);assert.equal(await page.locator('textarea').count(),0);assert((await page.evaluate(()=>window.fallbackValue)).startsWith('https://fixture.invalid/attendance/check-in?handoff='))
  await page.evaluate(()=>{Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async()=>{throw Error('Synthetic denial')}}});document.execCommand=()=>false})
  await copy.click();await copy.locator('[data-active=true]').filter({hasText:lang==='th'?'คัดลอกไม่ได้':'Copy failed'}).waitFor();assert.equal(await page.getByTestId('copies').innerText(),'2');assert.deepEqual(await copy.boundingBox(),copyBefore)
  await page.evaluate(()=>Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:()=>new Promise(resolve=>{window.resolveCopy=resolve})}}));await copy.click();await page.getByRole('button',{name:'Toggle copy',exact:true}).click();await page.evaluate(()=>window.resolveCopy());assert.equal(await page.getByTestId('copy').count(),0);assert.equal(await page.getByTestId('copies').innerText(),'2','Unmounted clipboard completion must not call the parent')
  await page.getByRole('button',{name:'Toggle copy',exact:true}).click();await page.evaluate(()=>{window.lateFallbacks=0;document.execCommand=()=>{window.lateFallbacks++;return true};Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:()=>new Promise((resolve,reject)=>{window.rejectCopy=reject})}})});await copy.click();await page.getByRole('button',{name:'Toggle copy',exact:true}).click();await page.evaluate(async()=>{window.rejectCopy(Error('Synthetic late denial'));await Promise.resolve();await Promise.resolve()});assert.equal(await page.evaluate(()=>window.lateFallbacks),0,'A removed control must not start a late clipboard fallback')
  await page.emulateMedia({reducedMotion:'reduce',forcedColors:'active'});await save.click();assert.equal(await save.locator('svg').evaluate(el=>getComputedStyle(el).animationName),'none');assert.equal(await save.evaluate(el=>getComputedStyle(el).transform),'none');assert.equal(await details.evaluate(el=>getComputedStyle(el).outlineStyle),'solid');await page.waitForFunction(()=>document.querySelector('[data-testid=saved]').textContent==='2')
  await page.emulateMedia({forcedColors:'none'});await page.getByRole('button',{name:'Toggle copy',exact:true}).click()
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);assert.deepEqual(errors,[])
  await page.screenshot({path:evidence+'/controls-'+lang+'-'+width+'.png',fullPage:true})
  results.push({lang,width,keyboard_and_disabled_choices:true,unsaved_input_preserved:true,one_native_submit_per_action:true,stable_loading_and_copy_geometry:true,clipboard_success_fallback_failure_unmount:true,forwarded_ref_and_native_link:true,pointer_cancellation:true,reduced_motion_and_forced_colors:true,overflow:false,page_errors:errors});await context.close()
 }
 fs.writeFileSync(evidence+'/controls-results.json',JSON.stringify(results,null,2),{mode:0o600});console.log(JSON.stringify(results,null,2))
}finally{await browser.close();await new Promise(resolve=>server.close(resolve))}
