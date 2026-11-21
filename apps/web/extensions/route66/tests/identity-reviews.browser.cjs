// Real components with synthetic HTTP. PostgreSQL/native access is tested separately.
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE_PATH||'playwright');
const expect=require((process.env.PLAYWRIGHT_MODULE_PATH||'playwright')+'/test').expect.configure({timeout:10000});
const evidence=process.env.LEARNHOUSE_UI_EVIDENCE,native=process.env.LEARNHOUSE_NATIVE_WEB;
assert(evidence&&native);
const css=fs.readdirSync(native+'/.next/static/chunks').filter(n=>n.endsWith('.css')).map(n=>fs.readFileSync(native+'/.next/static/chunks/'+n)).join('\n');
const server=http.createServer((req,res)=>{
 const p=new URL(req.url,'http://fixture').pathname;
 if(p==='/native.css'){res.setHeader('Content-Type','text/css');return res.end(css)}
 if(p==='/fixture.js'||p==='/fixture.css'){res.setHeader('Content-Type',p.endsWith('.css')?'text/css':'text/javascript');return res.end(p.endsWith('.css')?fs.readdirSync(evidence+'/ui-public').filter(n=>n.endsWith('.css')).map(n=>fs.readFileSync(evidence+'/ui-public/'+n)).join('\n'):fs.readFileSync(evidence+'/ui-public/IdentityReviews.js'))}
 if(p.startsWith('/_next/static/')){const f=path.resolve(native,'.next/static',p.slice('/_next/static/'.length));if(f.startsWith(path.resolve(native,'.next/static')+'/')&&fs.existsSync(f))return res.end(fs.readFileSync(f));res.statusCode=404;return res.end()}
 res.setHeader('Content-Type','text/html');res.end('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/native.css"><link rel="stylesheet" href="/fixture.css"></head><body style="margin:0;background:#fafafa;font-family:system-ui"><div id="root"></div><script type="module" src="/fixture.js"></script></body></html>');
});
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_BIN,args:['--disable-dev-shm-usage']});
 const results=[];
 try{
 for(const lang of ['en','th'])for(const width of [1440,390])for(const role of ['teacher','admin','student']){
  const th=lang==='th',t=(en,thai)=>th?thai:en,name=`review-${role}-${lang}-${width}`;
  const context=await browser.newContext({viewport:{width,height:950},timezoneId:'Asia/Bangkok',reducedMotion:'reduce'}),page=await context.newPage(),errors=[],posts=[];
  page.on('pageerror',e=>errors.push(e.message));
  let matched=false,failDecision=true,cases=role==='admin'?[item(1),{...item(2),student_name:'Separate manual record',can_match:false,match_state:'ownership_conflict'}]:[];
  function item(id){return {id,created_at:'2026-11-04T03:00:00Z',status:'open',outcome:null,reason:'Synthetic reported discrepancy',student_number:'6900000001',student_name:'Synthetic student นักศึกษาตัวอย่าง',match_state:'ready_to_match',decided_at:null,can_match:true,expected_token:'a'.repeat(64),class_name:'Synthetic class',section:'P1',accounts:[{name:'Synthetic account',owns_record:false,has_verified_claim:true}]}}
  function receipt(c){const {accounts,student_name,expected_token,decision_reason,...rest}=c;return rest}
  const cls=()=>({id:20,course_id:10,course_uuid:'course_fixture_10',course_name:'Synthetic class',course_available:matched,academic_year:2569,semester:1,section:'P1',manageable:role!=='student',version:1,active_count:1,last_synced_at:'2026-11-04T02:00:00Z',registry_course_id:'100',registry_class_id:'200'});
  await page.route('**/api/v1/**',async route=>{
   const req=route.request(),url=new URL(req.url()),p=url.pathname.replace('/api/v1/academic-classes',''),method=req.method();let result={};
   if(method==='POST')posts.push({path:p,body:req.postDataJSON()});
   if(url.pathname==='/api/v1/school-identity/me')result={eligible:false,search_hint:null,needs_google_signin:false,school_kind:'student',student_number_hint:'6900000001',directory_identity:null,courses:matched?[cls()]:[],student_match_status:matched?'matched':'conflict',student_profile:matched?{student_number:'6900000001',full_name_th:'Synthetic student นักศึกษาตัวอย่าง',faculty:'Synthetic faculty',program:'Synthetic program'}:null};
   else if(p==='')result={classes:role==='student'&&!matched?[]:[cls()],can_create:role!=='student',student_match_status:role==='student'&&!matched?'conflict':'matched'};
   else if(p==='/courses')result={courses:[{id:10,name:'Synthetic class',private:true,registry_course_id:'100',course_code:'990001'}],teachers:[],can_assign_teachers:role==='admin',teaching_assignments:[]};
   else if(p==='/connections/requests')result={requests:[],can_connect:false};
   else if(p==='/20/roster')result={class_id:20,version:1,students:[{id:1,student_number:'6900000001',full_name_th:'Synthetic student นักศึกษาตัวอย่าง',faculty:'Synthetic faculty',program:'Synthetic program',source:'registry',status:'active',account_status:'unlinked',missing_count:0}],events:[]};
   else if(p==='/20/roster/refresh')result={class_id:20,class_version:1,control_version:0,paused:false,initial_review_required:false,status:'ready',last_attempt_at:null,last_accepted_at:'2026-11-04T02:00:00Z',next_check_at:'2026-11-04T08:00:00Z',delayed:false,recent:[]};
   else if(p.endsWith('/learning-access/status'))result={status:'ready',can_configure:false};
   else if(p==='/20/roster/1/flag'){if(!cases.length)cases.push({...item(1),reason:req.postDataJSON().reason});result={flagged:true,identity_changed:false,case_id:1};}
   else if(p==='/20/identity-reviews')result={cases:cases.map(c=>({...receipt(c),student_name:c.student_name}))};
   else if(p==='/identity-reviews/own'){
    if(method==='POST'){assert.deepEqual(Object.keys(req.postDataJSON()),['reason']);if(!cases.length)cases.push({...item(1),reason:req.postDataJSON().reason});result=receipt(cases[0]);}
    else result={can_request:true,open_case_id:cases.find(c=>c.status==='open')?.id||null,cases:cases.map(receipt)};
   }else if(p==='/identity-reviews')result={cases:cases.filter(c=>c.status===(url.searchParams.get('status')||'open'))};
   else if(/^\/identity-reviews\/\d+$/.test(p))result=cases.find(c=>c.id===Number(p.split('/').pop()));
   else if(p.endsWith('/decision')){
    const c=cases.find(c=>c.id===Number(p.split('/')[2])),body=req.postDataJSON();
    if(failDecision){failDecision=false;c.expected_token='b'.repeat(64);return route.fulfill({status:409,json:{detail:'Synthetic stale evidence'}})}
    assert.equal(body.expected_token,c.expected_token);
    if(body.action==='recheck')assert.equal(c.can_match,true);
    c.status='closed';c.outcome=body.action==='recheck'?'matched':'unchanged';c.decision_reason=body.reason;c.decided_at='2026-11-04T03:01:00Z';result=c;
   }else return route.fulfill({status:404,json:{detail:'Unhandled synthetic endpoint '+p}});
   await route.fulfill({json:result});
  });
  await page.goto(`http://127.0.0.1:${server.address().port}/?role=${role}&lang=${lang}`);
  try{
   if(role==='teacher'){
    await page.getByRole('tab',{name:t('LearnHouse classes','ชั้นเรียน LearnHouse'),exact:true}).click();
    await page.getByRole('button',{name:t('Manage roster','จัดการรายชื่อ'),exact:true}).click();
    await page.getByRole('button',{name:t('Member actions','จัดการสมาชิก'),exact:true}).click();
    await page.getByLabel(t('Reason','เหตุผล'),{exact:true}).fill('Please verify the missing account match');
    await page.getByRole('button',{name:t('Flag identity for review','แจ้งให้ตรวจสอบตัวตน'),exact:true}).click();
    const summary=page.locator('summary').filter({hasText:t('Identity review requests','คำขอตรวจสอบตัวตน')});await expect(summary).toContainText('(1)');await summary.click();
    await expect(page.getByText(t('Waiting for administrator review','รอผู้ดูแลตรวจสอบ'),{exact:false})).toBeVisible();
    assert.equal(posts.filter(p=>p.path.endsWith('/flag')).length,1);assert.equal(await page.getByRole('tab',{name:t('Identity reviews','ตรวจสอบตัวตน'),exact:true}).count(),0);
   }else if(role==='admin'){
    await page.getByRole('tab',{name:t('Identity reviews','ตรวจสอบตัวตน'),exact:true}).click();
    await page.getByRole('button',{name:t('Review request','ตรวจสอบคำขอ'),exact:true}).first().click();
    const note=page.getByLabel(t('Decision reason (administrator record)','เหตุผลการตัดสินใจ (บันทึกสำหรับผู้ดูแล)'),{exact:true});await note.fill('Keep this note across a stale review');
    const confirm=page.getByRole('button',{name:t('Confirm verified match','ยืนยันการจับคู่จากหลักฐาน'),exact:true});await confirm.click();
    await expect(page.getByRole('alert')).toContainText(t('The evidence or decision changed','หลักฐานหรือผลการตัดสินใจเปลี่ยนแล้ว'));
    assert.equal(await note.inputValue(),'Keep this note across a stale review');await expect(confirm).toBeDisabled();
    await page.getByRole('alert').getByRole('button',{name:t('Refresh','โหลดใหม่'),exact:true}).click();
    await expect(note).toHaveValue('Keep this note across a stale review');await expect(confirm).toBeEnabled();await confirm.click();
    await expect(page.getByText(t('Decision saved','บันทึกผลการตรวจสอบแล้ว'),{exact:true})).toBeVisible();
    await page.getByRole('button',{name:t('All review requests','คำขอตรวจสอบทั้งหมด'),exact:true}).click();
    await page.getByRole('button',{name:t('Review request','ตรวจสอบคำขอ'),exact:true}).click();
    await note.fill('Keep the existing records and work separate');await expect(confirm).toBeDisabled();
    await page.getByRole('button',{name:t('Close without changing identity','ปิดคำขอโดยไม่เปลี่ยนตัวตน'),exact:true}).click();
    await expect(page.getByText(t('Closed — identity unchanged','ปิดคำขอแล้ว — ไม่เปลี่ยนตัวตน'),{exact:true})).toBeVisible();
    assert.deepEqual(cases.map(c=>c.outcome),['matched','unchanged']);
   }else{
    const reason=page.getByLabel(t('Reason for review','เหตุผลที่ขอตรวจสอบ'),{exact:true});await reason.fill('My verified number is not matched yet');
    await page.getByRole('button',{name:t('Request review','ส่งคำขอตรวจสอบ'),exact:true}).click();
    await expect(page.getByText(t('Waiting for administrator review','รอผู้ดูแลตรวจสอบ'),{exact:false})).toBeVisible();
    await page.reload();await expect(page.getByRole('button',{name:t('Request review','ส่งคำขอตรวจสอบ'),exact:true})).toHaveCount(0);
    cases[0].status='closed';cases[0].outcome='matched';cases[0].match_state='matched';matched=true;
    await page.getByRole('region',{name:t('Review my school identity','ขอตรวจสอบตัวตนของฉัน'),exact:true}).getByRole('button',{name:t('Refresh','โหลดใหม่'),exact:true}).click();
    await expect(page.getByText(t('Matched to the official class roster','จับคู่กับรายชื่อจากทะเบียนแล้ว'),{exact:true})).toBeVisible();
    await page.getByRole('link',{name:t('Open My classes','เปิดชั้นเรียนของฉัน'),exact:true}).click();
    await page.getByRole('tab',{name:t('LearnHouse classes','ชั้นเรียน LearnHouse'),exact:true}).click();
    await expect(page.getByRole('link',{name:t('Open released course','เปิดรายวิชาที่เผยแพร่แล้ว'),exact:true})).toBeVisible();
    assert.equal(await page.getByRole('button',{name:t('Manage roster','จัดการรายชื่อ'),exact:true}).count(),0);
   }
   assert.deepEqual(errors,[]);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,name+' overflow');
   await page.screenshot({path:evidence+'/'+name+'.png',fullPage:true});results.push({name,passed:true});
  }catch(e){await page.screenshot({path:evidence+'/'+name+'-failed.png',fullPage:true});console.log((await page.locator('body').innerText()).slice(-3500));throw e}
  await context.close();
 }
 fs.writeFileSync(evidence+'/ui-review-results.json',JSON.stringify(results,null,2));console.log(JSON.stringify({component_review_flows:results.length,passed:true}));
 }finally{await browser.close();server.close()}
})().catch(e=>{console.error(e);process.exitCode=1;server.close()});
