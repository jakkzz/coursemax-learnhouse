// Real component HTTP contracts with synthetic responses, not native-auth/DB acceptance.
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE_PATH||'playwright');
const expect=require((process.env.PLAYWRIGHT_MODULE_PATH||'playwright')+'/test').expect.configure({timeout:15000});
const evidence=process.env.LEARNHOUSE_UI_EVIDENCE,native=process.env.LEARNHOUSE_NATIVE_WEB;
assert(evidence&&native,'Provide private fixture output and the recorded native CSS artifact');
const css=fs.readdirSync(native+'/.next/static/chunks').filter(n=>n.endsWith('.css')).map(n=>fs.readFileSync(native+'/.next/static/chunks/'+n)).join('\n');
const server=http.createServer((req,res)=>{
 const p=new URL(req.url,'http://fixture').pathname;
 if(p==='/native.css'){res.setHeader('Content-Type','text/css');return res.end(css)}
 if(p==='/fixture.js'||p==='/fixture.css'){res.setHeader('Content-Type',p.endsWith('.css')?'text/css':'text/javascript');return res.end(fs.readFileSync(evidence+'/ui-public/RosterRefresh'+(p.endsWith('.css')?'.css':'.js')))}
 if(p.startsWith('/_next/static/')){const f=path.resolve(native,'.next/static',p.slice('/_next/static/'.length));if(f.startsWith(path.resolve(native,'.next/static')+'/')&&fs.existsSync(f))return res.end(fs.readFileSync(f));res.statusCode=404;return res.end()}
 res.setHeader('Content-Type','text/html');res.end('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/native.css"><link rel="stylesheet" href="/fixture.css"></head><body style="margin:0;background:#fafafa;font-family:system-ui"><div id="root"></div><script type="module" src="/fixture.js"></script></body></html>');
});
function people(count){return Array.from({length:count},(_,i)=>({id:i+1,student_number:String(6900000001+i),full_name_th:`Synthetic Student ${i+1} นางสาวนักศึกษาสมมติชื่อยาวเพื่อทดสอบการแสดงผลบนหน้าจอขนาดเล็ก`,faculty:'Synthetic faculty',program:'Synthetic program',source:'registry',status:'active',account_status:'unlinked',missing_count:0}))}
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_BIN,args:['--disable-dev-shm-usage']});
 const results=[];
 try{
 for(const lang of ['en','th'])for(const width of [1440,390])for(const role of ['teacher','student','withdrawn','official','unmatched','rows-0','rows-1','rows-1000']){
  const th=lang==='th',t=(en,thai)=>th?thai:en,name=`${role}-${lang}-${width}`;
  const context=await browser.newContext({viewport:{width,height:950},timezoneId:'Asia/Bangkok',reducedMotion:'reduce'}),page=await context.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.clock.install({time:new Date('2026-11-03T10:00:00Z')});
  const edge=role.startsWith('rows-'),count=edge?Number(role.slice(5)):40;
  let rows=people(count),version=1,status='ready',paused=false,control=0,checks=0,posts=[],wrongClass=false,transportFail=false,accessRequests=0;
  const cls=()=>({id:20,course_id:role==='unmatched'?null:10,course_uuid:role==='unmatched'?'':'course_fixture',course_name:'Synthetic roster class',course_available:role!=='withdrawn',academic_year:2569,semester:1,section:'P1',manageable:!['student','withdrawn'].includes(role),own_attendance_history_only:role==='withdrawn',version,active_count:rows.length,last_synced_at:count?'2026-11-03T04:00:00Z':null,registry_course_id:'100',registry_class_id:'200'});
  await page.route('**/api/v1/**',async route=>{
   const request=route.request(),p=new URL(request.url()).pathname.replace('/api/v1/academic-classes',''),method=request.method();let result={};
   if(method==='POST')posts.push({path:p,body:request.postDataJSON()});
   if(p==='')result={classes:[cls()],can_create:role!=='student',student_match_status:'matched'};
   else if(p==='/courses')result={courses:[{id:10,name:'Synthetic roster class',private:true,registry_course_id:'100',course_code:'990001'}],teachers:[],can_assign_teachers:false,teaching_assignments:[]};
   else if(p==='/connections/requests')result={requests:[],can_connect:false};
   else if(p==='/connections/official-roster')result={students:rows,fetched_at:'2026-11-03T10:00:00Z',source_url:'https://fixture.invalid/official'};
   else if(p.endsWith('/learning-access/status')){accessRequests++;result={status:'ready',can_configure:false};}
   else if(p==='/20/identity-reviews')result={cases:[]};
   else if(p==='/20/roster')result={class_id:20,version,students:rows,events:[]};
   else if(p==='/20/roster/refresh'){
    checks++;if(transportFail){transportFail=false;return route.fulfill({status:503,json:{detail:'Synthetic status outage'}})}
    result={class_id:wrongClass?21:20,class_version:wrongClass?999:version,control_version:control,paused,initial_review_required:count===0,status,last_attempt_at:'2026-11-03T10:00:00Z',last_accepted_at:'2026-11-03T04:00:00Z',next_check_at:'2026-11-03T16:00:00Z',delayed:false,recent:[]};wrongClass=false;
   }else if(p.endsWith('/refresh/check')){status='queued';result={status};}
   else if(p.endsWith('/refresh/settings')){paused=request.postDataJSON().paused;control++;result={paused,control_version:control};}
   else if(p.endsWith('/roster/preview'))result={preview_id:'a'.repeat(43),version,incoming_count:5,added_count:0,missing_count:35,withdraw_count:0,requires_large_drop_review:true,source_url:'https://fixture.invalid/official',changes:rows.slice(5).map(p=>({kind:'missing_once',student_number:p.student_number,name:p.full_name_th}))};
   else if(p.endsWith('/roster/apply')){version++;status='applied';result={applied:true,counts:{missing:35,withdrawn:0},version};}
   else if(p.endsWith('/membership')){rows[0].source='manual';rows[0].status=request.postDataJSON().status;version++;result={saved:true};}
   else return route.fulfill({status:404,json:{detail:'Unknown synthetic endpoint '+p}});
   await route.fulfill({status:p.endsWith('/refresh/check')?202:200,json:result});
  });
  await page.goto(`http://127.0.0.1:${server.address().port}/?lang=${lang}${role==='official'?'&official=1':''}`);
  try{
   if(role==='official'){
    await expect(page.getByRole('heading',{name:t('Official roster','รายชื่อจากทะเบียน'),exact:true})).toBeVisible();
    await page.getByRole('button',{name:t('Open saved roster','เปิดรายชื่อที่บันทึกไว้'),exact:true}).click();
    await expect(page.locator('#saved-handoff')).toHaveText('opened');
    await page.getByRole('button',{name:t('Refresh official roster','อัปเดตรายชื่อจากทะเบียน'),exact:true}).click();
    assert.equal(posts.length,0,'Official source viewing must not import');
   }else if(role==='unmatched'){
    await page.getByRole('button',{name:t('Open saved roster','เปิดรายชื่อที่บันทึกไว้'),exact:true}).click();
    await expect(page.locator('#saved-roster-title')).toBeVisible();
    await expect(page.getByRole('button',{name:t('Check now','ตรวจสอบตอนนี้'),exact:true})).toBeEnabled();
    assert.equal(accessRequests,0,'An unmatched school class is not native content');
   }else if(role==='withdrawn'){
    const ownHistory=page.getByRole('link',{name:t('My attendance','การเข้าเรียนของฉัน'),exact:true});await expect(ownHistory).toHaveAttribute('href','/attendance?class=20');
    assert.equal(await page.getByRole('button',{name:t('Open schedule','เปิดตารางเรียน'),exact:true}).count(),0);assert.equal(await page.getByRole('button',{name:t('Manage roster','จัดการรายชื่อ'),exact:true}).count(),0);assert.equal(await page.getByRole('link',{name:t('Open released course','เปิดรายวิชาที่เผยแพร่แล้ว'),exact:true}).count(),0);
    await page.getByRole('tab',{name:t('LearnHouse classes','ชั้นเรียน LearnHouse'),exact:true}).click();await expect(ownHistory).toHaveAttribute('href','/attendance?class=20');assert.equal(await page.getByText(t('Course content is not available to this account','บัญชีนี้ยังเปิดเนื้อหารายวิชาไม่ได้'),{exact:true}).count(),0);
   }else{
    await page.getByRole('tab',{name:t('LearnHouse classes','ชั้นเรียน LearnHouse'),exact:true}).click();
    if(role==='student'){
     await expect(page.getByRole('heading',{name:'Synthetic roster class',exact:true})).toBeVisible();await expect(page.getByRole('link',{name:t('Open released course','เปิดรายวิชาที่เผยแพร่แล้ว'),exact:true})).toBeVisible();
     assert.equal(await page.getByRole('button',{name:t('Manage roster','จัดการรายชื่อ'),exact:true}).count(),0);
     assert.equal(checks,0);assert.equal(await page.getByText('Synthetic Student 1',{exact:false}).count(),0);
    }else if(edge){
     await page.getByRole('button',{name:t('Manage roster','จัดการรายชื่อ'),exact:true}).click();
     await expect(page.locator('#saved-roster-title')).toBeVisible();
     if(count===0){await expect(page.getByRole('heading',{name:t('No roster yet','ยังไม่มีรายชื่อชั้นเรียน'),exact:true})).toBeVisible();await expect(page.getByRole('button',{name:t('Review changes','ตรวจสอบการเปลี่ยนแปลง'),exact:true})).toBeEnabled()}
     else{await expect(page.getByRole('button',{name:t('Member actions','จัดการสมาชิก'),exact:true})).toHaveCount(count);await page.getByLabel(t('Search name, number or program','ค้นหาชื่อ รหัสนักศึกษา หรือสาขาวิชา'),{exact:true}).fill('no synthetic match');await expect(page.getByRole('button',{name:t('Member actions','จัดการสมาชิก'),exact:true})).toHaveCount(0)}
    }else{
     await page.getByRole('button',{name:t('Manage roster','จัดการรายชื่อ'),exact:true}).click();
     const check=page.getByRole('button',{name:t('Check now','ตรวจสอบตอนนี้'),exact:true});await expect(check).toBeEnabled();
     await page.getByLabel(t('Search name, number or program','ค้นหาชื่อ รหัสนักศึกษา หรือสาขาวิชา'),{exact:true}).fill('Synthetic Student 1 ');
     await page.getByRole('button',{name:t('Member actions','จัดการสมาชิก'),exact:true}).first().click();
     const reason=page.getByLabel(t('Reason','เหตุผล'),{exact:true});await reason.fill('Keep the intended withdrawal');
     await reason.focus();
     version++;rows[0].status='withdrawn';status='applied';await page.clock.runFor(10001);
     await expect(page.getByRole('button',{name:t('Reload and review','โหลดใหม่และตรวจสอบ'),exact:true})).toBeVisible();
     assert.equal(await reason.inputValue(),'Keep the intended withdrawal');assert.equal(await reason.evaluate(e=>e===document.activeElement),true);
     await expect(page.getByRole('button',{name:t('Withdraw member','ถอนสถานะสมาชิก'),exact:true})).toBeDisabled();
     await page.getByRole('button',{name:t('Reload and review','โหลดใหม่และตรวจสอบ'),exact:true}).click();
     await expect(page.getByRole('button',{name:t('Withdraw member','ถอนสถานะสมาชิก'),exact:true})).toBeEnabled();
     assert.equal(await reason.inputValue(),'Keep the intended withdrawal');
     await page.getByRole('button',{name:t('Withdraw member','ถอนสถานะสมาชิก'),exact:true}).click();
     await expect(page.getByRole('button',{name:t('Withdraw member','ถอนสถานะสมาชิก'),exact:true})).toHaveCount(0);
     assert.equal(posts.find(p=>p.path.endsWith('/membership')).body.status,'withdrawn','Do not flip intended Withdraw to Restore');
     await page.getByRole('button',{name:t('Add existing student','เพิ่มนักศึกษาที่มีบัญชีแล้ว'),exact:true}).click();
     const email=page.getByLabel(t('Verified Google sign-in email','อีเมล Google ที่ใช้เข้าสู่ระบบและยืนยันแล้ว'),{exact:true});await email.fill('synthetic@example.invalid');
     await reason.fill('Keep this unfinished draft');await reason.focus();
     await check.click();await expect(page.getByText(t('Check queued. Saved membership has not changed.','รอการตรวจสอบ รายชื่อที่บันทึกไว้ยังไม่เปลี่ยน'),{exact:true})).toBeVisible();
     await reason.focus();version++;status='source_failed';await page.clock.runFor(10001);
     await expect(page.getByRole('button',{name:t('Try again','ลองอีกครั้ง'),exact:true})).toBeVisible();
     assert.equal(await email.inputValue(),'synthetic@example.invalid');assert.equal(await reason.inputValue(),'Keep this unfinished draft');assert.equal(await reason.evaluate(e=>e===document.activeElement),true);
     transportFail=true;await page.clock.runFor(10001);await expect(page.getByRole('button',{name:t('Reload status','โหลดสถานะใหม่'),exact:true})).toBeVisible();
     assert.equal(await reason.inputValue(),'Keep this unfinished draft');assert.equal(await reason.evaluate(e=>e===document.activeElement),true);
     status='needs_review';await page.clock.runFor(10001);
     await page.getByRole('button',{name:t('Review changes','ตรวจสอบการเปลี่ยนแปลง'),exact:true}).click();
     await expect(page.locator('#roster-review-title')).toBeFocused();
     await page.getByRole('checkbox').check();await page.getByRole('button',{name:t('Apply roster','บันทึกรายชื่อ'),exact:true}).click();
     await expect(page.locator('#roster-review-title')).toHaveCount(0);
     assert.equal(posts.find(p=>p.path.endsWith('/roster/apply')).body.confirm_large_drop,true);
     await page.getByRole('button',{name:t('Pause checks','พักการตรวจสอบ'),exact:true}).click();
     await expect(page.getByRole('button',{name:t('Resume checks','ตรวจสอบต่อ'),exact:true})).toBeVisible();
     await page.getByRole('button',{name:t('Resume checks','ตรวจสอบต่อ'),exact:true}).click();
     await expect(page.getByRole('button',{name:t('Pause checks','พักการตรวจสอบ'),exact:true})).toBeVisible();
     wrongClass=true;await page.clock.runFor(10001);assert.equal(await page.getByRole('button',{name:t('Reload and review','โหลดใหม่และตรวจสอบ'),exact:true}).count(),0);
     await page.getByRole('button',{name:t('All classes','ชั้นเรียนทั้งหมด'),exact:true}).click();
     const stopped=checks;await page.clock.runFor(20001);assert.equal(checks,stopped,'Stop status polling after leaving the roster');
     await page.getByRole('button',{name:t('Manage roster','จัดการรายชื่อ'),exact:true}).click();
     await expect(page.locator('#saved-roster-title')).toBeVisible();
    }
   }
   const statusRegion=page.getByRole('region',{name:t('Roster checks','การอัปเดตรายชื่อ'),exact:true});
   if(await statusRegion.count()){const line=await statusRegion.getByRole('status').first().boundingBox();assert(line&&line.width>=200,name+' status text must not collapse beside action buttons')}
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,name+' overflow');
   assert.deepEqual(errors,[]);await page.screenshot({path:evidence+'/'+name+'.png',fullPage:false});results.push({name,passed:true});
  }catch(error){await page.screenshot({path:evidence+'/'+name+'-failed.png'});console.log((await page.locator('body').innerText()).slice(-4000));throw error;}
  finally{await context.close()}
 }
 fs.writeFileSync(evidence+'/ui-results.json',JSON.stringify(results,null,2));console.log(JSON.stringify(results,null,2));
 }finally{await browser.close();await new Promise(resolve=>server.close(resolve))}
})().catch(error=>{console.error(error);process.exitCode=1});
